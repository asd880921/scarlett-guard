"""從系統匣圖示的同一份繪製程式產生 assets/icon.ico 與 assets/icon.png。

刻意不另外畫一張：圖示只要有兩份來源，遲早會長得不一樣。
這裡直接 import tray._make_icon，所以 exe 圖示、系統匣圖示、README 上的那張
必然相同。

兩個輸出各有用途：
  icon.ico —— 給 exe。每個尺寸都原生繪製，不是從大張縮下去的。
  icon.png —— 給 README。GitHub 對 .ico 的 <img> 支援很不一致，
               常常挑到 16x16 那一格，看起來就是一團模糊。

用法：
    python tools/make_icon.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scarlett_guard.tray import _make_icon  # noqa: E402

# Windows 會依顯示情境挑最接近的：工作列 32、桌面 48、檔案總管大圖示 256
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
PNG_SIZE = 256

# "ok" 是裝置正常時系統匣顯示的樣子，也就是使用者平常看到的那一顆
BASE_STATE = "ok"


def main() -> int:
    out_dir = ROOT / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 每一格都照該尺寸重畫，而不是畫一張再縮放
    frames = [_make_icon(BASE_STATE, size=s) for s in ICO_SIZES]
    ico = out_dir / "icon.ico"
    frames[-1].save(
        ico,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=frames[:-1],
    )

    png = out_dir / "icon.png"
    _make_icon(BASE_STATE, size=PNG_SIZE).save(png, format="PNG")

    for path in (ico, png):
        print(f"已產生 {path.relative_to(ROOT)}  ({path.stat().st_size:,} bytes)")
    print(f"ico 尺寸：{', '.join(f'{s}x{s}' for s in ICO_SIZES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
