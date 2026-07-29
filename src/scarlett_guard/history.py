"""事件紀錄與統計。

用 JSON Lines 保存，方便事後直接用文字工具或 pandas 分析
「到底多久壞一次、是不是真的和 CPU 負載相關」。
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from .paths import HISTORY_PATH

_MAX_LINES = 5000


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

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
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

    def resets_since(self, seconds: float) -> int:
        cutoff = time.time() - seconds
        return sum(
            1
            for r in self._read_all()
            if r.get("event") in {"reset_manual", "reset_hotkey", "reset_auto", "reset_tray"}
            and r.get("ts", 0) >= cutoff
            and r.get("ok", True)
        )

    def stats(self) -> dict[str, Any]:
        records = self._read_all()
        resets = [
            r
            for r in records
            if r.get("event", "").startswith("reset_") and r.get("ok", True)
        ]
        anomalies = [r for r in records if r.get("event") == "anomaly"]

        now = time.time()
        day = 86400.0
        last_reset = resets[-1] if resets else None

        # 平均間隔：只有兩次以上才有意義
        mean_gap_hours = None
        if len(resets) >= 2:
            timestamps = sorted(r.get("ts", 0.0) for r in resets)
            gaps = [b - a for a, b in zip(timestamps, timestamps[1:]) if b > a]
            if gaps:
                mean_gap_hours = round(sum(gaps) / len(gaps) / 3600.0, 1)

        by_reason: dict[str, int] = {}
        for rec in anomalies:
            reason = str(rec.get("reason", "unknown"))
            by_reason[reason] = by_reason.get(reason, 0) + 1

        return {
            "total_resets": len(resets),
            "resets_24h": sum(1 for r in resets if now - r.get("ts", 0) < day),
            "resets_7d": sum(1 for r in resets if now - r.get("ts", 0) < 7 * day),
            "total_anomalies": len(anomalies),
            "anomalies_by_reason": by_reason,
            "mean_gap_hours": mean_gap_hours,
            "last_reset_iso": last_reset.get("iso") if last_reset else None,
            "last_reset_ago": _humanise(now - last_reset["ts"]) if last_reset else None,
        }


def _humanise(seconds: float) -> str:
    delta = timedelta(seconds=max(0, int(seconds)))
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes = rem // 60
    if days:
        return f"{days} 天前"
    if hours:
        return f"{hours} 小時前"
    if minutes:
        return f"{minutes} 分鐘前"
    return "剛剛"
