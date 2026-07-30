"""系統匣圖示。

視窗收起來之後，這就是唯一的入口，所以驅動模式切換必須在選單第一層、一步可達。

## 為什麼選單項目沒有勾號、也不會變灰

Windows 的托盤選單是**一次性快照**：pystray 只在啟動時、以及每次點擊選單項目之後
重建 HMENU（見 `pystray/_base.py` 的 `update_menu`，它自己的說明就寫著
"not all supported platforms allow the menu to be generated when shown"）。
這代表 `checked` / `enabled` 這類動態狀態在外部條件改變時**不會跟著更新** ——
從托盤觸發一次切換，選單就會在 `busy=True` 的那一刻被重建並凍在停用狀態，
之後永遠不會恢復。

要維持它們正確就得從背景執行緒呼叫 `update_menu()` 重建 Win32 選單，
那是在一個已經很脆弱的表面上再加一個跨執行緒當機來源。

所以這裡的選擇是**不要有會過期的狀態**：
  - 項目一律可點，標籤自己講清楚會發生什麼（「切換到日常模式」而不是「日常模式」）
  - 目前處於哪個模式改用 tooltip 呈現 —— 滑鼠移上去就看得到，而且永遠是即時的
  - 不適用的動作由 service 層擋下並發系統通知，而不是先假裝停用

結果是：不會再有「明明可以用卻反白」，也不會有「已經失效卻還亮著」。
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


def _make_icon(state: str, size: int = 64) -> Image.Image:
    """畫一個帶狀態小圓點的圓角方塊。

    座標全部按 size 等比換算，所以每個尺寸都是**原生繪製**的。
    先畫小張再放大會糊掉 —— 這在 README 裡放大顯示時特別明顯。
    """
    k = size / 64.0
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (4 * k, 4 * k, size - 4 * k, size - 4 * k),
        radius=14 * k,
        fill=(28, 28, 30, 255),
    )
    # 一個代表訊號的正弦狀折線
    points = [(16, 40), (24, 24), (32, 44), (40, 22), (48, 36)]
    draw.line(
        [(x * k, y * k) for x, y in points],
        fill=(235, 235, 245, 235),
        width=max(1, round(4 * k)),
        joint="curve",
    )

    colour = _COLORS.get(state, _COLORS["idle"])
    draw.ellipse(
        (size - 26 * k, size - 26 * k, size - 6 * k, size - 6 * k),
        fill=(*colour, 255),
    )
    return image


class Tray:
    def __init__(
        self,
        on_reset: Callable[[], None],
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        on_switch_mode: Callable[[str], None] | None = None,
    ) -> None:
        self._on_reset = on_reset
        self._on_show = on_show
        self._on_quit = on_quit
        self._on_switch_mode = on_switch_mode
        self._icon = None
        self._thread: threading.Thread | None = None
        self._state = "ok"
        self._title = t("tray.title")

    @property
    def available(self) -> bool:
        return pystray is not None

    def start(self) -> None:
        if pystray is None:
            return
        menu = pystray.Menu(
            # 驅動模式是主要功能，放最前面且不收進子選單 —— 從托盤操作時
            # 少一層就是少一次滑動。標籤寫「切換到…」，不必靠勾號就知道會發生什麼。
            pystray.MenuItem(t("tray.mode.daily"), lambda *_a: self._switch_mode("daily")),
            pystray.MenuItem(t("tray.mode.asio"), lambda *_a: self._switch_mode("asio")),
            # 重置刻意「不」設為 default：預設動作會綁到左鍵雙擊，
            # 而重置會中斷音訊數秒，誤觸的代價太高。
            # 雙擊留給開啟視窗這個無害的動作，快速重置則交給全域熱鍵。
            pystray.MenuItem(t("tray.reset"), self._reset),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray.open"), self._show, default=True),
            pystray.MenuItem(t("tray.quit"), self._quit),
        )
        self._icon = pystray.Icon(
            "scarlett_guard", _make_icon(self._state), self._title, menu
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

    def set_title(self, title: str) -> None:
        """tooltip。目前的驅動模式顯示在這裡 —— 選單沒有勾號，這是唯一的狀態指示。"""
        if title == self._title or self._icon is None:
            return
        self._title = title
        try:
            self._icon.title = title
        except Exception:
            pass

    def notify(self, title: str, message: str = "") -> None:
        if self._icon is None:
            return
        # 本文絕不能是空字串：pystray 的「移除通知」就是送 szInfo=''，
        # 傳空的等於叫它把通知收掉，結果是完全不顯示。
        body = message.strip() or title
        if not body:
            return
        try:
            self._icon.notify(body, title)
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
    #
    # 全部都必須立刻返回：這些跑在 pystray 的 UI 執行緒上，
    # 在這裡做任何阻塞的事都會讓整個系統匣沒有回應。
    def _reset(self, *_args) -> None:
        threading.Thread(target=self._on_reset, daemon=True).start()

    def _switch_mode(self, mode: str) -> None:
        if self._on_switch_mode is None:
            return
        threading.Thread(target=self._on_switch_mode, args=(mode,), daemon=True).start()

    def _show(self, *_args) -> None:
        self._on_show()

    def _quit(self, *_args) -> None:
        self._on_quit()
