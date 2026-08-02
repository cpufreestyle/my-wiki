# -*- mode: python ; coding: utf-8 -*-

import os
import glob

# 注意：不再把整个 modules/shared-wiki 打进签名包。该目录含运行时会写入的
# registry.json 等可变数据，打进签名 app 会导致代码签名密封失效
# （"a sealed resource is missing or invalid"），双击被 Gatekeeper 拦截。
# 改为运行时按需从源码目录/用户目录加载（见 wiki_app 的 frozen 回退逻辑）。
BASE_DIR = os.path.dirname(os.path.abspath('wiki_app.py'))

# ===== 代码签名 / 公证配置（可选）=====
# 默认留空 None：不签名，双击仍可能被 Gatekeeper 拦截（需右键"打开"或 run-mywiki.command）。
# 填入开发者证书后，PyInstaller 会在打包时自动签名；再配合 xcrun notarytool 即可公证，
# 之后他人双击可正常打开。
# 查看本机可用证书：  security find-identity -v -p codesigning
# 典型值：           "Developer ID Application: Your Name (TEAMID1234)"
codesign_identity = None

# 权限文件（hardened runtime，公证必需）。仅在 codesign_identity 非空时由 PyInstaller 使用；
# 留空 None 表示不指定。已在仓库内置 MyWiki.entitlements，可直接使用。
entitlements_file = os.path.join(BASE_DIR, 'MyWiki.entitlements') if codesign_identity else None

# 网页版相关资源：web 服务器、检索/图谱后端、所有 *_web.html 页面与门户页
WEB_PY = [(os.path.join(BASE_DIR, 'web_server.py'), '.'),
          (os.path.join(BASE_DIR, 'rag.py'), '.'),
          (os.path.join(BASE_DIR, 'voice_mood.py'), '.')]
WEB_HTML = [(f, '.') for f in glob.glob(os.path.join(BASE_DIR, '*_web.html'))]
WEB_HTML.append((os.path.join(BASE_DIR, 'index.html'), '.'))
# 知识图谱数据也一并打包，使图谱页开箱即用
KG = (os.path.join(BASE_DIR, 'knowledge_graph.json'), '.')

a = Analysis(
    ['wiki_app.py'],
    pathex=[],
    binaries=[],
    datas=[(os.path.join(BASE_DIR, 'icon.ico'), '.'),
           (os.path.join(BASE_DIR, 'assets', 'AppIcon.icns'), 'assets')]
          + WEB_PY + WEB_HTML + [KG],
    hiddenimports=['wiki_core', 'agent_registry', 'obsidian_bridge', 'mcp_server',
                   'yaml', 'watchdog', 'watchdog.observers', 'watchdog.events',
                   'rag', 'voice_mood'],
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
    [],  # binaries/datas 交给 COLLECT，避免 EXE 直接落盘到 dist/MyWiki
    exclude_binaries=True,
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
    argv_emulation=True,
    target_arch=None,
    codesign_identity=codesign_identity,
    entitlements_file=entitlements_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MyWiki',
)

app = BUNDLE(
    coll,
    name='MyWiki.app',
    icon='assets/AppIcon.icns',
    bundle_identifier='com.mywiki.app',
    version='2.9.0',
    codesign_identity=codesign_identity,
    entitlements_file=entitlements_file,
    info_plist={
        'CFBundleShortVersionString': '2.9.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'CFBundleDisplayName': 'MyWiki',
        'CFBundleName': 'MyWiki',
    },
)
