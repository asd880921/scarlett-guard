"""UAC 提權。

`pnputil /restart-device` 需要系統管理員權限。程式在未提權時仍然可以開啟，
只是重置按鈕會停用並顯示提示，讓使用者自己決定要不要提權，
而不是一啟動就丟一個沒有前後文的 UAC 對話框。
"""
from __future__ import annotations

import ctypes
import sys

from .paths import launch_target, project_root


def is_elevated() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> tuple[bool, str]:
    """以系統管理員身分重新啟動自己。成功的話呼叫端應該立刻結束。"""
    if is_elevated():
        return False, "目前已經是系統管理員權限"

    exe, prefix = launch_target()
    args = prefix + [a for a in sys.argv[1:] if a != "--elevated"]
    params = " ".join(f'"{a}"' for a in args)

    try:
        # 大於 32 代表 ShellExecute 成功
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, str(project_root()), 1
        )
    except Exception as exc:
        return False, f"提權失敗：{exc}"

    if int(result) > 32:
        return True, "正在以系統管理員身分重新啟動…"
    if int(result) == 1223:  # ERROR_CANCELLED
        return False, "已取消提權"
    return False, f"提權失敗（代碼 {result}）"
