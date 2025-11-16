# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['d:\\virtualspace\\spotifyexe\\spotify_app\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('d:\\virtualspace\\spotifyexe\\spotify_app\\resources\\fonts\\Montserrat-Black.ttf', 'resources/fonts/'), ('d:\\virtualspace\\spotifyexe\\spotify_app\\resources\\style.qss', 'resources/'), ('D:\\virtualspace\\spotifyexe\\lib\\site-packages\\uiautomator2', 'uiautomator2'), ('d:\\virtualspace\\spotifyexe\\spotify_app\\resources\\app_icon.ico', 'resources/')],
    hiddenimports=['uiautomator2', 'PIL', 'pillow', 'wrapt', 'packaging.version', 'packaging.specifiers', 'packaging.requirements', 'ui.main_window', 'ui.settings_dialog'],
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
    name='Music Automation2',
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
    icon=['d:\\virtualspace\\spotifyexe\\spotify_app\\resources\\app_icon.ico'],
)
