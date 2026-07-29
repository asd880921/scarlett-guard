"""pywebview 的 JS ↔ Python 橋接層。

前端所有呼叫都經過這裡；每個方法都保證回傳可序列化的 dict／list，
並且不拋例外到 JS 端（否則前端只會拿到一個沒有訊息的 rejection）。
"""
from __future__ import annotations

import functools
import traceback
from typing import Any, Callable

from . import device, elevation, hotkey, i18n
from .paths import HISTORY_PATH, CONFIG_PATH, data_dir
from .service import GuardService


def _safe(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            return {
                "ok": False,
                "message": f"{type(exc).__name__}: {exc}",
                "detail": traceback.format_exc(limit=4),
            }

    return wrapper


class Api:
    def __init__(self, service: GuardService) -> None:
        self.service = service
        self.window = None  # 由 main 在視窗建立後填入
        self._on_hide: Callable[[], None] | None = None
        self._on_quit: Callable[[], None] | None = None

    def bind_window(
        self,
        window: Any,
        on_hide: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self.window = window
        self._on_hide = on_hide
        self._on_quit = on_quit

    # ------------------------------------------------------------------
    # 狀態查詢
    # ------------------------------------------------------------------
    @_safe
    def bootstrap(self) -> dict[str, Any]:
        """開頁時一次拿齊所有資料，避免前端連發五六個請求。"""
        return {
            "ok": True,
            "device": self.service.snapshot(force=True),
            "config": self.service.config.as_dict(),
            "monitor": self.service.monitor_state(),
            "stats": self.service.history.stats(),
            "history": self.service.history.recent(60),
            "input_devices": self.service.input_devices(),
            "autostart": self.service.autostart_state(),
            "hotkey_active": self.service.hotkeys.active,
            "hotkey_error": self.service.hotkeys.error,
            "elevated": device.is_elevated(),
            "paths": {
                "config": str(CONFIG_PATH),
                "history": str(HISTORY_PATH),
                "data_dir": str(data_dir()),
            },
        }

    @_safe
    def device_status(self, force: bool = False) -> dict[str, Any]:
        return {"ok": True, "device": self.service.snapshot(force=force)}

    @_safe
    def monitor_status(self) -> dict[str, Any]:
        return {"ok": True, "monitor": self.service.monitor_state()}

    @_safe
    def stats(self) -> dict[str, Any]:
        return {"ok": True, "stats": self.service.history.stats()}

    @_safe
    def history(self, limit: int = 60) -> dict[str, Any]:
        return {"ok": True, "history": self.service.history.recent(int(limit))}

    # ------------------------------------------------------------------
    # 動作
    # ------------------------------------------------------------------
    @_safe
    def reset(self, source: str = "manual") -> dict[str, Any]:
        return self.service.reset(source or "manual")

    @_safe
    def set_monitor_enabled(self, enabled: bool) -> dict[str, Any]:
        return self.service.set_monitor_enabled(bool(enabled))

    @_safe
    def resume_auto_recover(self) -> dict[str, Any]:
        self.service.resume_auto_recover()
        return {"ok": True, "message": "自動復原已重新啟用"}

    @_safe
    def update_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        return self.service.update_settings(values or {})

    @_safe
    def reset_settings(self) -> dict[str, Any]:
        self.service.config.reset_to_defaults()
        cfg = self.service.config.as_dict()
        i18n.set_language(cfg["language"])
        self.service.hotkeys.apply(cfg["hotkey"], cfg["hotkey_enabled"])
        return {"ok": True, "config": cfg, "messages": [i18n.t("cfg.restored")]}

    @_safe
    def validate_hotkey(self, combo: str) -> dict[str, Any]:
        ok, message = hotkey.validate(combo)
        return {"ok": ok, "message": message}

    @_safe
    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        return self.service.set_autostart(bool(enabled))

    @_safe
    def ghosts(self) -> dict[str, Any]:
        return {"ok": True, "ghosts": self.service.ghosts()}

    @_safe
    def remove_ghosts(self, instance_ids: list[str]) -> dict[str, Any]:
        return self.service.remove_ghosts(list(instance_ids or []))

    @_safe
    def clear_history(self) -> dict[str, Any]:
        self.service.history.clear()
        return {"ok": True, "message": "紀錄已清空"}

    @_safe
    def input_devices(self) -> dict[str, Any]:
        return {"ok": True, "input_devices": self.service.input_devices()}

    # ------------------------------------------------------------------
    # 視窗與權限
    # ------------------------------------------------------------------
    @_safe
    def relaunch_elevated(self) -> dict[str, Any]:
        ok, message = elevation.relaunch_as_admin()
        if ok and self._on_quit:
            self._on_quit()
        return {"ok": ok, "message": message}

    @_safe
    def hide_window(self) -> dict[str, Any]:
        if self._on_hide:
            self._on_hide()
        return {"ok": True}

    @_safe
    def quit_app(self) -> dict[str, Any]:
        if self._on_quit:
            self._on_quit()
        return {"ok": True}

    @_safe
    def open_data_folder(self) -> dict[str, Any]:
        import os

        os.startfile(str(data_dir()))  # noqa: S606 - 開啟自己的資料夾
        return {"ok": True}
