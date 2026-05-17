# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    "fisher",
    "utils.keyboard",
    "task_scheduler.scheduler",
    "task_scheduler.message_queue_handler",
    "pyscreeze",
    "PIL",
    "PIL.Image",
    "PIL.ImageGrab",
    "pydirectinput",
]

hiddenimports += collect_submodules("utils")
hiddenimports += collect_submodules("task_scheduler")
hiddenimports += collect_submodules("pyscreeze")
hiddenimports += collect_submodules("PIL")
hiddenimports += collect_submodules("pyautogui")
hiddenimports += collect_submodules("pydirectinput")

a = Analysis(
    ["desktop_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("media", "media"),
        ("fisher.py", "."),
        ("utils", "utils"),
        ("task_scheduler", "task_scheduler"),
    ],
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
