"""Focusrite 裝置的探索、重置與幽靈裝置清理。

重置的原理：`pnputil /restart-device` 會讓 Windows 對該裝置做一次完整的
「停用 → 重新列舉 → 啟用」，效果等同於實體拔插 USB，也就等同於在
Focusrite Device Settings 裡切換 Sample Rate 所觸發的 stream 重建。
"""
from __future__ import annotations

import ctypes
import json
import locale
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

# Focusrite 的 USB Vendor ID
FOCUSRITE_VID = "VID_1235"

_CREATE_NO_WINDOW = 0x08000000
_CONSOLE_ENCODING = locale.getpreferredencoding(False) or "utf-8"


@dataclass
class PnpDevice:
    instance_id: str
    friendly_name: str
    status: str
    device_class: str
    problem_code: str = ""

    @property
    def is_present(self) -> bool:
        return self.status.upper() == "OK"

    @property
    def is_ghost(self) -> bool:
        """殘留的幽靈裝置：曾經插過但現在不在線上。"""
        return self.status.upper() in {"UNKNOWN", "ERROR", "DEGRADED"}

    @property
    def is_usb_root(self) -> bool:
        """真正的 USB 實體裝置節點（而非它底下的音訊介面或端點）。"""
        upper = self.instance_id.upper()
        return upper.startswith("USB\\") and "&MI_" not in upper

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "friendly_name": self.friendly_name,
            "status": self.status,
            "device_class": self.device_class,
            "problem_code": self.problem_code,
            "is_present": self.is_present,
            "is_ghost": self.is_ghost,
            "is_usb_root": self.is_usb_root,
        }


@dataclass
class ActionResult:
    ok: bool
    message: str
    detail: str = ""
    duration_ms: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "message": self.message,
            "detail": self.detail,
            "duration_ms": self.duration_ms,
            **self.extra,
        }


# --------------------------------------------------------------------------
# 底層執行工具
# --------------------------------------------------------------------------

def is_elevated() -> bool:
    """目前行程是否具備系統管理員權限。pnputil 的裝置操作需要它。"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _run(args: list[str], timeout: float = 45.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        timeout=timeout,
        creationflags=_CREATE_NO_WINDOW,
        text=True,
        encoding=_CONSOLE_ENCODING,
        errors="replace",
    )


def _run_powershell(script: str, timeout: float = 45.0) -> str:
    """執行 PowerShell 並強制以 UTF-8 回傳，避免中文裝置名稱變亂碼。"""
    wrapped = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$ProgressPreference='SilentlyContinue'; " + script
    )
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", wrapped],
        capture_output=True,
        timeout=timeout,
        creationflags=_CREATE_NO_WINDOW,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError((proc.stderr or "PowerShell 執行失敗").strip())
    return proc.stdout


# --------------------------------------------------------------------------
# 探索
# --------------------------------------------------------------------------

def list_devices() -> list[PnpDevice]:
    """列出所有與 Focusrite 相關的 PnP 裝置，包含幽靈裝置。"""
    script = (
        "Get-PnpDevice | Where-Object { "
        "  $_.InstanceId -like '*VID_1235*' -or "
        "  $_.InstanceId -like 'FOCUSRITEUSB*' -or "
        "  $_.InstanceId -like '*FOCUSRITE*' -or "
        "  $_.FriendlyName -like '*Focusrite*' -or "
        "  $_.FriendlyName -like '*Scarlett*' "
        "} | Select-Object InstanceId, FriendlyName, Status, Class, Problem "
        "| ConvertTo-Json -Depth 3 -Compress"
    )
    try:
        out = _run_powershell(script).strip()
    except (RuntimeError, subprocess.TimeoutExpired, OSError):
        return []
    if not out:
        return []
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]

    devices: list[PnpDevice] = []
    for item in parsed:
        devices.append(
            PnpDevice(
                instance_id=str(item.get("InstanceId") or ""),
                friendly_name=str(item.get("FriendlyName") or "（無名稱）"),
                status=str(item.get("Status") or "Unknown"),
                device_class=str(item.get("Class") or ""),
                problem_code=str(item.get("Problem") or ""),
            )
        )
    return devices


def find_primary_device(preferred_instance_id: str = "") -> PnpDevice | None:
    """挑出要重置的目標裝置。

    優先序：使用者指定 → 在線上的 USB 實體節點 → 任何在線的 Focusrite 裝置。
    我們刻意選 USB 根節點（不含 &MI_）而不是它底下的音訊 function，
    因為重置根節點才等同於實體拔插。
    """
    devices = list_devices()
    if not devices:
        return None

    if preferred_instance_id:
        for dev in devices:
            if dev.instance_id.upper() == preferred_instance_id.upper():
                return dev

    usb_roots = [d for d in devices if d.is_usb_root and FOCUSRITE_VID in d.instance_id.upper()]
    for dev in usb_roots:
        if dev.is_present:
            return dev
    if usb_roots:
        return usb_roots[0]

    for dev in devices:
        if dev.is_present and dev.device_class.lower() != "audioendpoint":
            return dev
    return None


def list_ghosts() -> list[PnpDevice]:
    """反覆插拔／重裝驅動累積下來的殘留裝置。"""
    return [d for d in list_devices() if d.is_ghost]


def driver_info(instance_id: str) -> dict[str, Any]:
    """取得該裝置目前綁定的驅動版本與供應商。"""
    safe = instance_id.replace("'", "''")
    script = (
        f"$d = Get-PnpDevice -InstanceId '{safe}' -ErrorAction SilentlyContinue; "
        "if ($null -eq $d) { '{}' } else { "
        "  $p = @{}; "
        "  foreach ($k in 'DEVPKEY_Device_DriverVersion','DEVPKEY_Device_DriverProvider',"
        "'DEVPKEY_Device_DriverDate','DEVPKEY_Device_Manufacturer') { "
        "    $v = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName $k "
        "-ErrorAction SilentlyContinue).Data; if ($v) { $p[$k] = [string]$v } } "
        "  $p | ConvertTo-Json -Compress }"
    )
    try:
        out = _run_powershell(script).strip()
        data = json.loads(out) if out else {}
    except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        return {}
    return {
        "driver_version": data.get("DEVPKEY_Device_DriverVersion", ""),
        "driver_provider": data.get("DEVPKEY_Device_DriverProvider", ""),
        "driver_date": (data.get("DEVPKEY_Device_DriverDate", "") or "")[:10],
        "manufacturer": data.get("DEVPKEY_Device_Manufacturer", ""),
    }


def uses_focusrite_driver(devices: list[PnpDevice] | None = None) -> bool:
    """判斷目前是走 Focusrite 專屬驅動，還是 Windows 內建的 UAC2 類別驅動。

    裝上 Focusrite 驅動時，裝置會被歸到自訂的 'Focusrite Audio' 類別；
    用內建類別驅動時則會是標準的 'MEDIA' / 'AudioEndpoint'。
    """
    devices = devices if devices is not None else list_devices()
    return any("focusrite" in d.device_class.lower() for d in devices)


# --------------------------------------------------------------------------
# 動作
# --------------------------------------------------------------------------

def restart_device(instance_id: str) -> ActionResult:
    """軟體版的「拔掉再插回」。

    先用 pnputil /restart-device（Windows 10 2004+ 的官方做法），
    失敗時退回 Disable-PnpDevice + Enable-PnpDevice。
    """
    if not instance_id:
        return ActionResult(False, "找不到目標裝置", "請先在設定中選擇要重置的 Focusrite 裝置。")
    if not is_elevated():
        return ActionResult(
            False,
            "需要系統管理員權限",
            "重置 PnP 裝置必須以系統管理員身分執行，請用視窗上方的按鈕重新啟動。",
        )

    started = time.perf_counter()
    try:
        proc = _run(["pnputil", "/restart-device", instance_id])
    except (subprocess.TimeoutExpired, OSError) as exc:
        return ActionResult(False, "pnputil 執行失敗", str(exc))

    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode == 0:
        elapsed = int((time.perf_counter() - started) * 1000)
        return ActionResult(True, "裝置已重置", output, elapsed, {"method": "pnputil"})

    fallback = _restart_via_pnp_cmdlets(instance_id)
    fallback.duration_ms = int((time.perf_counter() - started) * 1000)
    if not fallback.ok:
        fallback.detail = (
            f"pnputil 失敗（exit {proc.returncode}）：{output}\n"
            f"備援方式也失敗：{fallback.detail}"
        )
    return fallback


def _restart_via_pnp_cmdlets(instance_id: str) -> ActionResult:
    safe = instance_id.replace("'", "''")
    script = (
        f"Disable-PnpDevice -InstanceId '{safe}' -Confirm:$false -ErrorAction Stop; "
        "Start-Sleep -Milliseconds 700; "
        f"Enable-PnpDevice -InstanceId '{safe}' -Confirm:$false -ErrorAction Stop; "
        "'OK'"
    )
    try:
        out = _run_powershell(script, timeout=60.0)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        return ActionResult(False, "重置失敗", str(exc), extra={"method": "pnp-cmdlets"})
    if "OK" in out:
        return ActionResult(True, "裝置已重置", out.strip(), extra={"method": "pnp-cmdlets"})
    return ActionResult(False, "重置失敗", out.strip(), extra={"method": "pnp-cmdlets"})


def remove_ghost(instance_id: str) -> ActionResult:
    """移除一個殘留的幽靈裝置節點。

    只該用在 Status 為 Unknown 的裝置上；呼叫端負責確認這一點。
    """
    if not is_elevated():
        return ActionResult(False, "需要系統管理員權限", "移除裝置節點需要系統管理員權限。")
    try:
        proc = _run(["pnputil", "/remove-device", instance_id])
    except (subprocess.TimeoutExpired, OSError) as exc:
        return ActionResult(False, "移除失敗", str(exc))
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode == 0:
        return ActionResult(True, "已移除幽靈裝置", output)
    return ActionResult(False, "移除失敗", f"exit {proc.returncode}: {output}")


def wait_until_present(instance_id: str, timeout: float = 15.0) -> bool:
    """重置後等待裝置重新上線。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for dev in list_devices():
            if dev.instance_id.upper() == instance_id.upper() and dev.is_present:
                return True
        time.sleep(0.5)
    return False


def snapshot(preferred_instance_id: str = "") -> dict[str, Any]:
    """給 UI 用的一次性完整狀態。"""
    devices = list_devices()
    primary = find_primary_device(preferred_instance_id)
    ghosts = [d.to_dict() for d in devices if d.is_ghost]
    info = driver_info(primary.instance_id) if primary else {}
    return {
        "primary": primary.to_dict() if primary else None,
        "driver": info,
        "devices": [d.to_dict() for d in devices],
        "ghost_count": len(ghosts),
        "ghosts": ghosts,
        "uses_focusrite_driver": uses_focusrite_driver(devices),
        "elevated": is_elevated(),
    }
