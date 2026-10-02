# -*- mode: python ; coding: utf-8 -*-

import sys

# Avoid UPX-packed binaries, which can trigger antivirus heuristics.
hiddenimports = ['openpyxl']
if sys.platform == 'win32':
    hiddenimports.extend(['pythoncom', 'pywintypes', 'win32com', 'win32com.client'])


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('do_not_use', 'do_not_use'),
        ('codici competenze.pdf', '.'),
        ('curricolobak.db', '.'),
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
    [],
    exclude_binaries=True,
    name='CreaCurricoloMulti',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CreaCurricoloMulti',
)
