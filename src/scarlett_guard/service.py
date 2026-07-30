"""把設定、裝置、驅動模式、熱鍵、紀錄串起來的核心服務層。

UI（pywebview）與系統匣（pystray）都只跟這一層對話，
所以兩邊的行為必然一致。
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

from . import autostart, device, driver_mode, hotkey, i18n
from .i18n import t
from .config import Config
from .history import History


class GuardService:
    def __init__(self) -> None:
        self.config = Config()
        # 語言要在任何會產生訊息的東西建立之前先設定好
        i18n.set_language(self.config.get("language"))
        self.history = History()
        self.history.trim()

        # 重置與模式切換共用同一把鎖：兩者都會讓裝置重新列舉，同時進行必然互踩
        self._action_lock = threading.Lock()
        self._listeners: list[Callable[[str, dict[str, Any]], None]] = []
        self._busy = False
        self._cached_snapshot: dict[str, Any] = {}
        self._snapshot_at = 0.0
        self._cached_mode: dict[str, Any] = {}
        self._mode_at = 0.0

        self.hotkeys = hotkey.HotkeyManager(on_trigger=lambda: self.reset("hotkey"))

    # ------------------------------------------------------------------
    # 啟動 / 關閉
    # ------------------------------------------------------------------
    def start(self) -> None:
        self.history.log("app_start", elevated=device.is_elevated())
        self.hotkeys.apply(self.config.get("hotkey"), self.config.get("hotkey_enabled"))

    def shutdown(self) -> None:
        self.hotkeys.stop()
        self.history.log("app_stop")

    # ------------------------------------------------------------------
    # 事件廣播（給 UI 與系統匣）
    # ------------------------------------------------------------------
    def subscribe(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        self._listeners.append(callback)

    def _emit(self, channel: str, payload: dict[str, Any]) -> None:
        for callback in list(self._listeners):
            try:
                callback(channel, payload)
            except Exception:
                continue

    # ------------------------------------------------------------------
    # 裝置狀態
    # ------------------------------------------------------------------
    def snapshot(self, force: bool = False) -> dict[str, Any]:
        """裝置狀態。PowerShell 查詢頗慢，所以做 3 秒快取。"""
        now = time.monotonic()
        if not force and self._cached_snapshot and now - self._snapshot_at < 3.0:
            return self._cached_snapshot
        data = device.snapshot(self.config.get("device_instance_id"))
        data["busy"] = self._busy
        self._cached_snapshot = data
        self._snapshot_at = now
        return data

    def invalidate_snapshot(self) -> None:
        self._snapshot_at = 0.0
        self._mode_at = 0.0

    def _emit_fresh_state(self) -> None:
        """動作收尾後在背景強制查一次並推送給 UI 與系統匣。

        刻意放到背景執行緒：這兩支 PowerShell 合起來要五到八秒，擺在呼叫路徑上
        會讓「已切換完成」的提示晚好幾秒才出現 —— 而 busy 早就解除了，
        使用者會看到按鈕先解鎖、結果才姍姍來遲，讀起來很不一致。

        這是唯一該用 force 的地方；查完之後快取是熱的，前端隨後的補查
        會直接命中快取，不會再多跑 PowerShell。
        """
        def run() -> None:
            try:
                self._emit("device", self.snapshot(force=True))
                self._emit("driver_mode", self.driver_mode(force=True))
            except Exception:
                # 這只是 UI 的狀態刷新，失敗不該影響任何實際動作
                pass

        threading.Thread(target=run, name="refresh", daemon=True).start()

    # ------------------------------------------------------------------
    # 驅動模式
    # ------------------------------------------------------------------
    def driver_mode(self, force: bool = False) -> dict[str, Any]:
        """目前的驅動模式與判斷依據。和 snapshot 一樣做快取，PowerShell 很慢。"""
        now = time.monotonic()
        if not force and self._cached_mode and now - self._mode_at < 3.0:
            return self._cached_mode
        state = driver_mode.probe()
        state["busy"] = self._busy
        state["focusrite_inf"] = str(
            driver_mode.find_focusrite_inf(self.config.get("focusrite_inf_path")) or ""
        )
        state["elevated"] = device.is_elevated()
        self._cached_mode = state
        self._mode_at = now
        return state

    def switch_driver_mode(self, mode: str, source: str = "manual") -> dict[str, Any]:
        """切換驅動模式。"""
        if not self._action_lock.acquire(blocking=False):
            return {"ok": False, "message": t("mode.busy"), "detail": ""}

        try:
            self._busy = True
            self._emit("busy", {"busy": True, "source": f"mode:{source}"})

            result = driver_mode.switch_mode(
                mode,
                focusrite_inf_override=self.config.get("focusrite_inf_path") or "",
                settle_seconds=float(self.config.get("mode_settle_seconds", 2.0)),
            )

            self.invalidate_snapshot()
            self._log_mode_switch(source, mode, result)
            return result.to_dict()
        finally:
            self._busy = False
            self._emit("busy", {"busy": False, "source": f"mode:{source}"})
            self._emit_fresh_state()
            self._action_lock.release()

    def repair_driver_binding(self) -> dict[str, Any]:
        """救回卡在「沒有驅動」或「音訊路徑沒起來」狀態的裝置。"""
        if not self._action_lock.acquire(blocking=False):
            return {"ok": False, "message": t("mode.busy"), "detail": ""}
        try:
            self._busy = True
            self._emit("busy", {"busy": True, "source": "mode:repair"})

            result = driver_mode.repair()

            self.invalidate_snapshot()
            self._log_mode_switch("repair", result.extra.get("mode", ""), result)
            return result.to_dict()
        finally:
            self._busy = False
            self._emit("busy", {"busy": False, "source": "mode:repair"})
            self._emit_fresh_state()
            self._action_lock.release()

    def _log_mode_switch(
        self, source: str, requested: str, result: device.ActionResult
    ) -> None:
        record = self.history.log(
            f"mode_{source}",
            ok=result.ok,
            requested=requested,
            resulting=result.extra.get("mode", ""),
            message=result.message,
            detail=result.detail[:500],
            duration_ms=result.duration_ms,
        )
        self._emit("history", record)

    # ------------------------------------------------------------------
    # 重置 —— 軟體版拔插
    # ------------------------------------------------------------------
    def reset(self, source: str = "manual") -> dict[str, Any]:
        """source: manual | hotkey | tray"""
        if not self._action_lock.acquire(blocking=False):
            return {"ok": False, "message": t("dev.busy"), "detail": ""}

        try:
            self._busy = True
            self._emit("busy", {"busy": True, "source": source})

            target = self.config.get("device_instance_id") or ""
            primary = device.find_primary_device(target)
            if primary is None:
                result = device.ActionResult(
                    False, t("dev.notfound"), t("dev.notfound.detail")
                )
                self._log_reset(source, result, "")
                return result.to_dict()

            result = device.restart_device(primary.instance_id)

            if result.ok:
                device.wait_until_present(primary.instance_id, timeout=15.0)
                settle = float(self.config.get("post_reset_settle_seconds", 3.0))
                if settle > 0:
                    time.sleep(settle)

            self.invalidate_snapshot()
            self._log_reset(source, result, primary.friendly_name)
            return result.to_dict()
        finally:
            self._busy = False
            self._emit("busy", {"busy": False, "source": source})
            self._emit_fresh_state()
            self._action_lock.release()

    def _log_reset(self, source: str, result: device.ActionResult, device_name: str) -> None:
        record = self.history.log(
            f"reset_{source}",
            ok=result.ok,
            message=result.message,
            detail=result.detail[:500],
            duration_ms=result.duration_ms,
            device=device_name,
            method=result.extra.get("method", ""),
        )
        self._emit("history", record)

    # ------------------------------------------------------------------
    # 設定
    # ------------------------------------------------------------------
    def update_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        before = self.config.as_dict()
        self.config.update(values)
        after = self.config.as_dict()
        messages: list[str] = []

        if after["language"] != before["language"]:
            # 之後產生的所有後端訊息都會用新語言；系統匣選單是在啟動時建好的，
            # 要下次啟動才會跟著換。
            i18n.set_language(after["language"])

        if (
            after["hotkey"] != before["hotkey"]
            or after["hotkey_enabled"] != before["hotkey_enabled"]
        ):
            ok, message = self.hotkeys.apply(after["hotkey"], after["hotkey_enabled"])
            messages.append(message)
            if not ok:
                # 熱鍵設壞了就退回原本能用的組合，不要讓使用者失去這個功能
                self.config.set("hotkey", before["hotkey"])
                self.hotkeys.apply(before["hotkey"], before["hotkey_enabled"])
                messages.append(t("hk.reverted", combo=before["hotkey"]))

        self._emit("settings", after)
        return {"ok": True, "config": after, "messages": messages}

    # ------------------------------------------------------------------
    # 幽靈裝置清理
    # ------------------------------------------------------------------
    def ghosts(self) -> list[dict[str, Any]]:
        return [g.to_dict() for g in device.list_ghosts()]

    def remove_ghosts(self, instance_ids: list[str]) -> dict[str, Any]:
        """移除幽靈裝置。只允許移除目前確實為 Unknown 狀態的節點。"""
        allowed = {g.instance_id.upper() for g in device.list_ghosts()}
        results: list[dict[str, Any]] = []
        removed = 0
        for instance_id in instance_ids:
            if instance_id.upper() not in allowed:
                results.append(
                    {
                        "instance_id": instance_id,
                        "ok": False,
                        "message": t("ghost.skip"),
                    }
                )
                continue
            result = device.remove_ghost(instance_id)
            if result.ok:
                removed += 1
            results.append({"instance_id": instance_id, **result.to_dict()})

        record = self.history.log("ghost_cleanup", removed=removed, requested=len(instance_ids))
        self._emit("history", record)
        self.invalidate_snapshot()
        return {"ok": removed > 0, "removed": removed, "results": results}

    # ------------------------------------------------------------------
    # 其他
    # ------------------------------------------------------------------
    def autostart_state(self) -> bool:
        return autostart.is_enabled()

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        ok, message = autostart.enable() if enabled else autostart.disable()
        return {"ok": ok, "message": message, "enabled": autostart.is_enabled()}
