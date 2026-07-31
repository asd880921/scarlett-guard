"""Windows Core Audio：系統輸出／輸入與個別應用程式的音量。

**為什麼要有這一頁。** 切換驅動模式會讓裝置重新列舉，Windows 把它當成一台
新裝置，於是音量、靜音、預設裝置全部回到出廠值。使用者原本得自己去
「設定 → 系統 → 音效 → 音量混音器」把每個應用程式重調一次 —— 這一整套
現在做在應用程式裡。

**為什麼是手寫 ctypes 而不是 pycaw。** pycaw 要拉進 comtypes，而這個專案的
PyInstaller 設定是調過的（見 scarlett_guard.spec），多一個會在匯入期動態產生
模組的套件就多一種打包後才會炸的失敗方式。這裡需要的介面就那五、六個，
而且 vtable 佈局是公開且穩定的 API，直接宣告反而更可控。

**執行緒。** 所有呼叫都丟到一條自己持有 COM 的專屬執行緒上跑（見 _ComThread）。
pywebview 的 js_api 呼叫來自不特定的執行緒，在那裡各自 CoInitialize 會留下
無人收拾的 apartment；集中到單一執行緒同時也順便把存取序列化了。
"""
from __future__ import annotations

import ctypes
import queue
import threading
from ctypes import POINTER, byref, c_float, c_int, c_uint, c_ulong, c_void_p, c_wchar_p
from typing import Any, Callable

from . import appicon

_ole32 = ctypes.windll.ole32
_shlwapi = ctypes.windll.shlwapi

_ole32.CoTaskMemFree.argtypes = [c_void_p]
_ole32.CoCreateInstance.restype = ctypes.c_long

# --- 常數 -----------------------------------------------------------------
CLSCTX_ALL = 0x17
COINIT_MULTITHREADED = 0x0
DEVICE_STATE_ACTIVE = 0x1
STGM_READ = 0x0
VT_LPWSTR = 31

RENDER = 0          # EDataFlow::eRender —— 喇叭、耳機
CAPTURE = 1         # EDataFlow::eCapture —— 麥克風
_ROLES = (0, 1, 2)  # ERole::eConsole / eMultimedia / eCommunications

# AudioSessionState
_STATE_EXPIRED = 2

FLOWS = {"render": RENDER, "capture": CAPTURE}


class AudioError(RuntimeError):
    """任何一層 COM 呼叫失敗都收斂成這個。"""

    def __init__(self, where: str, hr: int) -> None:
        super().__init__(f"{where}: 0x{hr & 0xFFFFFFFF:08X}")
        self.hr = hr
        self.where = where


# --------------------------------------------------------------------------
# COM 基礎設施
# --------------------------------------------------------------------------

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(text: str) -> GUID:
    value = GUID()
    hr = _ole32.CLSIDFromString(c_wchar_p(text), byref(value))
    if hr < 0:
        raise AudioError(f"CLSIDFromString({text})", hr)
    return value


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", c_ulong)]


class _PropVariantValue(ctypes.Union):
    _fields_ = [("pwszVal", c_wchar_p), ("uintVal", c_ulong), ("raw", ctypes.c_byte * 16)]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ushort),
        ("wReserved2", ctypes.c_ushort),
        ("wReserved3", ctypes.c_ushort),
        ("value", _PropVariantValue),
    ]


CLSID_MMDeviceEnumerator = _guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator = _guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IAudioEndpointVolume = _guid("{5CDF2C82-841E-4546-9722-0CF74078229A}")
IID_IAudioSessionManager2 = _guid("{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}")
IID_IAudioSessionControl2 = _guid("{BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D}")
IID_ISimpleAudioVolume = _guid("{87CE5498-68D6-44E5-9215-6DA47EF883D8}")
IID_IAudioMeterInformation = _guid("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")

# 切換預設裝置沒有公開 API —— IPolicyConfig 是未公開介面，但從 Vista 起就是
# 所有第三方切換工具（nircmd、SoundVolumeView…）走的同一條路，介面本身沒有變過。
CLSID_PolicyConfigClient = _guid("{870AF99C-171D-4F9E-AF0D-E63DF40C2BC9}")
IID_IPolicyConfig = _guid("{F8679F50-850A-41CF-9C72-430F290290C8}")
IID_IPolicyConfigVista = _guid("{568B9108-44BF-40B4-9006-86AFE5B5A620}")

PKEY_Device_FriendlyName = (_guid("{A45C254E-DF1C-4EFD-8020-67D146A850E0}"), 14)

_PROTOTYPES: dict[tuple, Any] = {}


def _invoke(ptr: c_void_p, index: int, argtypes: tuple, *args: Any) -> int:
    """呼叫某個 COM 介面 vtable 上的第 index 個方法。"""
    key = (index, argtypes)
    proto = _PROTOTYPES.get(key)
    if proto is None:
        proto = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, *argtypes)
        _PROTOTYPES[key] = proto
    table = ctypes.cast(ptr, POINTER(POINTER(c_void_p))).contents
    return proto(table[index])(ptr, *args)


def _call(ptr: c_void_p, index: int, argtypes: tuple, *args: Any, where: str = "") -> int:
    hr = _invoke(ptr, index, argtypes, *args)
    if hr < 0:
        raise AudioError(where or f"vtbl[{index}]", hr)
    return hr


def _release(ptr: c_void_p | None) -> None:
    if ptr and getattr(ptr, "value", None):
        try:
            _invoke(ptr, 2, ())
        except Exception:
            pass


class _Scope:
    """把一次操作裡取得的介面指標全部記下來，離開時一起 Release。

    Core Audio 一次查詢會經手十幾個介面，手動配對 Release 遲早會漏掉一個；
    漏掉的後果是裝置永遠拆不乾淨（切換驅動模式時尤其明顯）。
    """

    def __init__(self) -> None:
        self._owned: list[c_void_p] = []

    def __enter__(self) -> "_Scope":
        return self

    def __exit__(self, *exc: Any) -> bool:
        for ptr in reversed(self._owned):
            _release(ptr)
        self._owned.clear()
        return False

    def own(self, ptr: c_void_p) -> c_void_p:
        self._owned.append(ptr)
        return ptr


class _ComThread:
    """所有 Core Audio 工作的唯一執行緒。"""

    def __init__(self) -> None:
        self._jobs: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def _ensure(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._loop, name="coreaudio", daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        _ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
        while True:
            func, done, box = self._jobs.get()
            try:
                box.append((True, func()))
            except Exception as exc:
                box.append((False, exc))
            finally:
                done.set()

    def run(self, func: Callable[[], Any], timeout: float = 10.0) -> Any:
        self._ensure()
        done = threading.Event()
        box: list[tuple[bool, Any]] = []
        self._jobs.put((func, done, box))
        if not done.wait(timeout):
            raise TimeoutError("Core Audio 呼叫逾時")
        ok, value = box[0]
        if not ok:
            raise value
        return value


_COM = _ComThread()


# --------------------------------------------------------------------------
# 介面取得
# --------------------------------------------------------------------------

# 只有 COM 執行緒會碰這兩個快取，所以不需要鎖。
# 存在的理由是量測過的：每次呼叫都重建 enumerator 與音量表介面要 5 毫秒，
# 而音量表是用十分之一秒的頻率在打的 —— 那等於白燒掉 5% 的 CPU。
# 重用之後同一條路徑大約 0.3 毫秒。
_shared_enum: c_void_p | None = None
_meter_cache: dict[int, tuple[str, c_void_p]] = {}


def _enumerator(scope: _Scope) -> c_void_p:
    """行程共用的 IMMDeviceEnumerator。

    刻意不交給 scope 管理 —— 它要活到行程結束。這是 Core Audio 的常規用法，
    微軟自己的範例也是開一個然後一直留著。
    """
    del scope  # 保留參數是為了讓呼叫端讀起來和其他 _xxx(scope, …) 一致
    global _shared_enum
    if _shared_enum is None:
        ptr = c_void_p()
        hr = _ole32.CoCreateInstance(
            byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL,
            byref(IID_IMMDeviceEnumerator), byref(ptr),
        )
        if hr < 0:
            raise AudioError("CoCreateInstance(MMDeviceEnumerator)", hr)
        _shared_enum = ptr
    return _shared_enum


def _query(scope: _Scope, ptr: c_void_p, iid: GUID, where: str) -> c_void_p:
    out = c_void_p()
    _call(ptr, 0, (POINTER(GUID), POINTER(c_void_p)), byref(iid), byref(out), where=where)
    return scope.own(out)


def _activate(scope: _Scope, device: c_void_p, iid: GUID, where: str) -> c_void_p:
    out = c_void_p()
    _call(
        device, 3, (POINTER(GUID), c_ulong, c_void_p, POINTER(c_void_p)),
        byref(iid), CLSCTX_ALL, None, byref(out), where=where,
    )
    return scope.own(out)


def _default_device(scope: _Scope, enumerator: c_void_p, flow: int) -> c_void_p | None:
    """預設裝置。沒有任何裝置時回 None 而不是拋例外 —— 沒插喇叭是常態，不是錯誤。"""
    out = c_void_p()
    hr = _invoke(
        enumerator, 4, (c_int, c_int, POINTER(c_void_p)), flow, 0, byref(out)
    )
    if hr < 0 or not out.value:
        return None
    return scope.own(out)


def _open_device(scope: _Scope, enumerator: c_void_p, device_id: str) -> c_void_p | None:
    out = c_void_p()
    hr = _invoke(enumerator, 5, (c_wchar_p, POINTER(c_void_p)), device_id, byref(out))
    if hr < 0 or not out.value:
        return None
    return scope.own(out)


def _device_id(device: c_void_p) -> str:
    out = c_wchar_p()
    _call(device, 5, (POINTER(c_wchar_p),), byref(out), where="IMMDevice::GetId")
    value = out.value or ""
    _ole32.CoTaskMemFree(out)
    return value


def _device_name(scope: _Scope, device: c_void_p) -> str:
    store = c_void_p()
    _call(
        device, 4, (c_ulong, POINTER(c_void_p)), STGM_READ, byref(store),
        where="IMMDevice::OpenPropertyStore",
    )
    scope.own(store)

    key = PROPERTYKEY()
    key.fmtid, key.pid = PKEY_Device_FriendlyName
    prop = PROPVARIANT()
    try:
        _call(
            store, 5, (POINTER(PROPERTYKEY), POINTER(PROPVARIANT)),
            byref(key), byref(prop), where="IPropertyStore::GetValue",
        )
        name = prop.value.pwszVal if prop.vt == VT_LPWSTR else ""
    finally:
        _ole32.PropVariantClear(byref(prop))
    return name or ""


# --------------------------------------------------------------------------
# 端點音量
# --------------------------------------------------------------------------

def _read_endpoint(scope: _Scope, device: c_void_p) -> dict[str, Any]:
    volume = _activate(scope, device, IID_IAudioEndpointVolume, "Activate(IAudioEndpointVolume)")
    level = c_float()
    muted = c_int()
    _call(volume, 9, (POINTER(c_float),), byref(level), where="GetMasterVolumeLevelScalar")
    _call(volume, 15, (POINTER(c_int),), byref(muted), where="GetMute")
    return {"volume": _percent(level.value), "muted": bool(muted.value)}


def _sync_meter(flow: int, device: c_void_p | None, device_id: str) -> None:
    """讓快取的音量表指向目前的預設裝置。

    使用者換過預設裝置之後，舊的介面通常還是有效的（那台裝置並沒有消失），
    只是量到的是別台的聲音 —— 不會報錯，畫面上的表卻永遠不動。
    所以比對裝置 ID，而不是等呼叫失敗才發現。
    """
    cached = _meter_cache.get(flow)
    if cached is not None and cached[0] == device_id:
        return
    _drop_meter(flow)
    if device is None or not device_id:
        return
    ptr = c_void_p()
    hr = _invoke(
        device, 3, (POINTER(GUID), c_ulong, c_void_p, POINTER(c_void_p)),
        byref(IID_IAudioMeterInformation), CLSCTX_ALL, None, byref(ptr),
    )
    if hr >= 0 and ptr.value:
        _meter_cache[flow] = (device_id, ptr)


def _drop_meter(flow: int) -> None:
    entry = _meter_cache.pop(flow, None)
    if entry is not None:
        _release(entry[1])


def _cached_peak(flow: int) -> float:
    """讀快取起來的音量表。取不到就當作 0 —— 這只是裝飾，不值得讓整頁失敗。"""
    entry = _meter_cache.get(flow)
    if entry is None:
        return 0.0
    value = c_float()
    if _invoke(entry[1], 3, (POINTER(c_float),), byref(value)) < 0:
        # 裝置被拔掉了，介面就此失效；丟掉之後下一輪會重新解析
        _drop_meter(flow)
        return 0.0
    return round(float(value.value), 4)


def _percent(scalar: float) -> int:
    return max(0, min(100, int(round(float(scalar) * 100))))


# --------------------------------------------------------------------------
# 應用程式工作階段
# --------------------------------------------------------------------------

def _resolve_indirect(text: str) -> str:
    """把 `@%SystemRoot%\\System32\\AudioSrv.Dll,-202` 這種資源字串解成人看得懂的字。

    系統音效那一列的顯示名稱就是這個格式，不解的話畫面上會出現一串路徑。
    """
    if not text.startswith("@"):
        return text
    buffer = ctypes.create_unicode_buffer(512)
    try:
        hr = _shlwapi.SHLoadIndirectString(c_wchar_p(text), buffer, 512, None)
    except Exception:
        return ""
    return buffer.value if hr == 0 and buffer.value else ""


def _session_manager(scope: _Scope, device: c_void_p) -> c_void_p:
    return _activate(scope, device, IID_IAudioSessionManager2, "Activate(IAudioSessionManager2)")


def _iter_sessions(scope: _Scope, device: c_void_p) -> list[c_void_p]:
    """列出裝置上所有工作階段的 IAudioSessionControl2。"""
    manager = _session_manager(scope, device)
    enumerator = c_void_p()
    _call(manager, 5, (POINTER(c_void_p),), byref(enumerator), where="GetSessionEnumerator")
    scope.own(enumerator)

    count = c_int()
    _call(enumerator, 3, (POINTER(c_int),), byref(count), where="IAudioSessionEnumerator::GetCount")

    controls: list[c_void_p] = []
    for index in range(count.value):
        control = c_void_p()
        if _invoke(enumerator, 4, (c_int, POINTER(c_void_p)), index, byref(control)) < 0:
            continue
        scope.own(control)
        try:
            controls.append(_query(scope, control, IID_IAudioSessionControl2, "QI(IAudioSessionControl2)"))
        except AudioError:
            continue
    return controls


def _session_key(control: c_void_p) -> str:
    """工作階段的穩定識別。

    用 instance identifier 而不是 PID：同一個程式可能開多個工作階段，
    而 PID 在程式重開後會被回收給別人，拿它當鍵會把音量套到錯的目標上。
    """
    out = c_wchar_p()
    if _invoke(control, 13, (POINTER(c_wchar_p),), byref(out)) < 0 or not out.value:
        return ""
    value = out.value
    _ole32.CoTaskMemFree(out)
    return value


def _session_info(scope: _Scope, control: c_void_p, with_icon: bool) -> dict[str, Any] | None:
    state = c_int()
    if _invoke(control, 3, (POINTER(c_int),), byref(state)) < 0:
        return None
    # 已過期的工作階段對應的程式早就結束了，留在列表上只會讓人以為還能調
    if state.value == _STATE_EXPIRED:
        return None

    key = _session_key(control)
    if not key:
        return None

    is_system = _invoke(control, 15, ()) == 0  # IsSystemSoundsSession：S_OK 才是

    pid = c_ulong()
    if _invoke(control, 14, (POINTER(c_ulong),), byref(pid)) < 0:
        pid.value = 0

    name = ""
    icon = ""
    path = ""
    if not is_system:
        out = c_wchar_p()
        if _invoke(control, 4, (POINTER(c_wchar_p),), byref(out)) >= 0 and out.value:
            name = _resolve_indirect(out.value)
            _ole32.CoTaskMemFree(out)
        # 大多數程式根本沒設 DisplayName，真正的名字要從執行檔的版本資源拿
        path = appicon.process_path(int(pid.value))
        if not name:
            name = appicon.display_name(path)
        if with_icon:
            icon = appicon.icon_data_uri(path)

    volume = _query(scope, control, IID_ISimpleAudioVolume, "QI(ISimpleAudioVolume)")
    level = c_float()
    muted = c_int()
    _call(volume, 4, (POINTER(c_float),), byref(level), where="ISimpleAudioVolume::GetMasterVolume")
    _call(volume, 6, (POINTER(c_int),), byref(muted), where="ISimpleAudioVolume::GetMute")

    peak = 0.0
    try:
        meter = _query(scope, control, IID_IAudioMeterInformation, "QI(IAudioMeterInformation)")
        value = c_float()
        _call(meter, 3, (POINTER(c_float),), byref(value), where="GetPeakValue")
        peak = round(float(value.value), 4)
    except Exception:
        peak = 0.0

    return {
        "key": key,
        "name": name,
        "path": path,
        "icon": icon,
        "pid": int(pid.value),
        "is_system": is_system,
        "active": state.value == 1,
        "volume": _percent(level.value),
        "muted": bool(muted.value),
        "peak": peak,
    }


def _find_session(scope: _Scope, enumerator: c_void_p, key: str) -> c_void_p | None:
    """在所有輸出裝置上找那個工作階段。

    刻意掃過每一台而不只有預設裝置：應用程式可以被指定輸出到別的裝置，
    只看預設裝置的話那些程式的滑桿會拉了沒反應。
    """
    for device in _iter_devices(scope, enumerator, RENDER):
        for control in _iter_sessions(scope, device):
            if _session_key(control) == key:
                return control
    return None


# --------------------------------------------------------------------------
# 裝置列舉
# --------------------------------------------------------------------------

def _iter_devices(scope: _Scope, enumerator: c_void_p, flow: int) -> list[c_void_p]:
    collection = c_void_p()
    _call(
        enumerator, 3, (c_int, c_ulong, POINTER(c_void_p)),
        flow, DEVICE_STATE_ACTIVE, byref(collection), where="EnumAudioEndpoints",
    )
    scope.own(collection)

    count = c_uint()
    _call(collection, 3, (POINTER(c_uint),), byref(count), where="IMMDeviceCollection::GetCount")

    devices: list[c_void_p] = []
    for index in range(count.value):
        device = c_void_p()
        if _invoke(collection, 4, (c_uint, POINTER(c_void_p)), index, byref(device)) < 0:
            continue
        devices.append(scope.own(device))
    return devices


def _describe_flow(scope: _Scope, enumerator: c_void_p, flow: int) -> dict[str, Any]:
    default = _default_device(scope, enumerator, flow)
    default_id = _device_id(default) if default else ""
    _sync_meter(flow, default, default_id)

    devices = []
    for device in _iter_devices(scope, enumerator, flow):
        try:
            devices.append({"id": _device_id(device), "name": _device_name(scope, device)})
        except AudioError:
            continue

    state: dict[str, Any] = {
        "devices": devices,
        "default_id": default_id,
        "volume": 0,
        "muted": False,
        "peak": 0.0,
        "available": default is not None,
    }
    if default is not None:
        try:
            state.update(_read_endpoint(scope, default))
            state["peak"] = _cached_peak(flow)
        except AudioError:
            state["available"] = False
    return state


# --------------------------------------------------------------------------
# 對外 API —— 全部經由 COM 執行緒
# --------------------------------------------------------------------------

def overview() -> dict[str, Any]:
    """整頁需要的完整狀態：兩個端點 + 所有應用程式（含圖示）。"""
    def work() -> dict[str, Any]:
        with _Scope() as scope:
            enumerator = _enumerator(scope)
            render = _describe_flow(scope, enumerator, RENDER)
            capture = _describe_flow(scope, enumerator, CAPTURE)

            # 只列預設輸出裝置上的工作階段，和 Windows 混音器一致。
            # 掃過每一台的話「系統音效」會每台各出現一列（它是 per-device 的），
            # 使用者會看到四五列一模一樣的東西卻各自有不同音量。
            sessions: list[dict[str, Any]] = []
            device = _default_device(scope, enumerator, RENDER)
            if device is not None:
                for control in _iter_sessions(scope, device):
                    try:
                        info = _session_info(scope, control, with_icon=True)
                    except AudioError:
                        continue
                    if info:
                        sessions.append(info)

            # 系統音效固定排最前（和 Windows 混音器一致），其餘依名稱排列，
            # 這樣列表不會因為工作階段建立順序而每次刷新都跳動
            sessions.sort(key=lambda s: (not s["is_system"], s["name"].lower()))
            return {"render": render, "capture": capture, "sessions": sessions}

    return _COM.run(work)


def levels() -> dict[str, Any]:
    """輪詢用的輕量版：只有數值，沒有名稱與圖示。

    音量表要跟得上聲音才有意義，所以這條路徑會被高頻呼叫；
    每次都把圖示（每張數 KB）重送一遍是純粹的浪費。
    """
    def work() -> dict[str, Any]:
        with _Scope() as scope:
            enumerator = _enumerator(scope)
            out: dict[str, Any] = {"sessions": {}}
            render_device: c_void_p | None = None
            for name, flow in (("render", RENDER), ("capture", CAPTURE)):
                device = _default_device(scope, enumerator, flow)
                if flow == RENDER:
                    render_device = device
                if device is None:
                    _sync_meter(flow, None, "")
                    out[name] = None
                    continue
                try:
                    state = _read_endpoint(scope, device)
                except AudioError:
                    out[name] = None
                    continue
                device_id = _device_id(device)
                _sync_meter(flow, device, device_id)
                state["peak"] = _cached_peak(flow)
                state["default_id"] = device_id
                out[name] = state

            if render_device is not None:
                for control in _iter_sessions(scope, render_device):
                    try:
                        info = _session_info(scope, control, with_icon=False)
                    except AudioError:
                        continue
                    if info:
                        out["sessions"][info["key"]] = {
                            "volume": info["volume"],
                            "muted": info["muted"],
                            "peak": info["peak"],
                            "active": info["active"],
                        }
            return out

    return _COM.run(work)


def peaks() -> dict[str, float]:
    """只有輸出與輸入的即時音量表。

    音量表要跟得上聲音才有意義（大約十分之一秒更新一次），但 levels() 要列舉
    所有工作階段、開十幾個介面，用那個頻率去打會吃掉可觀的 CPU。
    這條路徑只碰兩個端點，成本大約是它的十分之一。
    """
    def work() -> dict[str, float]:
        out: dict[str, float] = {}
        for name, flow in (("render", RENDER), ("capture", CAPTURE)):
            if flow not in _meter_cache:
                # 快取是空的（首次呼叫，或裝置剛被拔掉）才付一次解析的成本
                with _Scope() as scope:
                    device = _default_device(scope, _enumerator(scope), flow)
                    _sync_meter(flow, device, _device_id(device) if device else "")
            out[name] = _cached_peak(flow)
        return out

    return _COM.run(work)


def set_endpoint_volume(flow: str, percent: int, device_id: str = "") -> None:
    target = FLOWS.get(flow, RENDER)
    scalar = max(0.0, min(1.0, float(percent) / 100.0))

    def work() -> None:
        with _Scope() as scope:
            enumerator = _enumerator(scope)
            device = (
                _open_device(scope, enumerator, device_id)
                if device_id
                else _default_device(scope, enumerator, target)
            )
            if device is None:
                raise AudioError("找不到音訊端點", 0)
            volume = _activate(scope, device, IID_IAudioEndpointVolume, "Activate(IAudioEndpointVolume)")
            _call(
                volume, 7, (c_float, POINTER(GUID)), c_float(scalar), None,
                where="SetMasterVolumeLevelScalar",
            )

    _COM.run(work)


def set_endpoint_mute(flow: str, muted: bool, device_id: str = "") -> None:
    target = FLOWS.get(flow, RENDER)

    def work() -> None:
        with _Scope() as scope:
            enumerator = _enumerator(scope)
            device = (
                _open_device(scope, enumerator, device_id)
                if device_id
                else _default_device(scope, enumerator, target)
            )
            if device is None:
                raise AudioError("找不到音訊端點", 0)
            volume = _activate(scope, device, IID_IAudioEndpointVolume, "Activate(IAudioEndpointVolume)")
            _call(volume, 14, (c_int, POINTER(GUID)), c_int(1 if muted else 0), None, where="SetMute")

    _COM.run(work)


def set_session_volume(key: str, percent: int) -> None:
    scalar = max(0.0, min(1.0, float(percent) / 100.0))

    def work() -> None:
        with _Scope() as scope:
            control = _find_session(scope, _enumerator(scope), key)
            if control is None:
                raise AudioError("找不到這個應用程式的音訊工作階段", 0)
            volume = _query(scope, control, IID_ISimpleAudioVolume, "QI(ISimpleAudioVolume)")
            _call(
                volume, 3, (c_float, POINTER(GUID)), c_float(scalar), None,
                where="ISimpleAudioVolume::SetMasterVolume",
            )

    _COM.run(work)


def set_session_mute(key: str, muted: bool) -> None:
    def work() -> None:
        with _Scope() as scope:
            control = _find_session(scope, _enumerator(scope), key)
            if control is None:
                raise AudioError("找不到這個應用程式的音訊工作階段", 0)
            volume = _query(scope, control, IID_ISimpleAudioVolume, "QI(ISimpleAudioVolume)")
            _call(
                volume, 5, (c_int, POINTER(GUID)), c_int(1 if muted else 0), None,
                where="ISimpleAudioVolume::SetMute",
            )

    _COM.run(work)


def reset_sessions() -> int:
    """把所有應用程式的音量拉回 100% 並解除靜音，回傳處理的數量。

    對應 Windows 混音器底下那顆「重設」—— 換過驅動模式之後有些程式的工作階段
    會帶著上一輪的音量回來，一個一個拉太慢。
    """
    def work() -> int:
        changed = 0
        with _Scope() as scope:
            enumerator = _enumerator(scope)
            for device in _iter_devices(scope, enumerator, RENDER):
                for control in _iter_sessions(scope, device):
                    try:
                        volume = _query(scope, control, IID_ISimpleAudioVolume, "QI(ISimpleAudioVolume)")
                        _call(volume, 3, (c_float, POINTER(GUID)), c_float(1.0), None, where="SetMasterVolume")
                        _call(volume, 5, (c_int, POINTER(GUID)), c_int(0), None, where="SetMute")
                        changed += 1
                    except AudioError:
                        continue
        return changed

    return _COM.run(work)


def set_default_device(device_id: str, flow: str = "render") -> None:
    """把某個端點設為預設裝置。

    三個 ERole 都要設。只設 eConsole 的話，Teams、Discord 這類走
    eCommunications 的程式仍然會用舊裝置 —— 使用者會看到「明明切過去了，
    但通話還在原本的耳機上」。
    """
    del flow  # 裝置 ID 本身就決定了方向，IPolicyConfig 不需要另外指定

    def work() -> None:
        with _Scope() as scope:
            for iid, index in ((IID_IPolicyConfig, 13), (IID_IPolicyConfigVista, 10)):
                ptr = c_void_p()
                hr = _ole32.CoCreateInstance(
                    byref(CLSID_PolicyConfigClient), None, CLSCTX_ALL, byref(iid), byref(ptr)
                )
                if hr < 0 or not ptr.value:
                    continue
                scope.own(ptr)
                try:
                    for role in _ROLES:
                        _call(
                            ptr, index, (c_wchar_p, c_int), device_id, role,
                            where="IPolicyConfig::SetDefaultEndpoint",
                        )
                    # 快取的音量表還指著上一台裝置，不丟掉的話表會停住
                    _drop_meter(RENDER)
                    _drop_meter(CAPTURE)
                    return
                except AudioError:
                    continue
            raise AudioError("這個 Windows 版本不接受切換預設裝置的呼叫", 0)

    _COM.run(work)
