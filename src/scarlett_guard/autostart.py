"""開機自動啟動。

用工作排程器而不是 Run 登錄機碼，因為本程式需要系統管理員權限；
只有排程工作的 /RL HIGHEST 能在登入時直接以高權限啟動而不跳 UAC。
"""
from __future__ import annotations

import locale
import subprocess
from pathlib import Path

from .paths import pythonw_exe, project_root

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
    exe = pythonw_exe()
    script = Path(project_root()) / "run.py"
    return f'"{exe}" "{script}" --tray'


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
        return True, "已設定為開機自動啟動（以系統管理員權限）"
    detail = (proc.stderr or proc.stdout or "").strip()
    return False, f"設定失敗：{detail}"


def disable() -> tuple[bool, str]:
    try:
        proc = _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, "已取消開機自動啟動"
    detail = (proc.stderr or proc.stdout or "").strip()
    return False, f"取消失敗：{detail}"
