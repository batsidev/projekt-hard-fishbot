# -*- mode: python ; coding: utf-8 -*-

"""PyInstaller build spec for the Fisher desktop launcher.

Build on Windows from the project root with:
    pyinstaller --clean desktop_launcher.spec

The spec bundles fisher.py, local packages, template images, and the screenshot
stack used by pyautogui so the generated executable can call
pyautogui.screenshot() without missing pyscreeze/Pillow/PIL modules.
"""

from PyInstaller.utils.hooks import collect_submodules


hiddenimports = (
    collect_submodules("task_scheduler")
    + collect_submodules("utils")
    + collect_submodules("pyscreeze")
    + collect_submodules("PIL")
    + collect_submodules("pyautogui")
    + ["fisher"]
)


a = Analysis(
    ["desktop_launcher.py"],
    pathex=[],
    binaries=[],
    datas=[("media", "media")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="desktop_launcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
