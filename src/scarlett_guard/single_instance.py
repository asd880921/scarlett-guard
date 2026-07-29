"""單一實例控制。

這個程式常駐、註冊全域熱鍵、而且會重置 PnP 裝置 —— 跑兩份沒有任何好處，
只會有兩個系統匣圖示、兩個熱鍵監聽器搶同一組按鍵，以及兩邊同時對裝置
下重置指令的風險。

做法：
  * 具名 Mutex 判斷是否已有實例在跑。
  * 具名 Event 讓後啟動的那份「敲門」，請已在執行的那份把視窗叫出來，
    然後自己安靜退出 —— 使用者重複點捷徑時的預期行為是看到視窗，
    而不是看到一則錯誤訊息。

用 Local\\ 命名空間（同一登入工作階段共用），提權與未提權的行程都看得到
彼此，所以不會因為權限不同而各跑一份。
"""
from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

_ERROR_ALREADY_EXISTS = 183
_WAIT_OBJECT_0 = 0x00000000
_INFINITE = 0xFFFFFFFF

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CreateEventW.argtypes = [
    wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR
]
_kernel32.CreateEventW.restype = wintypes.HANDLE
_kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.OpenEventW.restype = wintypes.HANDLE
_kernel32.SetEvent.argtypes = [wintypes.HANDLE]
_kernel32.SetEvent.restype = wintypes.BOOL
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL

_EVENT_MODIFY_STATE = 0x0002


class SingleInstance:
    def __init__(self, name: str = "ScarlettGuard") -> None:
        self._mutex_name = f"Local\\{name}.Mutex"
        self._event_name = f"Local\\{name}.Show"
        self._mutex = None
        self._event = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.is_primary = False

    # ------------------------------------------------------------------
    def acquire(self) -> bool:
        """嘗試成為唯一實例。回傳 False 代表已經有一份在跑。"""
        try:
            handle = _kernel32.CreateMutexW(None, False, self._mutex_name)
            last_error = ctypes.get_last_error()
        except OSError:
            # 拿不到就別擋著使用者，寧可放行也不要整個開不起來
            self.is_primary = True
            return True

        if not handle:
            self.is_primary = True
            return True

        if last_error == _ERROR_ALREADY_EXISTS:
            _kernel32.CloseHandle(handle)
            self.is_primary = False
            return False

        self._mutex = handle
        self.is_primary = True
        return True

    def signal_existing(self) -> bool:
        """請已在執行的實例把視窗叫出來。"""
        handle = _kernel32.OpenEventW(_EVENT_MODIFY_STATE, False, self._event_name)
        if not handle:
            return False
        try:
            return bool(_kernel32.SetEvent(handle))
        finally:
            _kernel32.CloseHandle(handle)

    def listen(self, on_show: Callable[[], None]) -> None:
        """（主要實例）開始等待其他實例的敲門。"""
        if not self.is_primary or self._thread is not None:
            return
        self._event = _kernel32.CreateEventW(None, False, False, self._event_name)
        if not self._event:
            return

        def loop() -> None:
            while not self._stop.is_set():
                result = _kernel32.WaitForSingleObject(self._event, 1000)
                if self._stop.is_set():
                    return
                if result == _WAIT_OBJECT_0:
                    try:
                        on_show()
                    except Exception:
                        continue

        self._thread = threading.Thread(target=loop, name="single-instance", daemon=True)
        self._thread.start()

    def release(self) -> None:
        self._stop.set()
        if self._event:
            _kernel32.SetEvent(self._event)  # 讓等待中的執行緒立刻醒來
            _kernel32.CloseHandle(self._event)
            self._event = None
        if self._mutex:
            _kernel32.CloseHandle(self._mutex)
            self._mutex = None
