"""系統匣圖示。

視窗收起來之後，這就是使用者唯一的入口，所以最重要的動作（立即重置）
必須在選單第一項、一步可達。
"""
from __future__ import annotations

import threading
from typing import Callable

from PIL import Image, ImageDraw

from .i18n import t

try:
    import pystray

    _PYSTRAY_ERROR = ""
except Exception as exc:  # pragma: no cover
    pystray = None  # type: ignore[assignment]
    _PYSTRAY_ERROR = str(exc)


# 狀態色 —— 對應 UI 裡的同一組語意色
_COLORS = {
    "ok": (48, 209, 88),
    "busy": (255, 159, 10),
    "error": (255, 69, 58),
    "idle": (142, 142, 147),
}


def _make_icon(state: str) -> Image.Image:
    """畫一個帶狀態小圓點的圓角方塊。"""
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((4, 4, size - 4, size - 4), radius=14, fill=(28, 28, 30, 255))
    # 一個代表訊號的正弦狀折線
    points = [(16, 40), (24, 24), (32, 44), (40, 22), (48, 36)]
    draw.line(points, fill=(235, 235, 245, 235), width=4, joint="curve")

    colour = _COLORS.get(state, _COLORS["idle"])
    draw.ellipse((size - 26, size - 26, size - 6, size - 6), fill=(*colour, 255))
    return image


class Tray:
    def __init__(
        self,
        on_reset: Callable[[], None],
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        on_switch_mode: Callable[[str], None] | None = None,
        current_mode: Callable[[], str] | None = None,
    ) -> None:
        self._on_reset = on_reset
        self._on_show = on_show
        self._on_quit = on_quit
        self._on_switch_mode = on_switch_mode
        self._current_mode = current_mode
        self._icon = None
        self._thread: threading.Thread | None = None
        self._state = "ok"

    @property
    def available(self) -> bool:
        return pystray is not None

    def start(self) -> None:
        if pystray is None:
            return
        menu = pystray.Menu(
            # 驅動模式是主要功能，放第一項。做成子選單而不是攤平：
            # 切換要十幾秒且會中斷音訊，多一層可以避免誤點。
            pystray.MenuItem(t("tray.mode"), self._mode_menu()),
            # 重置刻意「不」設為 default：預設動作會綁到左鍵雙擊，
            # 而重置會中斷音訊數秒，誤觸的代價太高。
            # 雙擊留給開啟視窗這個無害的動作，快速重置則交給全域熱鍵。
            pystray.MenuItem(t("tray.reset"), self._reset),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray.open"), self._show, default=True),
            pystray.MenuItem(t("tray.quit"), self._quit),
        )
        self._icon = pystray.Icon(
            "scarlett_guard", _make_icon(self._state), "Scarlett Guard", menu
        )
        self._thread = threading.Thread(target=self._icon.run, name="tray", daemon=True)
        self._thread.start()

    def set_state(self, state: str) -> None:
        if state == self._state or self._icon is None:
            return
        self._state = state
        try:
            self._icon.icon = _make_icon(state)
        except Exception:
            pass

    def notify(self, title: str, message: str) -> None:
        if self._icon is None:
            return
        try:
            self._icon.notify(message, title)
        except Exception:
            # 部分 Windows 設定下（例如關閉通知）會丟例外，不該影響主流程
            pass

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None

    # --- pystray 回呼 ---
    def _reset(self, *_args) -> None:
        threading.Thread(target=self._on_reset, daemon=True).start()

    def _show(self, *_args) -> None:
        self._on_show()

    def _mode_menu(self):
        """驅動模式子選單。勾號反映目前實際綁定的驅動。"""
        def item(mode: str, label_key: str):
            return pystray.MenuItem(
                t(label_key),
                lambda *_a: self._switch_mode(mode),
                checked=lambda _i, m=mode: (self._current_mode or (lambda: ""))() == m,
                radio=True,
            )

        return pystray.Menu(item("daily", "mode.daily"), item("asio", "mode.asio"))

    def _switch_mode(self, mode: str) -> None:
        if self._on_switch_mode is None:
            return
        # 切換是阻塞式的（十幾秒），絕不能在 pystray 的選單執行緒上跑，
        # 否則整個系統匣選單會凍住
        threading.Thread(target=self._on_switch_mode, args=(mode,), daemon=True).start()

    def _quit(self, *_args) -> None:
        self._on_quit()
