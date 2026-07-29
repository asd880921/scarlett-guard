"""應用程式資料路徑。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ScarlettGuard"


def data_dir() -> Path:
    """%APPDATA%\\ScarlettGuard —— 設定與紀錄的存放位置。"""
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def ui_dir() -> Path:
    return package_dir() / "ui"


def project_root() -> Path:
    return package_dir().parent.parent


def python_exe() -> str:
    """目前直譯器（venv 內的 pythonw/python）。"""
    return sys.executable


def pythonw_exe() -> str:
    """無主控台視窗的直譯器，找不到就退回一般的。"""
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate) if candidate.exists() else str(exe)


CONFIG_PATH = data_dir() / "config.json"
HISTORY_PATH = data_dir() / "history.jsonl"
LOG_PATH = data_dir() / "scarlett-guard.log"
