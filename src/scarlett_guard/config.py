"""設定的讀寫與預設值。"""
from __future__ import annotations

import copy
import json
import threading
from typing import Any

from .paths import CONFIG_PATH

DEFAULTS: dict[str, Any] = {
    # --- 介面 ---
    # "auto" 跟隨系統地區設定；也可指定 zh-Hant / zh-Hans / en
    "language": "auto",
    # --- 裝置 ---
    # 空字串代表「自動偵測」（抓第一個 Focusrite VID_1235 裝置）
    "device_instance_id": "",
    # --- 驅動模式切換 ---
    # 空字串 = 自動從 driver store 找 focusritecustom.inf。
    # 只有在自動偵測失敗時才需要手動指定。
    "focusrite_inf_path": "",
    # --- 熱鍵 ---
    "hotkey_enabled": True,
    "hotkey": "<ctrl>+<alt>+r",
    # --- 一般 ---
    "close_to_tray": True,
    "notify_on_reset": True,
    # 下面兩個是等裝置安定的秒數。刻意不放進 UI —— 預設值已經實測夠用，
    # 真的需要調整的人可以直接改 config.json。
    "post_reset_settle_seconds": 3.0,
    "mode_settle_seconds": 2.0,
}


class Config:
    """執行緒安全的設定容器，任何修改都立即寫回磁碟。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self) -> None:
        if not CONFIG_PATH.exists():
            self.save()
            return
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # 設定檔壞掉不該讓程式起不來，直接回到預設值
            return
        with self._lock:
            for key, value in raw.items():
                # 不認識的鍵一律忽略 —— 舊版留下的設定會自然被淘汰
                if key in DEFAULTS:
                    self._data[key] = value

    def save(self) -> None:
        with self._lock:
            snapshot = copy.deepcopy(self._data)
        try:
            CONFIG_PATH.write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        if key not in DEFAULTS:
            raise KeyError(f"未知的設定項目: {key}")
        with self._lock:
            self._data[key] = value
        self.save()

    def update(self, values: dict[str, Any]) -> None:
        with self._lock:
            for key, value in values.items():
                if key in DEFAULTS:
                    self._data[key] = value
        self.save()

    def reset_to_defaults(self) -> None:
        with self._lock:
            self._data = copy.deepcopy(DEFAULTS)
        self.save()

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._data)
