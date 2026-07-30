"""在 Focusrite 原廠驅動與 Windows 內建 UAC2 類別驅動之間切換。

## 為什麼需要這個

Focusrite 的驅動在音訊串流丟包後不會重新同步，會卡在壞掉的狀態（持續電流音
或直接沒聲音）。Windows 內建的 UAC2 類別驅動（`usbaudio2.sys`）沒有這個問題，
但它沒有原生 ASIO，全雙工延遲被 Windows 音訊引擎鎖在約 46 ms。

兩者各有不可取代的優點，而實測發現失效幾乎只發生在**日常使用**（大量程式反覆
開關音訊串流、切換取樣率），而不是 DAW 工作時（單一 ASIO 串流、固定取樣率、
一路持有）。所以最合理的用法是按情境切換：

- `MODE_DAILY` — 內建類別驅動。日常聽音樂、看影片、遊戲。穩定優先。
- `MODE_ASIO`  — 原廠驅動 + Focusrite ASIO。練琴／錄音。低延遲優先。

## 實作原理

Focusrite 的 `focusritecustom.inf` 以 hardware ID `USB\\VID_xxxx&PID_xxxx` 匹配
整台 USB composite 裝置，driver rank `00FF0001`。Windows 內建的 `usb.inf` 只以
compatible ID `USB\\COMPOSITE` 匹配，rank `00FF2006` —— 永遠被 outrank。

這是關鍵限制：**`pnputil` 無法安裝被 outrank 的驅動**，官方文件明載
「If the driver is not the highest ranked driver on the system, PnPUtil will not
force it onto the device.」

所以切到內建驅動必須「強制指定」，而不是「安裝」。這裡直接呼叫 `newdev.dll`
的 `UpdateDriverForPlugAndPlayDevicesW` 並帶 `INSTALLFLAG_FORCE` —— 這正是
`devcon update` 的底層做法，也是裝置管理員「讓我從清單中挑選」所走的路徑。
好處是完全不動 driver store：兩個驅動都留著，切換隨時可逆。

切回原廠方向不需要 force（它本來就是最高分），但一樣用同一條路徑處理，
因為手動指定過的裝置會留下綁定記錄，只靠 rescan 不一定會切回去。
"""
from __future__ import annotations

import ctypes
import json
import re
import subprocess
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

from .device import FOCUSRITE_VID, ActionResult, _run, _run_powershell, is_elevated
from .i18n import t

MODE_DAILY = "daily"
MODE_ASIO = "asio"
MODE_UNKNOWN = "unknown"

# Windows 內建 USB composite 驅動（usbccgp）。in-box，永遠存在。
WINDOWS_USB_INF = Path(r"C:\Windows\INF\usb.inf")

# 原廠驅動包在 driver store 裡的原始檔名
FOCUSRITE_INF_ORIGINAL = "focusritecustom.inf"

# 已知的原廠驅動安裝位置（driver store 查不到時的退路）
_FOCUSRITE_FALLBACK_DIRS = (
    Path(r"C:\Program Files\Focusrite\Drivers"),
    Path(r"C:\Program Files (x86)\Focusrite\Drivers"),
)

# 切到內建驅動後，音訊介面應該綁上的服務
_CLASS_AUDIO_SERVICE = "usbaudio2"
# 切到內建驅動後，composite 母節點應該綁上的服務
_CLASS_PARENT_SERVICE = "usbccgp"

_INSTALLFLAG_FORCE = 0x00000001
_INSTALLFLAG_NONINTERACTIVE = 0x00000004


# --------------------------------------------------------------------------
# 驅動包定位
# --------------------------------------------------------------------------

_OEM_INF_RE = re.compile(r"^oem\d+\.inf$", re.IGNORECASE)


def _driver_store_inf(original_name: str) -> Path | None:
    """在 driver store 裡找出某個原始檔名對應的 oemXX.inf 實際路徑。

    driver store 的 oem 編號會隨每次安裝改變，所以絕對不能寫死。

    `pnputil /enum-drivers` 的欄位標籤會隨系統語言變化（「已發佈的名稱」／
    "Published Name"），所以這裡只看**值**的長相、不看標籤文字：
    以空白行切出每個驅動包的區塊，在區塊內同時找到一個 oemXX.inf
    和一個等於目標原始檔名的值，才算命中。
    """
    try:
        proc = _run(["pnputil", "/enum-drivers"], timeout=60.0)
    except (subprocess.TimeoutExpired, OSError):
        return None

    target = original_name.lower()
    published = ""
    matched = False

    def resolve() -> Path | None:
        if not (published and matched):
            return None
        candidate = Path(r"C:\Windows\INF") / published
        return candidate if candidate.exists() else None

    for line in (proc.stdout or "").splitlines():
        if not line.strip():  # 區塊結束
            hit = resolve()
            if hit:
                return hit
            published, matched = "", False
            continue
        if ":" not in line:
            continue
        value = line.split(":", 1)[1].strip()
        if _OEM_INF_RE.match(value):
            published = value
        elif value.lower() == target:
            matched = True

    return resolve()


def find_focusrite_inf(override: str = "") -> Path | None:
    """找出可用的原廠驅動 INF。

    優先用 driver store 裡那一份 —— 它已經 staged、簽章齊全，不需要重新驗證。
    """
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return candidate

    staged = _driver_store_inf(FOCUSRITE_INF_ORIGINAL)
    if staged:
        return staged

    for folder in _FOCUSRITE_FALLBACK_DIRS:
        for name in ("FocusriteCustom.inf", "focusritecustom.inf"):
            candidate = folder / name
            if candidate.is_file():
                return candidate

    # 專案自帶的匯出備份（pnputil /export-driver 產生）
    backup = Path(__file__).resolve().parents[3] / "driver-backup" / "focusritecustom.inf"
    if backup.is_file():
        return backup
    return None


# --------------------------------------------------------------------------
# 現況探測
# --------------------------------------------------------------------------

# 一次取得判斷模式所需的全部資訊。
#
# 母節點（composite）與子節點（&MI_00 音訊介面）綁的服務是最可靠的判準：
# 類別驅動下母節點是 usbccgp、子節點是 usbaudio2；原廠驅動下母節點是
# FocusriteUsb，而且子節點根本不會被列舉出來（Focusrite 自己接管了列舉）。
_PROBE_SCRIPT = r"""
function Prop($id, $key) {
  try { [string](Get-PnpDeviceProperty -InstanceId $id -KeyName $key -ErrorAction Stop).Data }
  catch { '' }
}

$all = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
  $_.InstanceId -like 'USB\__VID__*'
}

$root = $all | Where-Object { $_.InstanceId -notlike '*&MI_*' -and $_.Status -eq 'OK' } |
        Select-Object -First 1
if (-not $root) {
  $root = $all | Where-Object { $_.InstanceId -notlike '*&MI_*' } | Select-Object -First 1
}

$audio = $all | Where-Object { $_.InstanceId -like '*&MI_00*' -and $_.Status -eq 'OK' } |
         Select-Object -First 1

# 錄音模式的音訊 function 掛在軟體根底下，不是 USB 裝置的子節點。
# 它在線與否是「錄音模式是否真的可用」的唯一判準 —— 母節點綁上 FocusriteUsb
# 只代表帳面換好了，不代表音訊路徑起來了。
$adapter = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
  $_.InstanceId -like 'FOCUSRITEUSB\AUDIO&ADAPTER*' -and $_.Status -eq 'OK'
} | Select-Object -First 1

$endpoints = @(Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue |
  Where-Object { $_.Status -eq 'OK' } | Select-Object -ExpandProperty FriendlyName)

# 真正需要重開機的唯一權威訊號：有裝置卡在 CM_PROB_NEED_RESTART（Code 14）。
# 換綁 API 回傳的 bRebootRequired 極度保守，不能當結論用。
$needRestart = @(Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
  ($_.InstanceId -like 'USB\__VID__*' -or $_.InstanceId -like 'FOCUSRITEUSB*') -and
  ($_.Problem -eq 'CM_PROB_NEED_RESTART' -or $_.Problem -eq 14)
} | Select-Object -ExpandProperty InstanceId)

$out = @{
  root_id       = ''
  root_name     = ''
  root_status   = ''
  root_problem  = ''
  root_service  = ''
  root_inf      = ''
  root_class    = ''
  audio_service = ''
  audio_status  = ''
  adapter_id    = ''
  endpoints     = $endpoints
  need_restart  = $needRestart
}

if ($adapter) { $out.adapter_id = [string]$adapter.InstanceId }

if ($root) {
  $out.root_id      = [string]$root.InstanceId
  $out.root_name    = [string]$root.FriendlyName
  $out.root_status  = [string]$root.Status
  $out.root_problem = [string]$root.Problem
  $out.root_class   = [string]$root.Class
  $out.root_service = Prop $root.InstanceId 'DEVPKEY_Device_Service'
  $out.root_inf     = Prop $root.InstanceId 'DEVPKEY_Device_DriverInfPath'
}
if ($audio) {
  $out.audio_service = Prop $audio.InstanceId 'DEVPKEY_Device_Service'
  $out.audio_status  = [string]$audio.Status
}

$out | ConvertTo-Json -Depth 4 -Compress
""".replace("__VID__", FOCUSRITE_VID)


def probe() -> dict[str, Any]:
    """回報目前的驅動模式與支撐該判斷的原始證據。

    刻意把證據一起回傳，讓 UI 能顯示「為什麼判定是這個模式」，
    而不是只給一個無法查核的結論。
    """
    try:
        raw = _run_powershell(_PROBE_SCRIPT, timeout=60.0).strip()
        data = json.loads(raw) if raw else {}
    except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        data = {}

    root_service = str(data.get("root_service") or "")
    root_class = str(data.get("root_class") or "")
    audio_service = str(data.get("audio_service") or "")
    endpoints = [str(x) for x in (data.get("endpoints") or [])]

    mode = MODE_UNKNOWN
    if "focusrite" in root_service.lower() or "focusrite" in root_class.lower():
        mode = MODE_ASIO
    elif root_service.lower() == _CLASS_PARENT_SERVICE:
        mode = MODE_DAILY

    root_id = str(data.get("root_id") or "")
    problem = str(data.get("root_problem") or "")
    # CM_PROB_NONE / 0 都代表沒問題；其餘都要讓使用者看到
    healthy = problem in ("", "0", "CM_PROB_NONE")

    restart_nodes = [str(x) for x in (data.get("need_restart") or []) if x]
    adapter_id = str(data.get("adapter_id") or "")
    usbaudio2_child = audio_service.lower() == _CLASS_AUDIO_SERVICE

    # 「母節點綁誰」和「音訊路徑是否真的起來」是兩件事，必須分開判斷。
    #
    # 實測過的失敗樣態：母節點成功換綁到 FocusriteUsb，但 usbccgp 建立的 MI_00
    # 子節點還活著、還綁著 usbaudio2 —— 因為它持有的音訊端點被音訊引擎抓著，
    # 舊堆疊拆不掉，於是 Focusrite 的 AUDIO&ADAPTER 節點根本沒被生出來。
    # 這種狀態下 UI 顯示「錄音模式」，但實際上沒有任何 ASIO 裝置可用。
    if mode == MODE_ASIO:
        complete = bool(adapter_id) and not usbaudio2_child
    elif mode == MODE_DAILY:
        complete = usbaudio2_child
    else:
        complete = False

    return {
        "mode": mode,
        "available": bool(root_id),
        "healthy": healthy,
        # 目標模式的音訊路徑是否真的可用（不只是母節點換綁成功）
        "complete": complete,
        "adapter_id": adapter_id,
        "usbaudio2_child": usbaudio2_child,
        # 唯一能證明「真的需要重開機」的訊號
        "needs_restart": bool(restart_nodes),
        "restart_nodes": restart_nodes,
        "root_id": root_id,
        "root_name": str(data.get("root_name") or ""),
        "root_status": str(data.get("root_status") or ""),
        "root_problem": problem,
        "root_service": root_service,
        "root_class": root_class,
        "root_inf": str(data.get("root_inf") or ""),
        "audio_service": audio_service,
        "audio_status": str(data.get("audio_status") or ""),
        "endpoints": [e for e in endpoints if "scarlett" in e.lower() or "focusrite" in e.lower()],
        "hardware_id": hardware_id_from_instance(root_id),
    }


def hardware_id_from_instance(instance_id: str) -> str:
    """從 instance ID 推出 hardware ID。

    `USB\\VID_1235&PID_8218\\S1PZGZH584102B` → `USB\\VID_1235&PID_8218`

    刻意不寫死 PID，這樣任何 Focusrite 介面都適用。
    """
    if not instance_id:
        return ""
    parts = instance_id.split("\\")
    if len(parts) < 3:
        return ""
    return "\\".join(parts[:2])


# --------------------------------------------------------------------------
# 強制綁定
# --------------------------------------------------------------------------

def _force_install(hardware_id: str, inf_path: Path) -> tuple[bool, str, bool]:
    """把指定的 INF 強制綁到符合 hardware_id 的裝置上。

    回傳 (成功, 訊息, 是否需要重開機)。
    """
    try:
        # use_last_error 必須開，否則 ctypes.get_last_error() 永遠拿到 0，
        # 失敗時就只剩一句「失敗」而沒有任何可查的錯誤碼。
        newdev = ctypes.WinDLL("newdev.dll", use_last_error=True)
    except OSError as exc:
        return False, f"newdev.dll: {exc}", False

    func = newdev.UpdateDriverForPlugAndPlayDevicesW
    func.argtypes = [
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.BOOL),
    ]
    func.restype = wintypes.BOOL

    reboot = wintypes.BOOL(False)
    ok = func(
        None,
        hardware_id,
        str(inf_path),
        _INSTALLFLAG_FORCE | _INSTALLFLAG_NONINTERACTIVE,
        ctypes.byref(reboot),
    )
    if ok:
        return True, "", bool(reboot.value)

    return False, _win_error_text(ctypes.get_last_error()), bool(reboot.value)


def _pause_audio_engine() -> list[str]:
    """停掉 Windows 音訊服務，放掉它們對音訊 KS filter 的 handle。

    這是「換綁被延後到重開機」的根本原因：`AudioEndpointBuilder` 持有音訊端點的
    handle，舊的裝置堆疊就拆不掉，PnP 只能把驅動替換排到下次開機。

    回傳原本正在執行的服務名，供之後還原。順序很重要 —— Audiosrv 依賴
    AudioEndpointBuilder，必須先停 Audiosrv。
    """
    was_running: list[str] = []
    for name in ("Audiosrv", "AudioEndpointBuilder"):
        try:
            out = _run_powershell(
                f"$s = Get-Service {name} -ErrorAction Stop; "
                "if ($s.Status -eq 'Running') { "
                # -Force 會一併停掉相依服務（midisrv、AarSvc 等），
                # 少了它 AudioEndpointBuilder 根本停不下來
                f"  Stop-Service {name} -Force -ErrorAction Stop; 'STOPPED' "
                "} else { 'ALREADY' }",
                timeout=45.0,
            )
            if "STOPPED" in out:
                was_running.append(name)
        except (RuntimeError, subprocess.TimeoutExpired, OSError):
            continue
    return was_running


def _resume_audio_engine(names: list[str]) -> None:
    """還原音訊服務。無論換綁成功或失敗都必須執行，否則整台電腦沒有聲音。"""
    # 還原順序與停止相反：先起 AudioEndpointBuilder，Audiosrv 才起得來
    for name in ("AudioEndpointBuilder", "Audiosrv"):
        if name not in names:
            continue
        try:
            _run_powershell(f"Start-Service {name} -ErrorAction Stop", timeout=45.0)
        except (RuntimeError, subprocess.TimeoutExpired, OSError):
            continue


def _set_device_enabled(instance_id: str, enabled: bool) -> None:
    """停用／啟用裝置，用來強制拆掉並重建整條堆疊。"""
    safe = instance_id.replace("'", "''")
    verb = "Enable-PnpDevice" if enabled else "Disable-PnpDevice"
    try:
        _run_powershell(
            f"{verb} -InstanceId '{safe}' -Confirm:$false -ErrorAction Stop", timeout=60.0
        )
    except (RuntimeError, subprocess.TimeoutExpired, OSError):
        pass


_WELL_KNOWN_ERRORS = {
    0x000000B7: "ERROR_ALREADY_EXISTS",
    0x00000005: "ERROR_ACCESS_DENIED — 需要系統管理員權限",
    0x00000002: "ERROR_FILE_NOT_FOUND — INF 路徑不存在",
    0x00000490: "ERROR_NOT_FOUND — 找不到符合該 hardware ID 的裝置",
    0xE0000203: "ERROR_NO_SUCH_DEVINST — 裝置不在線上",
    0xE000020B: "ERROR_NO_DRIVER_SELECTED",
    0xE0000217: "ERROR_NO_COMPAT_DRIVERS — 這個 INF 不支援該裝置",
    0xE0000242: "ERROR_IN_WOW64 — 必須以 64 位元行程執行",
}


def _win_error_text(code: int) -> str:
    label = _WELL_KNOWN_ERRORS.get(code & 0xFFFFFFFF, "")
    try:
        message = ctypes.FormatError(code).strip()
    except Exception:
        message = ""
    parts = [f"0x{code & 0xFFFFFFFF:08X}"]
    if label:
        parts.append(label)
    elif message:
        parts.append(message)
    return " ".join(parts)


# --------------------------------------------------------------------------
# 切換
# --------------------------------------------------------------------------

def _attempt_rebind(
    hardware_id: str,
    inf: Path,
    root_id: str,
    pause_engine: bool = False,
) -> tuple[bool, str, bool]:
    """執行一次換綁。

    `pause_engine=True` 時先停掉 Windows 音訊服務、停用裝置，換綁後再啟用並還原服務。
    這是為了放掉 `AudioEndpointBuilder` 對音訊端點的 handle —— 沒放掉的話舊的裝置
    堆疊拆不掉，PnP 只能把驅動替換排到下次開機（實測就是這樣卡住的）。
    """
    paused: list[str] = []
    if pause_engine:
        paused = _pause_audio_engine()
    try:
        if pause_engine:
            # 停用會連帶拆掉所有子節點，這正是舊音訊堆疊消失的關鍵一步
            _set_device_enabled(root_id, False)
            time.sleep(0.8)

        ok, error, reboot = _force_install(hardware_id, inf)

        if pause_engine:
            _set_device_enabled(root_id, True)

        # 換綁後一定要掃一次：音訊 function 是靠重新列舉才生出來的，
        # 不掃的話端點會遲遲不出現。
        try:
            _run(["pnputil", "/scan-devices"], timeout=60.0)
        except (subprocess.TimeoutExpired, OSError):
            pass
        return ok, error, reboot
    finally:
        # 無論成功或失敗都必須還原服務，否則整台電腦沒有聲音
        _resume_audio_engine(paused)


def switch_mode(
    mode: str,
    focusrite_inf_override: str = "",
    settle_seconds: float = 2.0,
) -> ActionResult:
    """切換驅動模式。切換期間音訊必然中斷數秒。"""
    if mode not in (MODE_DAILY, MODE_ASIO):
        return ActionResult(False, t("mode.badmode"), mode)
    if not is_elevated():
        return ActionResult(False, t("dev.needadmin"), t("mode.needadmin.detail"))

    before = probe()
    if not before["available"]:
        return ActionResult(False, t("dev.notfound"), t("dev.notfound.detail"))
    # 這裡一定要連 complete 一起檢查。只看 mode 的話，卡在「母節點換好但音訊路徑
    # 沒起來」的狀態時會直接回報「已經是這個模式」而什麼都不做 —— 那正是最需要
    # 重跑換綁去修好的狀態。
    if before["mode"] == mode and before["healthy"] and before["complete"]:
        return ActionResult(
            True, t("mode.already", mode=_label(mode)), "", 0, {"mode": mode, "changed": False}
        )

    hardware_id = before["hardware_id"]
    if not hardware_id:
        return ActionResult(False, t("mode.nohwid"), before["root_id"])

    if mode == MODE_DAILY:
        inf = WINDOWS_USB_INF
        if not inf.is_file():
            return ActionResult(False, t("mode.noinf"), str(inf))
    else:
        found = find_focusrite_inf(focusrite_inf_override)
        if found is None:
            return ActionResult(False, t("mode.nofocusrite"), t("mode.nofocusrite.detail"))
        inf = found

    started = time.perf_counter()

    # 預測第一次就需要暫停音訊引擎。
    #
    # 切到錄音模式而且目前有活著的 usbaudio2 子節點時，舊堆疊必然被音訊引擎的
    # handle 釘住 —— 實測證實這種情況下軟體重置一定無效，只是白花十幾秒。
    # 既然判準明確，就直接走重手段，把 59 秒壓到 30 秒以內。
    pause_engine = mode == MODE_ASIO and before["usbaudio2_child"]

    ok, error, reboot = _attempt_rebind(
        hardware_id, inf, before["root_id"], pause_engine=pause_engine
    )
    if not ok:
        return ActionResult(
            False,
            t("mode.fail", mode=_label(mode)),
            t("mode.fail.detail", inf=str(inf), hwid=hardware_id, error=error),
            int((time.perf_counter() - started) * 1000),
            {"mode": before["mode"]},
        )

    after = _wait_for_mode(mode, timeout=20.0)
    if settle_seconds > 0:
        time.sleep(settle_seconds)
        after = probe()

    # 換綁 API 說「需要重開機」時，先不要相信它。
    #
    # UpdateDriverForPlugAndPlayDevicesW 的 bRebootRequired 極度保守：舊的裝置堆疊
    # 只要有一瞬間沒能立刻拆掉（音訊端點被 AudioEndpointBuilder 短暫持有就會這樣），
    # 它就設成 TRUE —— 即使 PnP 隨後已經成功把整條堆疊換掉。實測連續八次來回切換，
    # 每次都當場生效、每次都回報需要重開機，一次都沒真的需要。
    #
    # 唯一權威的判準是有沒有裝置卡在 CM_PROB_NEED_RESTART（Code 14）。真的卡住時，
    # 也先用這個程式最擅長的軟體重置去化解 —— 那本來就是為了避開重開機而存在的。
    def settled() -> bool:
        return (
            not after["needs_restart"] and after["mode"] == mode and after["complete"]
        )

    restart_cleared = False
    escalated = pause_engine
    if not settled():
        # 第一級：軟體重置。成本最低，而且是這個程式本來就最擅長的事。
        # （已經預測過要暫停音訊引擎的話就跳過，那代表這一級不可能有用。）
        if not pause_engine:
            try:
                _run(["pnputil", "/restart-device", after["root_id"] or before["root_id"]])
            except (subprocess.TimeoutExpired, OSError):
                pass
            time.sleep(1.5)
            after = _wait_for_mode(mode, timeout=15.0)

        # 第二級：暫停音訊引擎後重來一次。
        if not settled():
            escalated = True
            _attempt_rebind(hardware_id, inf, before["root_id"], pause_engine=True)
            after = _wait_for_mode(mode, timeout=25.0)

        restart_cleared = settled()

    elapsed = int((time.perf_counter() - started) * 1000)
    extra = {
        "mode": after["mode"],
        "changed": True,
        # 只有實際存在 Code 14 才算真的要重開機，API 的旗標僅供紀錄
        "reboot_required": bool(after["needs_restart"]),
        "reboot_flag_from_api": reboot,
        "restart_cleared": restart_cleared,
        "escalated": escalated,
        "probe": after,
        "inf": str(inf),
    }

    if after["mode"] != mode:
        # 最要小心的失敗：母節點沒有 fallback 成功，裝置變成沒有驅動，
        # 結果是「Windows 完全找不到任何輸出輸入裝置」。這裡一定要講清楚怎麼救。
        return ActionResult(
            False,
            t("mode.verifyfail", mode=_label(mode)),
            t("mode.verifyfail.detail", service=after["root_service"] or "—",
              problem=after["root_problem"] or "—"),
            elapsed,
            extra,
        )

    if not after["healthy"]:
        return ActionResult(
            False,
            t("mode.unhealthy", mode=_label(mode)),
            t("mode.unhealthy.detail", problem=after["root_problem"]),
            elapsed,
            extra,
        )

    # 母節點換好、也沒有問題碼，但音訊路徑沒起來 —— 這是最容易被誤判成成功的失敗。
    # 使用者看到「已切換到錄音模式」卻找不到任何 ASIO 裝置，比直接失敗更難排查，
    # 所以寧可明確報錯。
    if not after["complete"]:
        return ActionResult(
            False,
            t("mode.incomplete", mode=_label(mode)),
            t(
                "mode.incomplete.detail",
                adapter=after["adapter_id"] or "—",
                child=after["audio_service"] or "—",
            ),
            elapsed,
            extra,
        )

    detail = t("mode.ok.detail", service=after["root_service"], audio=after["audio_service"] or "—")
    if restart_cleared:
        detail += "\n" + t("mode.escalated" if escalated else "mode.restartcleared")
    elif after["needs_restart"]:
        detail += "\n" + t("mode.reboot", nodes=", ".join(after["restart_nodes"]))
    return ActionResult(True, t("mode.ok", mode=_label(mode)), detail, elapsed, extra)


def _wait_for_mode(mode: str, timeout: float = 20.0) -> dict[str, Any]:
    """等裝置重新列舉完成。

    切換過程中會查到中間狀態，所以不能只看一次；而且**一定要等到 complete**，
    不能只看母節點綁到哪個驅動 —— 母節點換好而音訊路徑沒起來，是實測過的失敗樣態。
    """
    deadline = time.monotonic() + timeout
    latest = probe()
    while time.monotonic() < deadline:
        if latest["available"] and latest["mode"] == mode and latest["complete"]:
            return latest
        time.sleep(0.7)
        latest = probe()
    return latest


def _label(mode: str) -> str:
    return t("mode.daily") if mode == MODE_DAILY else t("mode.asio")


def repair() -> ActionResult:
    """裝置卡在沒有驅動的狀態時的救援：重掃 PnP，再強制綁回內建驅動。

    這是「切換到一半失敗、Windows 找不到任何音訊裝置」的解法。
    刻意固定救回**內建驅動** —— 它是 in-box 的，不可能不存在，
    所以這條路徑永遠可用。
    """
    if not is_elevated():
        return ActionResult(False, t("dev.needadmin"), t("mode.needadmin.detail"))

    try:
        _run(["pnputil", "/scan-devices"], timeout=60.0)
    except (subprocess.TimeoutExpired, OSError):
        pass

    state = probe()
    if state["available"] and state["healthy"] and state["mode"] != MODE_UNKNOWN:
        return ActionResult(
            True, t("mode.repair.nothing"), t("mode.ok.detail",
            service=state["root_service"], audio=state["audio_service"] or "—"),
            0, {"mode": state["mode"], "probe": state},
        )

    return switch_mode(MODE_DAILY)
