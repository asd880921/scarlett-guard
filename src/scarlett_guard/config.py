"""設定的讀寫與預設值。"""
from __future__ import annotations

import copy
import json
import threading
from typing import Any

from .paths import CONFIG_PATH

DEFAULTS: dict[str, Any] = {
    # --- 裝置 ---
    # 空字串代表「自動偵測」（抓第一個 Focusrite VID_1235 裝置）
    "device_instance_id": "",
    # --- 熱鍵 ---
    "hotkey_enabled": True,
    "hotkey": "<ctrl>+<alt>+r",
    # --- 自動偵測與自動復原 ---
    "monitor_enabled": False,
    "auto_recover": False,
    # 監聽哪一個輸入裝置（空 = 自動找 Focusrite 的錄音端點）
    "monitor_input_device": "",
    # 0 = 跟隨裝置目前的預設取樣率。硬指定成裝置不支援的值會直接開不起來，
    # 所以預設交給裝置自己決定。
    "monitor_samplerate": 0,
    "monitor_blocksize": 1024,
    # 偵測器個別開關
    "detect_stall": True,
    "detect_silence": True,
    "detect_noise": True,
    # 門檻
    "stall_seconds": 2.0,          # 多久沒收到音訊回呼視為 stream 凍結
    "silence_seconds": 8.0,        # 位元級全零持續多久視為 ADC 死掉
    # 低於此值視為「數位靜音」。實測 Scarlett Solo 閒置時的噪音底約 -104 dB，
    # 所以門檻必須遠低於它 —— 真正的位元級全零會是 -240 dB（EPS 夾制後的值），
    # 而任何一個非零取樣都會把 RMS 拉到 -170 dB 以上。
    "silence_floor_db": -140.0,
    "noise_seconds": 1.5,          # 雜訊特徵需持續多久
    "noise_margin_db": 18.0,       # 高出基準噪音底多少 dB
    "noise_zcr": 0.30,             # 過零率門檻（電流音/白噪遠高於人聲）
    # 安全閥
    "cooldown_seconds": 30.0,      # 兩次自動重置之間的最短間隔
    "max_resets_per_hour": 6,      # 超過就停用自動復原，避免無限迴圈
    # --- 一般 ---
    "start_minimised": False,
    "close_to_tray": True,
    "notify_on_reset": True,
    "post_reset_settle_seconds": 3.0,
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
