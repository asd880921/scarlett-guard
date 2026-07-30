"""檢查 GitHub 上有沒有新版本。

只讀不裝：執行中的 exe 沒辦法安全地覆蓋自己，所以這裡只負責告訴使用者
「有新版了」並開啟下載頁，實際更新由使用者自己解壓覆蓋。

查不到就安靜跳過。離線、GitHub 限流、還沒有任何 release，
這些都不該讓程式開不起來或跳出錯誤 —— 使用者開這個程式是為了切換驅動，
不是為了看更新檢查的錯誤訊息。
"""
from __future__ import annotations

import json
import subprocess
import threading
import urllib.request
from typing import Any, Callable

from .paths import app_version

GITHUB_REPO = "asd880921/scarlett-guard"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"
_LATEST_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

_TIMEOUT = 6.0
_CREATE_NO_WINDOW = 0x08000000


def parse_version(text: str) -> tuple[int, ...]:
    """把 'v2.1.0' 轉成 (2, 1, 0) 方便比大小。

    非數字的片段（例如 '1.0.0-beta' 的 '0-beta'）只取前面的數字部分，
    解析不出來就當 0 —— 版本比較失準頂多是少提示一次，不該讓它拋例外。
    """
    parts: list[int] = []
    for chunk in (text or "").strip().lstrip("vV").split(".")[:4]:
        digits = ""
        for ch in chunk:
            if not ch.isdigit():
                break
            digits += ch
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


class UpdateChecker:
    """啟動時在背景查一次，結果放著給 UI 取用。"""

    def __init__(self, on_done: Callable[[dict[str, Any]], None] | None = None) -> None:
        self._on_done = on_done
        self._lock = threading.Lock()
        self._result: dict[str, Any] = {
            "checked": False,
            "available": False,
            "current": app_version(),
            "latest": "",
            "url": RELEASES_PAGE,
        }

    @property
    def result(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._result)

    def start(self) -> None:
        threading.Thread(target=self._run, name="update-check", daemon=True).start()

    def _run(self) -> None:
        current = app_version()
        latest = ""
        url = RELEASES_PAGE
        try:
            request = urllib.request.Request(
                _LATEST_API,
                headers={
                    "User-Agent": f"ScarlettGuard/{current}",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(request, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = str(data.get("tag_name") or "").strip()
            url = str(data.get("html_url") or RELEASES_PAGE)
        except Exception:
            pass  # 離線 / 限流 / 沒有 release —— 一律當作沒有新版

        with self._lock:
            self._result.update(
                checked=True,
                current=current,
                latest=latest.lstrip("vV"),
                url=url,
                available=bool(latest) and parse_version(latest) > parse_version(current),
            )
            snapshot = dict(self._result)

        if self._on_done is not None:
            try:
                self._on_done(snapshot)
            except Exception:
                pass


def open_release_page(url: str = "") -> bool:
    """在瀏覽器開啟下載頁。

    走 explorer.exe 而不是 webbrowser：這個程式通常以系統管理員身分執行，
    直接開瀏覽器會讓瀏覽器也繼承高權限，那是不必要的風險。
    explorer 會用登入使用者的權限開，等同於在檔案總管裡點連結。
    """
    target = url or RELEASES_PAGE
    if not target.startswith(("http://", "https://")):
        return False
    try:
        subprocess.Popen(["explorer.exe", target], creationflags=_CREATE_NO_WINDOW)
        return True
    except OSError:
        pass
    try:
        import webbrowser

        return bool(webbrowser.open(target))
    except Exception:
        return False
