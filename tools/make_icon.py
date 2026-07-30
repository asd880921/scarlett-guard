"""從系統匣圖示的同一份繪製程式產生 assets/icon.ico。

刻意不另外畫一張：圖示只要有兩份來源，遲早會長得不一樣。
這裡直接 import tray._make_icon，所以 exe 圖示與系統匣圖示必然相同。

用法：
    python tools/make_icon.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scarlett_guard.tray import _make_icon  # noqa: E402

# Windows 會依顯示情境挑最接近的尺寸：工作列 32、桌面 48、檔案總管大圖示 256
SIZES = (16, 24, 32, 48, 64, 128, 256)

# "ok" 是裝置正常時系統匣顯示的樣子，也就是使用者平常看到的那一顆
BASE_STATE = "ok"


def main() -> int:
    out = ROOT / "assets" / "icon.ico"
    out.parent.mkdir(parents=True, exist_ok=True)

    # _make_icon 畫的是 64x64；先放大到最大尺寸再讓 Pillow 產生各級別，
    # 避免小尺寸直接從 64 縮下去時邊緣糊掉
    master = _make_icon(BASE_STATE).resize((256, 256), resample=1)  # LANCZOS
    master.save(out, format="ICO", sizes=[(s, s) for s in SIZES])

    print(f"已產生 {out.relative_to(ROOT)}  ({out.stat().st_size:,} bytes)")
    print(f"尺寸：{', '.join(f'{s}x{s}' for s in SIZES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
