"""開機自動啟動。

用工作排程器而不是 Run 登錄機碼，因為本程式需要系統管理員權限；
只有排程工作的 /RL HIGHEST 能在登入時直接以高權限啟動而不跳 UAC。
"""
from __future__ import annotations

import locale
import subprocess

from .i18n import t
from .paths import launch_target

TASK_NAME = "ScarlettGuard"
_CREATE_NO_WINDOW = 0x08000000
_ENCODING = locale.getpreferredencoding(False) or "utf-8"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        timeout=30,
        creationflags=_CREATE_NO_WINDOW,
        text=True,
        encoding=_ENCODING,
        errors="replace",
    )


def _launch_command() -> str:
    exe, prefix = launch_target()
    parts = [exe, *prefix, "--tray"]
    return " ".join(f'"{p}"' for p in parts)


def is_enabled() -> bool:
    try:
        proc = _run(["schtasks", "/Query", "/TN", TASK_NAME])
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def enable() -> tuple[bool, str]:
    try:
        proc = _run(
            [
                "schtasks",
                "/Create",
                "/TN",
                TASK_NAME,
                "/TR",
                _launch_command(),
                "/SC",
                "ONLOGON",
                "/RL",
                "HIGHEST",
                "/F",
            ]
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, t("auto.enabled")
    detail = (proc.stderr or proc.stdout or "").strip()
    return False, t("auto.enablefail", detail=detail)


def disable() -> tuple[bool, str]:
    try:
        proc = _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, t("auto.disabled")
    detail = (proc.stderr or proc.stdout or "").strip()
    return False, t("auto.disablefail", detail=detail)
