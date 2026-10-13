# -*- mode: python ; coding: utf-8 -*-

import os
import glob
import re

# 版本号单一数据源是 pyproject.toml 的 [project].version，这里直接读它。
# 之前手写一份常量正是「包内 2.9.0 / README 2.10.1」漂移的来源：改版本号时只需改
# pyproject，包与 Info.plist 会自动跟上。
def _pyproject_version():
    spec_dir = globals().get('SPECPATH') or os.path.dirname(os.path.abspath('pyproject.toml'))
    with open(os.path.join(spec_dir, 'pyproject.toml'), encoding='utf-8') as fh:
        found = re.search(r'^version\s*=\s*"([^"]+)"', fh.read(), re.M)
    if not found:
        raise SystemExit('MyWiki.spec: pyproject.toml 里找不到 version')
    return found.group(1)


VERSION = _pyproject_version()

# 注意：不再把整个 modules/shared-wiki 打进签名包。该目录含运行时会写入的
# registry.json 等可变数据，打进签名 app 会导致代码签名密封失效
# （"a sealed resource is missing or invalid"），双击被 Gatekeeper 拦截。
# 改为运行时按需从源码目录/用户目录加载（见 wiki_app 的 frozen 回退逻辑）。
BASE_DIR = os.path.dirname(os.path.abspath('wiki_app.py'))


def _tree(src_root, dest_root):
    """把 src_root 整棵目录树映射为 (源文件, 目标子目录) 列表。

    用于把只读运行时资源（vendor/mediapipe 等）按原目录层级打进包，
    保持页面里 /vendor/... 的同源相对路径在 .app 内依然成立。
    """
    out = []
    for dp, _, fs in os.walk(src_root):
        rel = os.path.relpath(dp, src_root)
        dest = dest_root if rel == '.' else os.path.join(dest_root, rel)
        for f in fs:
            out.append((os.path.join(dp, f), dest))
    return out

# 面部情绪页默认背景图（assets/backgrounds/）
BACKGROUND_IMAGES = [(f, 'assets/backgrounds')
                     for f in glob.glob(os.path.join(BASE_DIR, 'assets', 'backgrounds', '*.jpg'))]

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
          (os.path.join(BASE_DIR, 'voice_mood.py'), '.'),
          (os.path.join(BASE_DIR, 'vision_segment.py'), '.'),
          (os.path.join(BASE_DIR, 'backup_snapshots.py'), '.')]
# web_server.py 以数据文件形式打包，其本地 import 不会被 PyInstaller 静态分析
# 捕获，必须逐个列进 datas，否则打包版对应接口静默降级（如 /api/qa 无 llm_qa）。
WEB_PY += [(os.path.join(BASE_DIR, 'llm_qa.py'), '.'),
           (os.path.join(BASE_DIR, 'face_mood.py'), '.'),
           (os.path.join(BASE_DIR, 'vision_face_mood.py'), '.'),
           (os.path.join(BASE_DIR, 'wiki_paths.py'), '.'),
           (os.path.join(BASE_DIR, 'wiki_data.py'), '.'),
           (os.path.join(BASE_DIR, 'wiki_i18n.py'), '.')]
WEB_HTML = [(f, '.') for f in glob.glob(os.path.join(BASE_DIR, '*_web.html'))]
WEB_HTML.append((os.path.join(BASE_DIR, 'index.html'), '.'))
# 共享网页资源：theme.js（深浅色）+ apple-ui.css（Apple 皮肤）。
# 所有 *_web.html 都 <link href="assets/web/apple-ui.css">，漏打则打包版全部裸样式。
WEB_THEME = [(f, 'assets/web')
             for f in glob.glob(os.path.join(BASE_DIR, 'assets', 'web', '*'))]
# 语音输入共享脚本 voice-controller.js（根目录，4 个页面同源引用）
WEB_VOICE = [(os.path.join(BASE_DIR, 'voice-controller.js'), '.')]
# 面部关键点模型：face_mood.py 默认读 models/face_landmarker.task。
# 打包版沙箱/离线时不能依赖运行期下载，必须内置这份 ~3.6MB 模型。
MODEL_HINT = [(f, 'models')
              for f in glob.glob(os.path.join(BASE_DIR, 'models', '*.task'))]
# MediaPipe 前端运行时（face_mood_web.html 同源加载 /vendor/mediapipe/*）。
# 与 AGENTS.md「vendor/mediapipe 只增不改」一致：整体作为只读资源打包。
VENDOR_MP = _tree(os.path.join(BASE_DIR, 'vendor'), 'vendor')
# 知识图谱数据也一并打包，使图谱页开箱即用
KG = (os.path.join(BASE_DIR, 'knowledge_graph.json'), '.')

# shared-wiki 源码以只读资源打包；运行时（wiki_tabs_share._resolve_shared_dir）
# 首次使用会拷贝到 ~/Library/Application Support/MyWiki/shared-wiki 再加载，
# registry.json 等运行时写入发生在用户目录，不会破坏 .app 代码签名。
SHARED_WIKI = [(f, os.path.join('modules', 'shared-wiki'))
               for f in glob.glob(os.path.join(BASE_DIR, 'modules', 'shared-wiki', '*.py'))]

a = Analysis(
    ['wiki_app.py'],
    pathex=[],
    binaries=[],
    datas=[(os.path.join(BASE_DIR, 'icon.ico'), '.'),
           (os.path.join(BASE_DIR, 'assets', 'AppIcon.icns'), 'assets')]
          + WEB_PY + WEB_HTML + WEB_THEME + WEB_VOICE + MODEL_HINT + VENDOR_MP
          + [KG] + SHARED_WIKI + BACKGROUND_IMAGES,
    hiddenimports=['agent_registry', 'obsidian_bridge', 'mcp_server',
                   'yaml', 'watchdog', 'watchdog.observers', 'watchdog.events',
                   'rag', 'voice_mood', 'vision_segment', 'llm_qa',
                   'face_mood', 'vision_face_mood',
                   'wiki_paths', 'wiki_data', 'wiki_i18n',
                   'cv2', 'mediapipe', 'numpy',
                   'Vision', 'Quartz', 'Foundation', 'PIL'],
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
    version=VERSION,
    codesign_identity=codesign_identity,
    entitlements_file=entitlements_file,
    info_plist={
        'CFBundleShortVersionString': VERSION,
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'CFBundleDisplayName': 'MyWiki',
        'CFBundleName': 'MyWiki',
    },
)
