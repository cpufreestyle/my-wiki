# -*- mode: python ; coding: utf-8 -*-

import os

# 收集 shared-wiki 模块目录，打包时一并包含
SHARED_DIR = os.path.join(os.path.dirname(os.path.abspath('wiki_app.py')), 'modules', 'shared-wiki')
BASE_DIR = os.path.dirname(os.path.abspath('wiki_app.py'))

a = Analysis(
    ['wiki_app.py'],
    pathex=[],
    binaries=[],
    datas=[(SHARED_DIR, 'modules/shared-wiki'),
           (os.path.join(BASE_DIR, 'icon.ico'), '.'),
           (os.path.join(BASE_DIR, 'assets', 'AppIcon.icns'), 'assets')],
    hiddenimports=['wiki_core', 'agent_registry', 'obsidian_bridge', 'mcp_server',
                   'yaml', 'watchdog', 'watchdog.observers', 'watchdog.events'],
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
    name='MyWiki',
    icon='assets/AppIcon.icns',
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
