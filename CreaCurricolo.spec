# -*- mode: python ; coding: utf-8 -*-

hiddenimports = ['openpyxl']


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('do_not_use', 'do_not_use'),
        ('codici competenze.pdf', '.'),
        ('curricolobak.db', '.'),
        ('ADMIN/file_ricevuti/cartella_vuota.txt', 'ADMIN/file_ricevuti'),
        ('ADMIN/input/cartella_vuota.txt', 'ADMIN/input'),
        ('ADMIN/output/cartella_vuota.txt', 'ADMIN/output'),
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
    console=True,
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
