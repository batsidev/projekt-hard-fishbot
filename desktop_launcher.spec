# -*- mode: python ; coding: utf-8 -*-

"""PyInstaller build spec for a standalone Fisher desktop launcher.

Build with:
    pyinstaller --noconfirm desktop_launcher.spec

The spec bundles fisher.py, the task_scheduler/utils packages, and the media
images so the generated executable can run without the source project folder.
"""

from PyInstaller.utils.hooks import collect_submodules


hiddenimports = (
    collect_submodules("task_scheduler")
    + collect_submodules("utils")
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
