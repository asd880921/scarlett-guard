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
        self._cached_inf = ""
        self._inf_at = 0.0

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

    def _emit_fresh_state(self, refresh_mode: bool = False) -> None:
        """動作收尾後在背景刷新狀態並推送給 UI 與系統匣。

        刻意放到背景執行緒：查裝置要跑 PowerShell（好幾秒），擺在呼叫路徑上
        會讓「已完成」的提示晚好幾秒才出現 —— 而 busy 早就解除了，
        使用者會看到按鈕先解鎖、結果才姍姍來遲，讀起來很不一致。

        `refresh_mode` 只有在動作本身沒有探測過模式時（例如重置）才需要開；
        切換與修復都已經把自己的探測結果餵回快取了，再查一次是白費。
        """
        def run() -> None:
            try:
                self._emit("device", self.snapshot(force=True))
                self._emit("driver_mode", self.driver_mode(force=refresh_mode))
            except Exception:
                # 這只是 UI 的狀態刷新，失敗不該影響任何實際動作
                pass

        threading.Thread(target=run, name="refresh", daemon=True).start()

    # ------------------------------------------------------------------
    # 驅動模式
    # ------------------------------------------------------------------
    def _focusrite_inf(self) -> str:
        """原廠 INF 的位置。查一次要跑 `pnputil /enum-drivers`（約兩秒），
        但它只有在重裝驅動時才會變，所以快取久一點。"""
        now = time.monotonic()
        if self._cached_inf and now - self._inf_at < 60.0:
            return self._cached_inf
        self._cached_inf = str(
            driver_mode.find_focusrite_inf(self.config.get("focusrite_inf_path")) or ""
        )
        self._inf_at = now
        return self._cached_inf

    def _decorate_mode(self, probe: dict[str, Any]) -> dict[str, Any]:
        """把探測結果補上 UI 需要、但不必再跑 PowerShell 的欄位。"""
        state = dict(probe)
        state["busy"] = self._busy
        state["elevated"] = device.is_elevated()
        state["focusrite_inf"] = self._focusrite_inf()
        return state

    def driver_mode(self, force: bool = False) -> dict[str, Any]:
        """目前的驅動模式與判斷依據。和 snapshot 一樣做快取，PowerShell 很慢。"""
        now = time.monotonic()
        if not force and self._cached_mode and now - self._mode_at < 3.0:
            # busy 是即時狀態，不該被快取住
            self._cached_mode["busy"] = self._busy
            return self._cached_mode
        self._cached_mode = self._decorate_mode(driver_mode.probe())
        self._mode_at = now
        return self._cached_mode

    def cached_driver_mode(self) -> dict[str, Any]:
        """只回最後一次已知的狀態，**絕不查詢**。

        給系統匣選單用：選單的 checked / enabled 回呼跑在 pystray 的 UI 執行緒上，
        在那裡跑 PowerShell 會讓整個選單凍住好幾秒，切換進行中甚至會卡到沒有回應。
        """
        return self._cached_mode or {}

    def _seed_mode_cache(self, probe: dict[str, Any] | None) -> None:
        """用動作自己已經做過的探測結果餵回快取。

        切換與修復在收尾前都已經完整探測過一次，沒有理由再查一遍 —— 更重要的是，
        不餵回去的話前端會有五到八秒拿到的還是**切換前**的狀態：重置按鈕會依舊狀態
        誤判成可按，模式指示器也會先跳回舊位置、過幾秒才彈回來。
        """
        if not probe:
            return
        self._cached_mode = self._decorate_mode(probe)
        self._mode_at = time.monotonic()

    def switch_driver_mode(self, mode: str, source: str = "manual") -> dict[str, Any]:
        """切換驅動模式。"""
        if not self._action_lock.acquire(blocking=False):
            return {"ok": False, "message": t("mode.busy"),
                    "detail": t("mode.busy.detail"), "blocked": True}

        try:
            self._busy = True
            self._emit("busy", {"busy": True, "source": f"mode:{source}"})

            result = driver_mode.switch_mode(
                mode,
                focusrite_inf_override=self.config.get("focusrite_inf_path") or "",
                settle_seconds=float(self.config.get("mode_settle_seconds", 2.0)),
            )

            self._snapshot_at = 0.0
            # 切換自己已經探測過了，直接餵回快取；連同結果一起回傳，
            # 前端就能在拿到結果的同一刻更新畫面，沒有任何一段舊狀態的空窗。
            self._seed_mode_cache(result.extra.get("probe"))
            self._log_mode_switch(source, mode, result)
            payload = result.to_dict()
            payload["driver_mode"] = self.driver_mode()
            return payload
        finally:
            self._busy = False
            self._emit("busy", {"busy": False, "source": f"mode:{source}"})
            self._emit_fresh_state()
            self._action_lock.release()

    def repair_driver_binding(self) -> dict[str, Any]:
        """救回卡在「沒有驅動」或「音訊路徑沒起來」狀態的裝置。"""
        if not self._action_lock.acquire(blocking=False):
            return {"ok": False, "message": t("mode.busy"),
                    "detail": t("mode.busy.detail"), "blocked": True}
        try:
            self._busy = True
            self._emit("busy", {"busy": True, "source": "mode:repair"})

            result = driver_mode.repair()

            self._snapshot_at = 0.0
            self._seed_mode_cache(result.extra.get("probe"))
            self._log_mode_switch("repair", result.extra.get("mode", ""), result)
            payload = result.to_dict()
            payload["driver_mode"] = self.driver_mode()
            return payload
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
    def reset_available(self) -> bool:
        """重置只在錄音模式下有意義，而且也只有那時才會成功。

        日常模式走的是 Windows 內建類別驅動，本來就沒有原廠驅動那個
        「丟包後不重新同步」的缺陷 —— 沒有東西需要重置。而且真的按下去也會失敗：
        `usbaudio2` 的音訊端點被 AudioEndpointBuilder 持有，
        `pnputil /restart-device` 拆不掉子節點，只會回 exit 3010
        （System reboot is needed），備援的 Disable-PnpDevice 同樣失敗。

        刻意讀快取而不另外查：熱鍵路徑上多跑一支 PowerShell 會讓按下去卡三秒。
        還沒探測過時一律放行 —— 這是救援工具，不確定的時候不該擋住使用者。
        """
        mode = (self._cached_mode or {}).get("mode", "")
        return mode != driver_mode.MODE_DAILY

    def reset(self, source: str = "manual") -> dict[str, Any]:
        """source: manual | hotkey | tray"""
        if not self.reset_available():
            # 熱鍵在日常模式下單純失效，不發任何訊息、也不寫紀錄 ——
            # 使用者按到的是一個此刻不適用的快捷鍵，不是出了錯。
            if source == "hotkey":
                return {"ok": False, "message": "", "detail": "", "blocked": True}
            return {
                "ok": False,
                "message": t("reset.blocked"),
                "detail": t("reset.blocked.detail"),
                "blocked": True,
            }

        if not self._action_lock.acquire(blocking=False):
            return {"ok": False, "message": t("dev.busy"),
                    "detail": t("dev.busy.detail"), "blocked": True}

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
            # 重置沒有自己探測模式，而重新列舉可能改變 complete / adapter_id，
            # 所以這裡要真的重查一次
            self._emit_fresh_state(refresh_mode=True)
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
