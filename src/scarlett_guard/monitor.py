"""音訊異常偵測。

我們監聽 Scarlett 的「錄音端點」而不是播放的 loopback，這是刻意的：
loopback 拿到的是 Windows 混音器的軟體輸出，驅動掛掉時它往往照樣送出正常資料；
而錄音端點拿到的是 ADC 的真實取樣，能反映硬體那一側到底還活著沒有。

三個偵測器，各自獨立可關：

  stall    音訊回呼停止進來 → stream 時鐘凍結。這是最可靠的訊號。
  silence  連續「位元級全零」→ 類比 ADC 不可能長時間輸出精確的 0
           （永遠有噪音底），所以這幾乎必然代表 stream 已死。
  noise    音量高出學習到的噪音底一大截，且過零率極高 → 電流音／白噪的特徵。
           人聲與樂器的過零率遠低於此，所以能區分開。

必須誠實說明：這些是啟發式規則，不是保證。noise 偵測器最容易誤判
（例如錄製 hi-hat、破音吉他或真的白噪音素材）。因此預設全部關閉，
並提供即時儀表讓使用者自己校準門檻。
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

try:
    import sounddevice as sd

    _SD_ERROR = ""
except Exception as exc:  # pragma: no cover - 只有缺 PortAudio 時才會走到
    sd = None  # type: ignore[assignment]
    _SD_ERROR = str(exc)


_EPS = 1e-12


@dataclass
class Anomaly:
    reason: str          # stall | silence | noise
    label: str           # 給人看的說明
    detail: str
    metrics: dict[str, Any]


def list_input_devices() -> list[dict[str, Any]]:
    """列出可用的錄音裝置，Focusrite 的排在最前面。"""
    if sd is None:
        return []
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception:
        return []

    result: list[dict[str, Any]] = []
    for index, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) < 1:
            continue
        name = str(dev.get("name", ""))
        api = ""
        try:
            api = str(hostapis[dev["hostapi"]]["name"])
        except (IndexError, KeyError, TypeError):
            pass
        result.append(
            {
                "index": index,
                "name": name,
                "hostapi": api,
                "channels": dev.get("max_input_channels", 0),
                "default_samplerate": int(dev.get("default_samplerate", 0) or 0),
                "is_focusrite": _looks_like_focusrite(name),
            }
        )
    # 同一個實體裝置會在 MME / DirectSound / WASAPI / WDM-KS 各出現一次。
    # WASAPI 最貼近硬體且名稱不會被截斷，所以自動選擇時優先它。
    result.sort(key=lambda d: (not d["is_focusrite"], _hostapi_rank(d["hostapi"]), d["name"]))
    return result


_HOSTAPI_PREFERENCE = ("wasapi", "wdm-ks", "directsound", "mme")


def _hostapi_rank(hostapi: str) -> int:
    lowered = (hostapi or "").lower()
    for rank, name in enumerate(_HOSTAPI_PREFERENCE):
        if name in lowered:
            return rank
    return len(_HOSTAPI_PREFERENCE)


def _looks_like_focusrite(name: str) -> bool:
    lowered = name.lower()
    return "focusrite" in lowered or "scarlett" in lowered


def find_default_input() -> dict[str, Any] | None:
    for dev in list_input_devices():
        if dev["is_focusrite"]:
            return dev
    return None


class AudioMonitor:
    """在背景執行的音訊看門狗。"""

    def __init__(
        self,
        config,
        on_anomaly: Callable[[Anomaly], None],
        on_state_change: Callable[[], None] | None = None,
    ) -> None:
        self._config = config
        self._on_anomaly = on_anomaly
        self._on_state_change = on_state_change or (lambda: None)

        self._lock = threading.Lock()
        self._stream: Any = None
        self._watchdog: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._paused = threading.Event()

        # 由音訊回呼更新、由看門狗讀取的狀態
        self._last_callback_at = 0.0
        self._rms_db = -120.0
        self._peak_db = -120.0
        self._zcr = 0.0
        self._baseline_db: float | None = None
        self._silence_since: float | None = None
        self._noise_since: float | None = None
        self._history: deque[float] = deque(maxlen=180)  # 給 UI 畫波形

        self._error = ""
        self._device_name = ""
        self._running = False

    # ------------------------------------------------------------------
    # 生命週期
    # ------------------------------------------------------------------
    def start(self) -> tuple[bool, str]:
        with self._lock:
            if self._running:
                return True, "已在執行"
            if sd is None:
                self._error = f"sounddevice 無法載入：{_SD_ERROR}"
                return False, self._error

            device = self._resolve_device()
            if device is None:
                self._error = "找不到 Focusrite 錄音裝置，請確認裝置已連接。"
                return False, self._error

            samplerate = int(self._config.get("monitor_samplerate") or 0)
            if not samplerate:
                samplerate = device.get("default_samplerate") or 48000
            # 0 = 交給 PortAudio 挑選最合適的區塊大小
            blocksize = max(0, int(self._config.get("monitor_blocksize", 1024) or 0))
            # Solo 的兩個輸入分別是麥克風與樂器，兩軌都要看，回呼裡再取平均
            channels = max(1, min(2, int(device.get("channels", 1) or 1)))

            try:
                self._stream = sd.InputStream(
                    device=device["index"],
                    channels=channels,
                    samplerate=samplerate,
                    blocksize=blocksize,
                    dtype="float32",
                    callback=self._audio_callback,
                )
                self._stream.start()
            except Exception as exc:
                self._stream = None
                self._error = (
                    f"無法開啟錄音串流：{exc}\n"
                    "若 DAW 正以 ASIO 獨佔此裝置，監聽功能會被擋下，這是正常的。"
                )
                return False, self._error

            self._device_name = device["name"]
            self._error = ""
            self._running = True
            self._reset_detector_state()
            self._stop_event.clear()
            self._paused.clear()

        self._watchdog = threading.Thread(
            target=self._watchdog_loop, name="monitor-watchdog", daemon=True
        )
        self._watchdog.start()
        self._on_state_change()
        return True, f"已開始監聽「{self._device_name}」"

    def stop(self) -> None:
        with self._lock:
            self._running = False
        self._stop_event.set()
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        watchdog = self._watchdog
        self._watchdog = None
        if watchdog is not None and watchdog.is_alive():
            watchdog.join(timeout=2.0)
        self._on_state_change()

    def pause(self) -> None:
        """重置裝置期間暫停偵測，否則一定會誤判成 stall。"""
        self._paused.set()

    def resume(self) -> None:
        self._reset_detector_state()
        self._paused.clear()

    @property
    def running(self) -> bool:
        return self._running

    def _resolve_device(self) -> dict[str, Any] | None:
        """決定要監聽哪一個錄音裝置。

        使用者指定的名稱優先；找不到就退回自動挑選 Focusrite，
        因為裝置重新列舉後 PortAudio 的索引與名稱後綴都可能改變。
        """
        devices = list_input_devices()
        if not devices:
            return None

        wanted = (self._config.get("monitor_input_device") or "").strip()
        if wanted:
            for dev in devices:
                if dev["name"] == wanted:
                    return dev
            for dev in devices:
                if wanted.lower() in dev["name"].lower():
                    return dev

        for dev in devices:
            if dev["is_focusrite"]:
                return dev
        return None

    # ------------------------------------------------------------------
    # 音訊路徑
    # ------------------------------------------------------------------
    def _audio_callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        now = time.monotonic()
        try:
            block = np.asarray(indata, dtype=np.float32)
            if block.ndim > 1:
                block = block.mean(axis=1)
            if block.size == 0:
                return

            rms = float(np.sqrt(np.mean(np.square(block))))
            peak = float(np.max(np.abs(block)))
            # 過零率：雜訊／電流音接近隨機，過零率遠高於任何樂音
            zcr = float(np.mean(np.abs(np.diff(np.signbit(block).astype(np.int8)))))

            rms_db = 20.0 * np.log10(max(rms, _EPS))
            peak_db = 20.0 * np.log10(max(peak, _EPS))
        except Exception:
            return

        self._last_callback_at = now
        self._rms_db = rms_db
        self._peak_db = peak_db
        self._zcr = zcr
        self._history.append(round(rms_db, 1))

    # ------------------------------------------------------------------
    # 偵測邏輯
    # ------------------------------------------------------------------
    def _reset_detector_state(self) -> None:
        self._last_callback_at = time.monotonic()
        self._silence_since = None
        self._noise_since = None
        self._baseline_db = None

    def _watchdog_loop(self) -> None:
        # 給串流一點時間穩定下來再開始判斷
        time.sleep(1.0)
        while not self._stop_event.wait(0.2):
            if self._paused.is_set():
                continue
            try:
                anomaly = self._evaluate()
            except Exception:
                continue
            if anomaly is not None:
                self._reset_detector_state()
                self._on_anomaly(anomaly)
                # 交給上層處理（可能會重置裝置），先停一下避免連環觸發
                time.sleep(2.0)

    def _evaluate(self) -> Anomaly | None:
        cfg = self._config
        now = time.monotonic()
        rms_db = self._rms_db
        zcr = self._zcr

        # --- stall：回呼停了 ---
        if cfg.get("detect_stall"):
            gap = now - self._last_callback_at
            if gap > float(cfg.get("stall_seconds", 2.0)):
                return Anomaly(
                    "stall",
                    "音訊串流停止回應",
                    f"已有 {gap:.1f} 秒沒有收到音訊資料，driver 的 stream 時鐘可能已凍結。",
                    {"gap_seconds": round(gap, 2)},
                )

        # --- silence：位元級全零 ---
        if cfg.get("detect_silence"):
            floor = float(cfg.get("silence_floor_db", -90.0))
            if rms_db <= floor:
                if self._silence_since is None:
                    self._silence_since = now
                elif now - self._silence_since > float(cfg.get("silence_seconds", 8.0)):
                    held = now - self._silence_since
                    return Anomaly(
                        "silence",
                        "輸入訊號完全消失",
                        f"連續 {held:.1f} 秒偵測到數位靜音（{rms_db:.0f} dBFS）。"
                        "類比 ADC 正常運作時不可能長時間輸出精確的零值。",
                        {"rms_db": round(rms_db, 1), "held_seconds": round(held, 1)},
                    )
            else:
                self._silence_since = None

        # --- noise：音量高出噪音底且過零率極高 ---
        if cfg.get("detect_noise"):
            margin = float(cfg.get("noise_margin_db", 18.0))
            zcr_threshold = float(cfg.get("noise_zcr", 0.30))
            suspicious = (
                self._baseline_db is not None
                and rms_db > self._baseline_db + margin
                and zcr > zcr_threshold
            )
            if suspicious:
                if self._noise_since is None:
                    self._noise_since = now
                elif now - self._noise_since > float(cfg.get("noise_seconds", 1.5)):
                    held = now - self._noise_since
                    return Anomaly(
                        "noise",
                        "偵測到疑似電流音",
                        f"訊號高出噪音底 {rms_db - (self._baseline_db or 0):.0f} dB "
                        f"且過零率達 {zcr:.2f}，持續 {held:.1f} 秒。",
                        {
                            "rms_db": round(rms_db, 1),
                            "baseline_db": round(self._baseline_db or 0.0, 1),
                            "zcr": round(zcr, 3),
                        },
                    )
            else:
                self._noise_since = None
                # 只在「安靜且不可疑」的時候更新噪音底，避免把電流音學進基準
                if rms_db > float(cfg.get("silence_floor_db", -90.0)):
                    if self._baseline_db is None:
                        self._baseline_db = rms_db
                    else:
                        self._baseline_db = 0.98 * self._baseline_db + 0.02 * rms_db
        return None

    # ------------------------------------------------------------------
    # 給 UI 的即時資料
    # ------------------------------------------------------------------
    def telemetry(self) -> dict[str, Any]:
        now = time.monotonic()
        gap = now - self._last_callback_at if self._running else 0.0
        return {
            "running": self._running,
            "paused": self._paused.is_set(),
            "device_name": self._device_name,
            "error": self._error,
            "rms_db": round(self._rms_db, 1),
            "peak_db": round(self._peak_db, 1),
            "zcr": round(self._zcr, 3),
            "baseline_db": round(self._baseline_db, 1) if self._baseline_db is not None else None,
            "callback_gap": round(gap, 2),
            "waveform": list(self._history),
            "available": sd is not None,
            "sd_error": _SD_ERROR,
        }
