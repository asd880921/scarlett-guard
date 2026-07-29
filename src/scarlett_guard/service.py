"""把設定、裝置、監聽、熱鍵、紀錄串起來的核心服務層。

UI（pywebview）與系統匣（pystray）都只跟這一層對話，
所以兩邊的行為必然一致。
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

from . import autostart, device, hotkey, monitor
from .config import Config
from .history import History


class GuardService:
    def __init__(self) -> None:
        self.config = Config()
        self.history = History()
        self.history.trim()

        self._reset_lock = threading.Lock()
        self._listeners: list[Callable[[str, dict[str, Any]], None]] = []
        self._busy = False
        self._auto_recover_suspended = False
        self._last_auto_reset_at = 0.0
        self._cached_snapshot: dict[str, Any] = {}
        self._snapshot_at = 0.0

        self.monitor = monitor.AudioMonitor(
            self.config,
            on_anomaly=self._handle_anomaly,
            on_state_change=lambda: self._emit("monitor", self.monitor_state()),
        )
        self.hotkeys = hotkey.HotkeyManager(on_trigger=lambda: self.reset("hotkey"))

    # ------------------------------------------------------------------
    # 啟動 / 關閉
    # ------------------------------------------------------------------
    def start(self) -> None:
        self.history.log("app_start", elevated=device.is_elevated())
        self.hotkeys.apply(self.config.get("hotkey"), self.config.get("hotkey_enabled"))
        if self.config.get("monitor_enabled"):
            self.monitor.start()

    def shutdown(self) -> None:
        self.hotkeys.stop()
        self.monitor.stop()
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
        data["auto_recover_suspended"] = self._auto_recover_suspended
        self._cached_snapshot = data
        self._snapshot_at = now
        return data

    def invalidate_snapshot(self) -> None:
        self._snapshot_at = 0.0

    # ------------------------------------------------------------------
    # 重置 —— 整個程式的核心動作
    # ------------------------------------------------------------------
    def reset(self, source: str = "manual") -> dict[str, Any]:
        """軟體版拔插。source: manual | hotkey | tray | auto"""
        if not self._reset_lock.acquire(blocking=False):
            return {"ok": False, "message": "已有重置作業進行中", "detail": ""}

        try:
            self._busy = True
            self._emit("busy", {"busy": True, "source": source})

            target = self.config.get("device_instance_id") or ""
            primary = device.find_primary_device(target)
            if primary is None:
                result = device.ActionResult(
                    False, "找不到 Focusrite 裝置", "請確認 USB 已連接。"
                )
                self._log_reset(source, result, "")
                return result.to_dict()

            # 重置期間 stream 必然中斷，先暫停偵測否則一定誤判成 stall
            was_monitoring = self.monitor.running
            if was_monitoring:
                self.monitor.pause()

            result = device.restart_device(primary.instance_id)

            if result.ok:
                device.wait_until_present(primary.instance_id, timeout=15.0)
                settle = float(self.config.get("post_reset_settle_seconds", 3.0))
                if settle > 0:
                    time.sleep(settle)

            if was_monitoring:
                # 裝置重新列舉後索引會變，串流必須整個重開
                self.monitor.stop()
                ok, message = self.monitor.start()
                if not ok:
                    result.detail = (result.detail + "\n監聽重啟失敗：" + message).strip()

            self.invalidate_snapshot()
            self._log_reset(source, result, primary.friendly_name)
            return result.to_dict()
        finally:
            self._busy = False
            self._emit("busy", {"busy": False, "source": source})
            self._emit("device", self.snapshot(force=True))
            self._reset_lock.release()

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
    # 自動復原
    # ------------------------------------------------------------------
    def _handle_anomaly(self, anomaly: monitor.Anomaly) -> None:
        record = self.history.log(
            "anomaly",
            reason=anomaly.reason,
            label=anomaly.label,
            detail=anomaly.detail,
            metrics=anomaly.metrics,
            auto_recover=bool(self.config.get("auto_recover")),
        )
        self._emit("anomaly", record)
        self._emit("history", record)

        if not self.config.get("auto_recover") or self._auto_recover_suspended:
            self.monitor.resume()
            return

        # 安全閥一：冷卻時間
        cooldown = float(self.config.get("cooldown_seconds", 30.0))
        since_last = time.monotonic() - self._last_auto_reset_at
        if self._last_auto_reset_at and since_last < cooldown:
            self.history.log(
                "auto_skipped",
                reason="cooldown",
                detail=f"距離上次自動重置僅 {since_last:.0f} 秒，未達冷卻時間 {cooldown:.0f} 秒。",
            )
            self.monitor.resume()
            return

        # 安全閥二：每小時上限，避免在裝置真的壞掉時無限重置
        limit = int(self.config.get("max_resets_per_hour", 6))
        if limit > 0 and self.history.resets_since(3600) >= limit:
            self._auto_recover_suspended = True
            record = self.history.log(
                "auto_suspended",
                detail=f"一小時內已重置 {limit} 次，自動復原已暫停以避免無限迴圈。",
            )
            self._emit("auto_suspended", record)
            self._emit("history", record)
            self.monitor.resume()
            return

        self._last_auto_reset_at = time.monotonic()
        self.reset("auto")
        self.monitor.resume()

    def resume_auto_recover(self) -> None:
        self._auto_recover_suspended = False
        self._last_auto_reset_at = 0.0
        self._emit("device", self.snapshot(force=True))

    # ------------------------------------------------------------------
    # 監聽
    # ------------------------------------------------------------------
    def monitor_state(self) -> dict[str, Any]:
        state = self.monitor.telemetry()
        state["auto_recover"] = bool(self.config.get("auto_recover"))
        state["auto_recover_suspended"] = self._auto_recover_suspended
        return state

    def set_monitor_enabled(self, enabled: bool) -> dict[str, Any]:
        self.config.set("monitor_enabled", bool(enabled))
        if enabled:
            ok, message = self.monitor.start()
        else:
            self.monitor.stop()
            ok, message = True, "已停止監聽"
        return {"ok": ok, "message": message, "state": self.monitor_state()}

    # ------------------------------------------------------------------
    # 設定
    # ------------------------------------------------------------------
    def update_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        before = self.config.as_dict()
        self.config.update(values)
        after = self.config.as_dict()
        messages: list[str] = []

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
                messages.append(f"已還原為先前的組合：{before['hotkey']}")

        needs_restart = any(
            after[key] != before[key]
            for key in ("monitor_input_device", "monitor_samplerate", "monitor_blocksize")
        )
        if needs_restart and self.monitor.running:
            self.monitor.stop()
            ok, message = self.monitor.start()
            messages.append(message)

        if after["monitor_enabled"] != before["monitor_enabled"]:
            result = self.set_monitor_enabled(after["monitor_enabled"])
            messages.append(result["message"])

        if after["auto_recover"] and not before["auto_recover"]:
            self._auto_recover_suspended = False

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
                        "message": "略過：此裝置目前並非幽靈狀態",
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

    def input_devices(self) -> list[dict[str, Any]]:
        return monitor.list_input_devices()
