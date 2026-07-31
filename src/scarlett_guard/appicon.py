"""從執行檔取出圖示與顯示名稱。

音量混音器裡如果只有文字，使用者其實分不出「wallpaper64.exe」是什麼東西 ——
圖示才是應用程式真正的識別。Windows 自己的混音器也是這樣做的。

兩件事都很貴（開檔、讀資源、GDI 繪製），但同一個執行檔的答案永遠一樣，
所以整支模組只在乎一件事：**用路徑當鍵快取住**。列表每半秒刷新一次，
沒有快取的話每次都要重新解一輪圖示資源。
"""
from __future__ import annotations

import base64
import ctypes
import io
import os
import threading
from ctypes import byref, c_int, c_void_p, wintypes

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32
_shell32 = ctypes.windll.shell32
_version = ctypes.windll.version
_kernel32 = ctypes.windll.kernel32

# 32px：混音器列高只有這麼多，取更大的只是浪費解碼時間與傳輸量
ICON_SIZE = 32

_DI_NORMAL = 0x0003
_BI_RGB = 0
_DIB_RGB_COLORS = 0

_lock = threading.Lock()
_icon_cache: dict[str, str] = {}
_name_cache: dict[str, str] = {}


def _declare() -> None:
    """替所有會回傳控制代碼的 API 宣告型別。

    **不能省。** ctypes 的預設回傳型別是 32 位元的 int，在 64 位元行程裡會把
    HDC / HBITMAP 這類指標攔腰截斷 —— 拿到的是一個看起來有效、實際上指向別處的
    數字，後續呼叫要嘛安靜失敗、要嘛破壞不屬於自己的記憶體。
    """
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    _gdi32.CreateCompatibleDC.restype = wintypes.HDC
    _gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    _gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    _gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC, c_void_p, ctypes.c_uint, ctypes.POINTER(c_void_p),
        wintypes.HANDLE, wintypes.DWORD,
    ]
    _gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
    _gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
    _gdi32.SelectObject.restype = wintypes.HGDIOBJ
    _gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    _gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    _gdi32.DeleteDC.argtypes = [wintypes.HDC]

    _user32.DrawIconEx.argtypes = [
        wintypes.HDC, c_int, c_int, wintypes.HICON, c_int, c_int,
        ctypes.c_uint, wintypes.HBRUSH, ctypes.c_uint,
    ]
    _user32.FillRect.argtypes = [wintypes.HDC, c_void_p, wintypes.HBRUSH]
    _user32.DestroyIcon.argtypes = [wintypes.HICON]

    _shell32.ExtractIconExW.restype = ctypes.c_uint
    _shell32.SHDefExtractIconW.restype = ctypes.c_long


_declare()


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


# --------------------------------------------------------------------------
# 行程 → 執行檔路徑
# --------------------------------------------------------------------------

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def process_path(pid: int) -> str:
    """行程的完整執行檔路徑。

    刻意用 PROCESS_QUERY_LIMITED_INFORMATION 而不是 QUERY_INFORMATION：
    前者不需要提權就能對大部分行程成功，混音器在未提權時也該看得到圖示。
    """
    if not pid:
        return ""
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buf, byref(size)):
            return ""
        return buf.value or ""
    finally:
        _kernel32.CloseHandle(handle)


# --------------------------------------------------------------------------
# 顯示名稱
# --------------------------------------------------------------------------

def file_description(path: str) -> str:
    """版本資源裡的 FileDescription，例如「遠端桌面連線」。

    這是 Windows 混音器顯示的那個名字。取不到就由呼叫端退回檔名 ——
    截圖裡的 `wallpaper64.exe` 就是這種沒有版本資源的情況。
    """
    if not path:
        return ""
    with _lock:
        if path in _name_cache:
            return _name_cache[path]
    value = _read_file_description(path)
    with _lock:
        _name_cache[path] = value
    return value


def _read_file_description(path: str) -> str:
    try:
        size = _version.GetFileVersionInfoSizeW(ctypes.c_wchar_p(path), None)
        if not size:
            return ""
        block = ctypes.create_string_buffer(size)
        if not _version.GetFileVersionInfoW(ctypes.c_wchar_p(path), 0, size, block):
            return ""

        # 先問這個檔案帶了哪些語言，再去對應的字串表取值 ——
        # 寫死 040904B0（美式英文）在中文版程式上會直接查不到。
        langs = c_void_p()
        length = ctypes.c_uint()
        if not _version.VerQueryValueW(
            block, ctypes.c_wchar_p(r"\VarFileInfo\Translation"), byref(langs), byref(length)
        ) or length.value < 4:
            return ""
        pair = ctypes.cast(langs, ctypes.POINTER(wintypes.WORD))
        candidates = [f"{pair[0]:04x}{pair[1]:04x}"]
        # 有些程式的翻譯表和實際存在的字串表對不上，補一個最常見的組合
        candidates.append(f"{pair[0]:04x}04b0")

        for code in candidates:
            value = c_void_p()
            if _version.VerQueryValueW(
                block,
                ctypes.c_wchar_p(rf"\StringFileInfo\{code}\FileDescription"),
                byref(value),
                byref(length),
            ) and length.value:
                text = ctypes.wstring_at(value, length.value).strip("\x00").strip()
                if text:
                    return text
    except Exception:
        return ""
    return ""


def display_name(path: str) -> str:
    """給使用者看的應用程式名稱：優先版本資源，退回檔名。"""
    if not path:
        return ""
    return file_description(path) or os.path.basename(path)


# --------------------------------------------------------------------------
# 圖示
# --------------------------------------------------------------------------

def icon_data_uri(path: str) -> str:
    """執行檔圖示的 PNG data URI；取不到回空字串（前端會退回預設字符）。"""
    if not path:
        return ""
    with _lock:
        if path in _icon_cache:
            return _icon_cache[path]
    try:
        value = _extract_icon(path)
    except Exception:
        value = ""
    with _lock:
        _icon_cache[path] = value
    return value


def _extract_icon(path: str) -> str:
    hicon = _load_hicon(path)
    if not hicon:
        return ""
    try:
        png = _hicon_to_png(hicon, ICON_SIZE)
    finally:
        _user32.DestroyIcon(hicon)
    if not png:
        return ""
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _load_hicon(path: str) -> int:
    """取出指定尺寸的圖示。

    先用 SHDefExtractIconW：它會挑最接近要求尺寸的那一張，必要時還會縮放，
    ExtractIconEx 只給固定的大／小兩種。取不到才退回 ExtractIconEx。
    """
    large = wintypes.HICON()
    try:
        hr = _shell32.SHDefExtractIconW(
            ctypes.c_wchar_p(path), 0, 0, byref(large), None, ICON_SIZE
        )
        if hr == 0 and large.value:
            return large.value
    except Exception:
        pass

    large = wintypes.HICON()
    small = wintypes.HICON()
    try:
        if _shell32.ExtractIconExW(ctypes.c_wchar_p(path), 0, byref(large), byref(small), 1):
            if large.value:
                if small.value:
                    _user32.DestroyIcon(small)
                return large.value
            if small.value:
                return small.value
    except Exception:
        pass
    return 0


def _hicon_to_png(hicon: int, size: int) -> bytes:
    """HICON → 帶 alpha 的 PNG。

    畫兩次而不是一次：把同一個圖示分別畫在全黑與全白底上，再從兩者的差值反推
    alpha。直接畫在 32bpp DIB 上讀 alpha 通道看似更省事，但只對 32bpp 的現代
    圖示有效 —— 舊式的「色彩＋遮罩」圖示畫完整片 alpha 都是 0，結果是一張全透明
    的圖。兩次繪製對兩種圖示都成立，而且不必自己處理遮罩點陣圖。
    """
    from PIL import Image  # 延後匯入：只有真的要畫圖示時才需要

    on_black = _draw_icon(hicon, size, 0x000000)
    on_white = _draw_icon(hicon, size, 0xFFFFFF)
    if on_black is None or on_white is None:
        return b""

    out = bytearray(size * size * 4)
    for i in range(0, len(out), 4):
        # DIB 是 BGRA 順序；用綠色通道推 alpha 就夠（三個通道的差值一致）
        cb, cw = on_black[i + 1], on_white[i + 1]
        alpha = 255 - (cw - cb)
        if alpha <= 0:
            continue  # 完全透明，維持 0
        if alpha > 255:
            alpha = 255
        for ch in range(3):
            # 畫在黑底上得到的是 alpha 預乘後的值，除回去才是原色
            value = on_black[i + (2 - ch)] * 255 // alpha
            out[i + ch] = 255 if value > 255 else value
        out[i + 3] = alpha

    image = Image.frombuffer("RGBA", (size, size), bytes(out), "raw", "RGBA", 0, 1)
    if image.getbbox() is None:
        return b""  # 整張空的，當作沒有圖示
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _draw_icon(hicon: int, size: int, background: int) -> bytes | None:
    """把圖示畫在指定的純色底上，回傳 BGRA 原始位元組。"""
    hdc = _gdi32.CreateCompatibleDC(None)
    if not hdc:
        return None
    bitmap = None
    try:
        info = _BITMAPINFO()
        header = info.bmiHeader
        header.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        header.biWidth = size
        header.biHeight = -size          # 負值 = 由上而下，省掉自己翻轉
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = _BI_RGB

        bits = c_void_p()
        bitmap = _gdi32.CreateDIBSection(
            hdc, byref(info), _DIB_RGB_COLORS, byref(bits), None, 0
        )
        if not bitmap or not bits:
            return None
        _gdi32.SelectObject(hdc, bitmap)

        brush = _gdi32.CreateSolidBrush(
            # GDI 的 COLORREF 是 BGR；只用純黑與純白，兩邊等價
            ((background & 0xFF) << 16) | (background & 0xFF00) | ((background >> 16) & 0xFF)
        )
        rect = wintypes.RECT(0, 0, size, size)
        _user32.FillRect(hdc, byref(rect), brush)
        _gdi32.DeleteObject(brush)

        if not _user32.DrawIconEx(hdc, 0, 0, hicon, size, size, 0, None, _DI_NORMAL):
            return None
        _gdi32.GdiFlush()
        return ctypes.string_at(bits, size * size * 4)
    finally:
        if bitmap:
            _gdi32.DeleteObject(bitmap)
        _gdi32.DeleteDC(hdc)
