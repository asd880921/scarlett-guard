"""介面一致性檢查。

UI 是 HTML + JS，沒有編譯期，所以「文案 key 打錯」或「找一個不存在的元素」
都只會讓畫面安靜地半殘 —— 開發時完全看不出來。這支腳本補上那一層檢查。

用法：
    python tools/check_ui.py

檢查項目：
  1. i18n.py 三語的 key 是否完全一致
  2. ui/i18n.js 三語的 key 是否完全一致
  3. index.html 的 data-i18n* 引用的 key 是否都存在
  4. app.js 裡 t('...') 引用的 key 是否都存在
  5. app.js 裡 $('#id') 找的元素是否都在 index.html 定義過
  6. 有沒有已定義卻沒人用的文案 key（只警告，不算失敗）

回傳碼 0 表示全部通過。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# 輸出被重導向時（CI、管線），Windows 上的 stdout 會落回系統的 ANSI 代碼頁，
# 印中文就會 UnicodeEncodeError。這裡強制 UTF-8，讓腳本不必挑執行環境。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "scarlett_guard"
UI = PKG / "ui"

failures: list[str] = []
warnings: list[str] = []


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1. 後端文案三語一致
# --------------------------------------------------------------------------
def check_backend_catalog() -> set[str]:
    sys.path.insert(0, str(PKG.parent))
    from scarlett_guard import i18n  # noqa: PLC0415

    keys = {lang: set(table) for lang, table in i18n.CATALOG.items()}
    base = keys.get(i18n.DEFAULT, set())
    for lang, ks in keys.items():
        for missing in sorted(base - ks):
            failures.append(f"i18n.py [{lang}] 缺少 {missing!r}")
        for extra in sorted(ks - base):
            failures.append(f"i18n.py [{lang}] 多出 {extra!r}")
    print(f"i18n.py         : {len(base)} keys × {len(keys)} langs")
    return base


# --------------------------------------------------------------------------
# 2. 前端文案三語一致
# --------------------------------------------------------------------------
def check_frontend_catalog() -> set[str]:
    js = read(UI / "i18n.js")
    # 語言鍵可能加引號（'zh-Hant'）也可能不加（en 是合法 JS 識別字）
    blocks = re.split(r"^    '?([A-Za-z-]+)'?: \{$", js, flags=re.M)
    tables: dict[str, set[str]] = {}
    for i in range(1, len(blocks) - 1, 2):
        tables[blocks[i]] = set(re.findall(r"^      '([^']+)':", blocks[i + 1], flags=re.M))

    if len(tables) < 2:
        failures.append(f"i18n.js 只解析到 {len(tables)} 個語言區塊：{sorted(tables)}")
        return set()

    base_lang = "zh-Hant" if "zh-Hant" in tables else sorted(tables)[0]
    base = tables[base_lang]
    for lang, ks in tables.items():
        for missing in sorted(base - ks):
            failures.append(f"i18n.js [{lang}] 缺少 {missing!r}")
        for extra in sorted(ks - base):
            failures.append(f"i18n.js [{lang}] 多出 {extra!r}")
    print(f"i18n.js         : {len(base)} keys × {len(tables)} langs")
    return base


# --------------------------------------------------------------------------
# 3–4. 引用的文案 key 都必須存在
# --------------------------------------------------------------------------
def check_key_usage(catalog: set[str]) -> set[str]:
    html = read(UI / "index.html")
    app = read(UI / "app.js")

    used: set[str] = set()
    for attr in ("data-i18n", "data-i18n-html", "data-i18n-title", "data-i18n-aria"):
        used |= set(re.findall(rf'{attr}="([^"]+)"', html))

    # \b 是必要的：少了它，createElement('div') 這種以 t 結尾的函式名也會被抓進來
    js_keys = set(re.findall(r"\bt\('([a-z][a-zA-Z0-9_.]*)'", app))
    used |= js_keys

    # 動態組出來的 key（`view.${name}.title`、`ev.${event}`）無法靜態檢查，
    # 改為驗證它們的已知前綴至少有東西存在
    for prefix in ("view.", "ev."):
        if not any(k.startswith(prefix) for k in catalog):
            failures.append(f"文案表裡沒有任何 {prefix}* 的 key，動態引用會全部落空")

    for key in sorted(used - catalog):
        failures.append(f"引用了不存在的文案 key：{key!r}")

    print(f"key 引用        : html+js 共 {len(used)} 個")
    return used


# --------------------------------------------------------------------------
# 5. DOM id 必須存在
# --------------------------------------------------------------------------
def check_dom_ids() -> None:
    html = read(UI / "index.html")
    app = read(UI / "app.js")
    defined = set(re.findall(r'id="([^"]+)"', html))
    referenced = set(re.findall(r"\$\('#([a-zA-Z0-9_-]+)'\)", app))
    for missing in sorted(referenced - defined):
        failures.append(f"app.js 找了不存在的元素 id：{missing!r}")
    print(f"DOM id          : 引用 {len(referenced)} / 定義 {len(defined)}")


# --------------------------------------------------------------------------
# 6. 沒人用的文案（警告）
# --------------------------------------------------------------------------
def check_unused(catalog: set[str], used: set[str]) -> None:
    # 動態前綴的 key 靜態掃不到，排除掉避免假警報
    dynamic = tuple(("view.", "ev."))
    unused = {k for k in catalog - used if not k.startswith(dynamic)}
    if unused:
        warnings.append(f"{len(unused)} 個文案 key 沒有被引用：{', '.join(sorted(unused))}")


def main() -> int:
    backend = check_backend_catalog()
    frontend = check_frontend_catalog()
    used = check_key_usage(frontend)
    check_dom_ids()
    check_unused(frontend, used)
    del backend  # 後端文案由 Python 直接呼叫 t()，不做靜態引用檢查

    print()
    for warning in warnings:
        print(f"[warn] {warning}")
    if failures:
        print(f"\n=== {len(failures)} 個問題 ===")
        for failure in failures:
            print(" -", failure)
        return 1
    print("=== 全部通過 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
