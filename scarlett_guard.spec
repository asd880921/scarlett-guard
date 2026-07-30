# -*- mode: python ; coding: utf-8 -*-
"""Scarlett Guard — PyInstaller 打包設定（onedir）。

onedir 而不是單一 exe：啟動不需要每次解壓到暫存目錄，冷啟動快很多，
而且 WebView2 對從暫存目錄載入的本機檔案有時會有存取問題。
整個資料夾壓成 scarlett-guard.zip 交付。
"""

from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = [
    ('src/scarlett_guard/ui', 'scarlett_guard/ui'),   # HTML / CSS / JS 介面
    ('VERSION', '.'),                                  # 版本號單一來源
]
binaries = []

hiddenimports = [
    # pywebview 走 WebView2；後端是動態選的，掃不到
    'webview.platforms.edgechromium',
    # pystray 與 pynput 都在 import 時才決定後端
    'pystray._win32',
    'pynput.keyboard._win32',
    'pynput.mouse._win32',
]

# 這幾個套件會動態載入子模組，只列 hiddenimport 會漏
for pkg in ('webview', 'pystray', 'pynput', 'PIL', 'clr_loader', 'pythonnet'):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ['run.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # pywebview 用 WebView2，這些 GUI 後端一個都不需要
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'sip', 'shiboken2', 'shiboken6',
        'tkinter', '_tkinter',
        # 沒用到卻常被間接拉進來的大套件
        'numpy', 'scipy', 'pandas', 'matplotlib', 'cv2',
        'cryptography', 'IPython', 'notebook', 'pytest', 'setuptools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Scarlett Guard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,          # 視窗程式，不要黑色主控台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Scarlett Guard',
)
