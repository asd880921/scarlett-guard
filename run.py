#!/usr/bin/env python
"""Scarlett Guard 啟動器。

直接執行這個檔案即可，不需要先安裝套件：
    .venv\\Scripts\\python.exe run.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 打包後套件是由凍結的匯入器提供的，src/ 並不存在，插進去只會多一個死路徑
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from scarlett_guard.main import main  # noqa: E402

if __name__ == "__main__":
    main()
