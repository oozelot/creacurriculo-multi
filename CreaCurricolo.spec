# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

hiddenimports = ['openpyxl']
if sys.platform == 'win32':
    hiddenimports.extend(['pythoncom', 'pywintypes', 'win32com', 'win32com.client'])
file_ricevuti = [
    (str(percorso), 'ADMIN/file_ricevuti')
    for percorso in Path('ADMIN/file_ricevuti').glob('*.ini')
]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('do_not_use', 'do_not_use'),
        *file_ricevuti,
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
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='CreaCurricoloMulti',
)
