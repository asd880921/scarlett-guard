"""程式進入點：組裝服務、系統匣與視窗。"""
from __future__ import annotations

import argparse
import json
import threading
import time
from typing import Any

import webview

from . import elevation
from .api import Api
from .i18n import t
from .paths import ui_dir
from .service import GuardService
from .single_instance import SingleInstance
from .tray import Tray

_WINDOW_TITLE = "Scarlett Guard"


class Application:
    def __init__(self, start_hidden: bool = False, instance: SingleInstance | None = None) -> None:
        self.instance = instance
        self.service = GuardService()
        self.api = Api(self.service)
        self.window: Any = None
        self.tray: Tray | None = None
        self._ui_ready = threading.Event()
        self._quitting = False
        self._start_hidden = start_hidden

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.service.start()
        self.service.subscribe(self._on_service_event)

        self.window = webview.create_window(
            _WINDOW_TITLE,
            str(ui_dir() / "index.html"),
            js_api=self.api,
            width=1080,
            height=760,
            min_size=(880, 620),
            background_color="#0B0B0F",
            hidden=self._start_hidden,
            easy_drag=False,
        )
        self.api.bind_window(self.window, on_hide=self._hide_window, on_quit=self.quit)
        self.window.events.closing += self._on_closing

        self.tray = Tray(
            on_reset=lambda: self.service.reset("tray"),
            on_show=self._show_window,
            on_toggle_monitor=self._toggle_monitor,
            on_quit=self.quit,
            monitor_enabled=lambda: bool(self.service.config.get("monitor_enabled")),
            on_switch_mode=lambda mode: self.service.switch_driver_mode(mode, "tray"),
            # 用快取的探測結果 —— 選單每次開啟都會呼叫 checked，
            # 在那裡跑 PowerShell 會讓選單卡好幾秒才展開
            current_mode=lambda: str(self.service.driver_mode().get("mode", "")),
        )
        self.tray.start()

        # 之後有人再點捷徑時，把這扇視窗叫出來，而不是開第二份
        if self.instance is not None:
            self.instance.listen(self._show_window)

        threading.Thread(target=self._poll_loop, name="poll", daemon=True).start()

        webview.start(self._on_started, debug=False)
        self._teardown()

    # ------------------------------------------------------------------
    def _on_started(self) -> None:
        self._ui_ready.set()

    def _on_closing(self) -> bool:
        """關閉視窗時收進系統匣，而不是直接結束 —— 這程式的價值在於常駐。"""
        if self._quitting:
            return True
        if self.service.config.get("close_to_tray") and self.tray and self.tray.available:
            self._hide_window()
            return False
        self.quit()
        return True

    def _hide_window(self) -> None:
        try:
            if self.window is not None:
                self.window.hide()
        except Exception:
            pass

    def _show_window(self) -> None:
        try:
            if self.window is not None:
                self.window.show()
                self.window.restore()
        except Exception:
            pass

    def _toggle_monitor(self, enabled: bool) -> None:
        result = self.service.set_monitor_enabled(enabled)
        self._push("monitor", result.get("state", {}))
        self._push("settings", self.service.config.as_dict())

    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        try:
            self.service.shutdown()
        except Exception:
            pass
        if self.instance is not None:
            self.instance.release()
        if self.tray is not None:
            self.tray.stop()
        try:
            if self.window is not None:
                self.window.destroy()
        except Exception:
            pass

    def _teardown(self) -> None:
        if not self._quitting:
            self.quit()

    # ------------------------------------------------------------------
    # 事件推送
    # ------------------------------------------------------------------
    def _on_service_event(self, channel: str, payload: dict[str, Any]) -> None:
        self._push(channel, payload)

        if channel == "busy" and self.tray is not None:
            self.tray.set_state("busy" if payload.get("busy") else "ok")

        if channel == "anomaly" and self.tray is not None:
            self.tray.set_state("error")
            if self.service.config.get("notify_on_reset"):
                self.tray.notify(t("tray.anomaly"), str(payload.get("label", "")))

        if channel == "history" and self.tray is not None:
            event = str(payload.get("event", ""))
            if event.startswith("reset_"):
                ok = bool(payload.get("ok"))
                self.tray.set_state("ok" if ok else "error")
                if self.service.config.get("notify_on_reset"):
                    self.tray.notify(
                        t("tray.title"),
                        t("tray.reset.ok")
                        if ok
                        else t("tray.reset.fail", message=payload.get("message", "")),
                    )
            elif event.startswith("mode_"):
                # 從系統匣切換時視窗可能是關著的，通知是唯一的結果回饋 ——
                # 而且切換失敗可能讓系統完全沒有音訊裝置，一定要說出來
                ok = bool(payload.get("ok"))
                self.tray.set_state("ok" if ok else "error")
                self.tray.notify(t("tray.title"), str(payload.get("message", "")))

    def _push(self, channel: str, payload: dict[str, Any]) -> None:
        if not self._ui_ready.is_set() or self.window is None:
            return
        try:
            data = json.dumps({"channel": channel, "payload": payload}, ensure_ascii=False)
            self.window.evaluate_js(
                f"window.SG && window.SG.onEvent && window.SG.onEvent({data})"
            )
        except Exception:
            # 視窗關閉中或 JS 尚未載入完成，忽略即可
            pass

    def _poll_loop(self) -> None:
        """定期把即時資料推給 UI。

        監聽儀表需要高頻更新（10Hz），裝置狀態則因為 PowerShell 查詢很慢
        而降到 5 秒一次。
        """
        tick = 0
        while not self._quitting:
            time.sleep(0.1)
            if not self._ui_ready.is_set():
                continue
            tick += 1
            try:
                if self.service.monitor.running:
                    self._push("monitor", self.service.monitor_state())
                if tick % 50 == 0:
                    self._push("device", self.service.snapshot())
                    self._push("stats", self.service.history.stats())
                # 驅動模式幾乎不會自己改變，所以查得比裝置狀態更疏。
                # 但一定要定期查：系統匣選單的勾號讀的是這份快取，
                # 沒有人先把它熱起來的話，第一次展開選單會卡兩三秒。
                if tick % 300 == 0:
                    self._push("driver_mode", self.service.driver_mode())
            except Exception:
                continue


def main() -> None:
    parser = argparse.ArgumentParser(prog="scarlett-guard", description="Scarlett Guard")
    parser.add_argument(
        "--tray", action="store_true", help="啟動時直接收進系統匣，不顯示視窗"
    )
    parser.add_argument(
        "--elevated", action="store_true", help="內部使用：標記這是提權後重啟的行程"
    )
    args = parser.parse_args()

    # 已經有一份在跑就把它的視窗叫出來，自己安靜退出。
    # 使用者重複點捷徑時想看到的是視窗，不是錯誤訊息。
    instance = SingleInstance()
    if not instance.acquire():
        instance.signal_existing()
        return

    app = Application(start_hidden=args.tray or False, instance=instance)
    try:
        app.run()
    finally:
        instance.release()


__all__ = ["Application", "main", "elevation"]
