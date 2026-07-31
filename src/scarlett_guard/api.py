"""pywebview 的 JS ↔ Python 橋接層。

前端所有呼叫都經過這裡；每個方法都保證回傳可序列化的 dict／list，
並且不拋例外到 JS 端（否則前端只會拿到一個沒有訊息的 rejection）。
"""
from __future__ import annotations

import functools
import traceback
from typing import Any, Callable

from . import audio, device, elevation, hotkey, i18n, updater
from .paths import HISTORY_PATH, CONFIG_PATH, app_version, data_dir
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
    """暴露給前端的橋接物件。

    重要：所有內部狀態都必須用底線前綴。pywebview 在建立 JS 橋接時會走訪
    這個物件的「公開」屬性，一旦把 pywebview 的 Window 或其他大型物件掛成
    公開屬性，它會遞迴進 WebView2 的 COM 物件圖並炸掉：

        [pywebview] Error while processing window.native.AccessibilityObject
        .Bounds.Empty.Empty…: maximum recursion depth exceeded

    那次失敗會讓整個 window.pywebview.api 不被注入 —— 前端拿不到任何資料，
    而且完全沒有錯誤訊息，畫面只會停在初始文字。
    """

    def __init__(self, service: GuardService) -> None:
        self._service = service
        self._on_hide: Callable[[], None] | None = None
        self._on_quit: Callable[[], None] | None = None

    def bind_window(
        self,
        window: Any,
        on_hide: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        # 刻意不保留 window 的參照 —— 見上面的類別說明
        del window
        self._on_hide = on_hide
        self._on_quit = on_quit

    # ------------------------------------------------------------------
    # 狀態查詢
    # ------------------------------------------------------------------
    @_safe
    def bootstrap(self) -> dict[str, Any]:
        """開頁時一次拿齊「立即可得」的資料。

        刻意**不**包含裝置狀態與驅動模式：那需要跑 PowerShell，要花兩三秒。
        把它放進來會讓設定、紀錄、路徑這些本來就在記憶體裡的資料一起被卡住，
        整個 UI 空白好幾秒。前端拿到這包之後再自己去要。
        """
        return {
            "ok": True,
            "device_pending": True,
            "version": app_version(),
            # 檢查可能在 UI 就緒前就跑完了，那樣就不會有 update 事件推過來，
            # 所以這裡也帶一份目前狀態
            "update": self._service.updates.result,
            "config": self._service.config.as_dict(),
            "history": self._service.history.recent(30),
            "autostart": self._service.autostart_state(),
            "hotkey_active": self._service.hotkeys.active,
            "hotkey_error": self._service.hotkeys.error,
            "elevated": device.is_elevated(),
            "paths": {
                "config": str(CONFIG_PATH),
                "history": str(HISTORY_PATH),
                "data_dir": str(data_dir()),
            },
        }

    @_safe
    def device_status(self, force: bool = False) -> dict[str, Any]:
        return {"ok": True, "device": self._service.snapshot(force=force)}

    @_safe
    def driver_mode(self, force: bool = False) -> dict[str, Any]:
        """目前的驅動模式。和 device_status 一樣需要跑 PowerShell，不放進 bootstrap。"""
        return {"ok": True, "driver_mode": self._service.driver_mode(force=force)}

    @_safe
    def history(self, limit: int = 30) -> dict[str, Any]:
        return {"ok": True, "history": self._service.history.recent(int(limit))}

    # ------------------------------------------------------------------
    # 動作
    # ------------------------------------------------------------------
    @_safe
    def switch_driver_mode(self, mode: str) -> dict[str, Any]:
        return self._service.switch_driver_mode(str(mode or ""), "manual")

    @_safe
    def repair_driver_binding(self) -> dict[str, Any]:
        return self._service.repair_driver_binding()

    @_safe
    def reset(self, source: str = "manual") -> dict[str, Any]:
        return self._service.reset(source or "manual")

    @_safe
    def update_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._service.update_settings(values or {})

    @_safe
    def reset_settings(self) -> dict[str, Any]:
        self._service.config.reset_to_defaults()
        cfg = self._service.config.as_dict()
        i18n.set_language(cfg["language"])
        self._service.hotkeys.apply(cfg["hotkey"], cfg["hotkey_enabled"])
        return {"ok": True, "config": cfg, "messages": [i18n.t("cfg.restored")]}

    @_safe
    def validate_hotkey(self, combo: str) -> dict[str, Any]:
        ok, message = hotkey.validate(combo)
        return {"ok": ok, "message": message}

    @_safe
    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        return self._service.set_autostart(bool(enabled))

    @_safe
    def ghosts(self) -> dict[str, Any]:
        return {"ok": True, "ghosts": self._service.ghosts()}

    @_safe
    def remove_ghosts(self, instance_ids: list[str]) -> dict[str, Any]:
        return self._service.remove_ghosts(list(instance_ids or []))

    @_safe
    def clear_history(self) -> dict[str, Any]:
        self._service.history.clear()
        return {"ok": True}

    # ------------------------------------------------------------------
    # 系統音效
    # ------------------------------------------------------------------
    # 這一整區都**不需要**提權，也不碰 PowerShell —— 走的是 Core Audio COM，
    # 一次查詢十幾毫秒。所以它可以被高頻輪詢，和上面那些動輒兩秒的查詢是兩回事。
    @_safe
    def audio_overview(self) -> dict[str, Any]:
        return {"ok": True, "audio": audio.overview()}

    @_safe
    def audio_levels(self) -> dict[str, Any]:
        """輪詢用：只有數值，不含名稱與圖示。"""
        return {"ok": True, "levels": audio.levels()}

    @_safe
    def audio_peaks(self) -> dict[str, Any]:
        """音量表專用的高頻路徑，只有兩個數字。"""
        return {"ok": True, "peaks": audio.peaks()}

    @_safe
    def set_output_volume(self, percent: int) -> dict[str, Any]:
        audio.set_endpoint_volume("render", int(percent))
        return {"ok": True}

    @_safe
    def set_output_mute(self, muted: bool) -> dict[str, Any]:
        audio.set_endpoint_mute("render", bool(muted))
        return {"ok": True}

    @_safe
    def set_input_volume(self, percent: int) -> dict[str, Any]:
        audio.set_endpoint_volume("capture", int(percent))
        return {"ok": True}

    @_safe
    def set_input_mute(self, muted: bool) -> dict[str, Any]:
        audio.set_endpoint_mute("capture", bool(muted))
        return {"ok": True}

    @_safe
    def set_app_volume(self, key: str, percent: int) -> dict[str, Any]:
        audio.set_session_volume(str(key), int(percent))
        return {"ok": True}

    @_safe
    def set_app_mute(self, key: str, muted: bool) -> dict[str, Any]:
        audio.set_session_mute(str(key), bool(muted))
        return {"ok": True}

    @_safe
    def set_default_audio_device(self, device_id: str, flow: str = "render") -> dict[str, Any]:
        audio.set_default_device(str(device_id), str(flow or "render"))
        record = self._service.history.log(
            "audio_default", flow=str(flow or "render"), device=str(device_id)[-60:]
        )
        self._service.emit_history(record)
        return {"ok": True}

    @_safe
    def reset_app_volumes(self) -> dict[str, Any]:
        count = audio.reset_sessions()
        record = self._service.history.log("audio_reset", count=count)
        self._service.emit_history(record)
        return {"ok": True, "count": count}

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
    def log_js_error(self, where: str, detail: str) -> dict[str, Any]:
        """前端例外回報。

        沒有這條路徑的話，UI 的 JS 錯誤只會讓畫面安靜地半殘，
        從後端完全看不出任何異常。
        """
        record = self._service.history.log(
            "js_error", where=str(where)[:120], detail=str(detail)[:2000]
        )
        return {"ok": True, "logged": record["iso"]}

    @_safe
    def open_release_page(self, url: str = "") -> dict[str, Any]:
        return {"ok": updater.open_release_page(str(url or ""))}

    @_safe
    def open_data_folder(self) -> dict[str, Any]:
        import os

        os.startfile(str(data_dir()))  # noqa: S606 - 開啟自己的資料夾
        return {"ok": True}
