"""全域熱鍵。

在提權的行程裡註冊低階鍵盤 hook，任何前景視窗（含全螢幕 DAW）按下都收得到。
"""
from __future__ import annotations

import threading
from typing import Callable

from .i18n import t

try:
    from pynput import keyboard

    _PYNPUT_ERROR = ""
except Exception as exc:  # pragma: no cover
    keyboard = None  # type: ignore[assignment]
    _PYNPUT_ERROR = str(exc)


class HotkeyManager:
    def __init__(self, on_trigger: Callable[[], None]) -> None:
        self._on_trigger = on_trigger
        self._listener = None
        self._lock = threading.Lock()
        self._combo = ""
        self._error = ""

    @property
    def active(self) -> bool:
        return self._listener is not None

    @property
    def combo(self) -> str:
        return self._combo

    @property
    def error(self) -> str:
        return self._error

    def apply(self, combo: str, enabled: bool) -> tuple[bool, str]:
        self.stop()
        if not enabled:
            return True, t("hk.disabled")
        if keyboard is None:
            self._error = t("hk.nopynput", error=_PYNPUT_ERROR)
            return False, self._error
        combo = (combo or "").strip()
        if not combo:
            self._error = t("hk.empty")
            return False, self._error

        with self._lock:
            try:
                listener = keyboard.GlobalHotKeys({combo: self._fire})
                listener.daemon = True
                listener.start()
            except Exception as exc:
                self._error = t("hk.failed", error=exc)
                return False, self._error
            self._listener = listener
            self._combo = combo
            self._error = ""
        return True, t("hk.registered", combo=combo)

    def stop(self) -> None:
        with self._lock:
            listener = self._listener
            self._listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def _fire(self) -> None:
        # 在自己的執行緒裡跑，避免卡住鍵盤 hook —— 卡住會讓整台機器的輸入延遲
        threading.Thread(target=self._on_trigger, daemon=True).start()


def validate(combo: str) -> tuple[bool, str]:
    """在真正註冊前先驗證組合字串是否合法。"""
    if keyboard is None:
        return False, t("hk.noload")
    try:
        keyboard.HotKey.parse(combo)
    except Exception as exc:
        return False, t("hk.invalid", error=exc)
    return True, t("hk.valid")
