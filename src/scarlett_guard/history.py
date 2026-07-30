"""事件紀錄。

用 JSON Lines 保存，切換或重置失敗時可以事後回溯到底發生了什麼 ——
UI 上的 toast 一閃就沒了，沒有這個檔案就什麼都查不到。
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from typing import Any

from .paths import HISTORY_PATH

_MAX_LINES = 2000


class History:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def log(self, event: str, **fields: Any) -> dict[str, Any]:
        record = {
            "ts": time.time(),
            "iso": datetime.now().astimezone().isoformat(timespec="seconds"),
            "event": event,
            **fields,
        }
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            try:
                with HISTORY_PATH.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass
        return record

    def _read_all(self) -> list[dict[str, Any]]:
        if not HISTORY_PATH.exists():
            return []
        records: list[dict[str, Any]] = []
        try:
            with HISTORY_PATH.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        return records

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        return list(reversed(self._read_all()[-limit:]))

    def clear(self) -> None:
        with self._lock:
            try:
                HISTORY_PATH.write_text("", encoding="utf-8")
            except OSError:
                pass

    def trim(self) -> None:
        """避免紀錄檔無限成長。"""
        records = self._read_all()
        if len(records) <= _MAX_LINES:
            return
        keep = records[-_MAX_LINES:]
        with self._lock:
            try:
                with HISTORY_PATH.open("w", encoding="utf-8") as fh:
                    for rec in keep:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except OSError:
                pass
