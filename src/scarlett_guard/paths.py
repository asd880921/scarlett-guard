"""應用程式資料路徑與版本。

打包成 exe 之後，「程式在哪裡」「怎麼再啟動一次自己」這兩件事的答案都變了，
所以相關判斷全部集中在這裡，不散落到各個模組。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ScarlettGuard"

# PyInstaller 會設這個屬性。onedir 模式下 sys._MEIPASS 是 _internal 資料夾，
# sys.executable 則是 exe 本身。
FROZEN = bool(getattr(sys, "frozen", False))


def data_dir() -> Path:
    """%APPDATA%\\ScarlettGuard —— 設定與紀錄的存放位置。"""
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def bundle_dir() -> Path:
    """打包後的資源根目錄；開發時就是專案根目錄。"""
    if FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return package_dir().parent.parent


def ui_dir() -> Path:
    if FROZEN:
        return bundle_dir() / "scarlett_guard" / "ui"
    return package_dir() / "ui"


def project_root() -> Path:
    if FROZEN:
        return Path(sys.executable).parent
    return package_dir().parent.parent


def app_version() -> str:
    """版本號的單一來源。GitHub Actions 會核對它和 tag 是否一致。"""
    for candidate in (bundle_dir() / "VERSION", package_dir().parent.parent / "VERSION"):
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return "0.0.0"


def launch_target() -> tuple[str, list[str]]:
    """再啟動一次自己需要的 (執行檔, 前置參數)。

    打包後就是 exe 自己；開發時是 pythonw + run.py。開機自動啟動與 UAC 提權
    都要用它，寫死成 python 的話打包版會建出一個指向不存在腳本的排程工作。
    """
    if FROZEN:
        return sys.executable, []
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    launcher = project_root() / "run.py"
    return str(pythonw if pythonw.exists() else exe), [str(launcher)]


CONFIG_PATH = data_dir() / "config.json"
HISTORY_PATH = data_dir() / "history.jsonl"
LOG_PATH = data_dir() / "scarlett-guard.log"
