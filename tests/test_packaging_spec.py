"""test_packaging_spec.py — MyWiki.spec 打包清单回归测试（不真正构建）。

打包版 (.app) 把 web_server.py 及其本地依赖当“数据文件”塞进资源目录，
PyInstaller 的静态分析不会跟踪数据文件里的 import，遗漏即静默降级：
页面裸样式（漏 apple-ui.css）、接口不可用（漏 llm_qa.py）、面部识别缺模型
（漏 models/face_landmarker.task）。

本测试以哑 PyInstaller 符号执行 spec，捕获 Analysis / BUNDLE 的实参，断言
运行期真正需要的资源都在 datas、本地模块都在 hiddenimports、版本号与
pyproject.toml 一致。spec 本身不 import，避免真的触发重量级打包分析。
"""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATH = os.path.join(ROOT, "MyWiki.spec")
PYPROJECT = os.path.join(ROOT, "pyproject.toml")


class _Dummy:
    """占位对象：吃掉 PyInstaller 的构造调用与属性访问（a.pure / a.datas ...）。"""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __getattr__(self, name):  # noqa: D105
        return _Dummy()


def _load_spec():
    """执行 spec，返回 {构造名: kwargs}；CWD 临时切到仓库根（spec 用相对路径）。"""
    captured = {}

    def make(name):
        def factory(*args, **kwargs):
            captured[name] = kwargs
            return _Dummy(*args, **kwargs)
        return factory

    namespace = {
        "__file__": SPEC_PATH,
        "__name__": "mywiki_spec_under_test",
        "Analysis": make("Analysis"),
        "PYZ": make("PYZ"),
        "EXE": make("EXE"),
        "COLLECT": make("COLLECT"),
        "BUNDLE": make("BUNDLE"),
    }
    with open(SPEC_PATH, encoding="utf-8") as fh:
        source = fh.read()
    prior = os.getcwd()
    try:
        os.chdir(ROOT)
        exec(compile(source, SPEC_PATH, "exec"), namespace)  # noqa: S102
    finally:
        os.chdir(prior)
    return captured


def _packaged_pairs(captured):
    """把 datas 展平成 {(打包后文件名, 目标子目录)}。"""
    datas = captured["Analysis"].get("datas") or []
    return {(os.path.basename(src), dest) for src, dest in datas}


def _pyproject_version():
    with open(PYPROJECT, encoding="utf-8") as fh:
        m = re.search(r'^version\s*=\s*"([^"]+)"', fh.read(), re.MULTILINE)
    return m.group(1) if m else None


class SpecDatasTests(unittest.TestCase):
    """打进包的只读资源必须覆盖运行期真实引用的路径。"""

    @classmethod
    def setUpClass(cls):
        cls.captured = _load_spec()
        cls.pairs = _packaged_pairs(cls.captured)

    def test_apple_ui_css_is_packaged(self):
        """所有 *_web.html 都 <link> assets/web/apple-ui.css，漏打则浏览器 404 裸样式。"""
        self.assertIn(("apple-ui.css", "assets/web"), self.pairs)

    def test_theme_js_is_packaged(self):
        self.assertIn(("theme.js", "assets/web"), self.pairs)

    def test_voice_controller_js_is_packaged(self):
        """根级 voice-controller.js 被 mood/daily/reminder/rag 四页同源引用。"""
        self.assertIn(("voice-controller.js", "."), self.pairs)

    def test_face_landmarker_model_is_packaged(self):
        """face_mood.py 读 models/face_landmarker.task，打包版不可依赖联网下载。"""
        self.assertIn(("face_landmarker.task", "models"), self.pairs)

    def test_mediapipe_vendor_tree_is_packaged(self):
        """face_mood_web.html 同源加载 /vendor/mediapipe/*（AGENTS.md 只增不改）。"""
        vendor = {name for name, dest in self.pairs
                  if dest.startswith("vendor/mediapipe")}
        for required in ("vision_bundle.mjs", "selfie_segmentation.js",
                         "vision_wasm_internal.js", "vision_wasm_internal.wasm",
                         "selfie_segmentation_solution_simd_wasm_bin.wasm"):
            self.assertIn(required, vendor)

    def test_every_web_page_is_packaged(self):
        """仓库根每个 *_web.html 与 index.html 都应进包，新增页面自动受检。"""
        pages = [f for f in os.listdir(ROOT) if f.endswith("_web.html")]
        pages.append("index.html")
        packaged_html = {name for name, _ in self.pairs}
        for page in pages:
            self.assertIn(page, packaged_html, f"{page} 未打进包")

    def test_web_server_local_modules_are_packaged(self):
        """web_server.py 以数据文件打包，其本地 import 必须显式列入 datas。"""
        for module in ("llm_qa.py", "face_mood.py", "vision_face_mood.py",
                       "wiki_paths.py", "wiki_data.py", "wiki_i18n.py",
                       "rag.py", "voice_mood.py", "vision_segment.py"):
            self.assertIn((module, "."), self.pairs, f"{module} 未打进包")


class SpecHiddenImportsTests(unittest.TestCase):
    """hiddenimports 需覆盖原生/第三方重依赖，否则打包版裸机崩溃。"""

    @classmethod
    def setUpClass(cls):
        cls.hidden = set(_load_spec()["Analysis"].get("hiddenimports") or [])

    def test_local_runtime_modules_are_hidden_imports(self):
        for module in ("rag", "voice_mood", "vision_segment", "llm_qa",
                       "face_mood", "vision_face_mood",
                       "wiki_paths", "wiki_data", "wiki_i18n",
                       "agent_registry", "obsidian_bridge", "mcp_server"):
            self.assertIn(module, self.hidden)

    def test_native_vision_deps_are_hidden_imports(self):
        for module in ("cv2", "mediapipe", "numpy", "Vision", "Quartz", "PIL"):
            self.assertIn(module, self.hidden)


class SpecVersionTests(unittest.TestCase):
    """包内版本号必须与 pyproject.toml 单一数据源一致（防止 2.9.0 / 2.10.1 漂移）。"""

    @classmethod
    def setUpClass(cls):
        cls.bundle = _load_spec()["BUNDLE"]
        cls.pyproject = _pyproject_version()

    def test_pyproject_version_detected(self):
        self.assertTrue(self.pyproject, "未能从 pyproject.toml 解析 version")

    def test_bundle_version_matches_pyproject(self):
        self.assertEqual(self.bundle.get("version"), self.pyproject)

    def test_bundle_info_plist_version_matches_pyproject(self):
        plist = self.bundle.get("info_plist") or {}
        self.assertEqual(plist.get("CFBundleShortVersionString"), self.pyproject)


if __name__ == "__main__":
    unittest.main()
