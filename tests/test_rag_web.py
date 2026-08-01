#!/usr/bin/env python3
"""
tests/test_rag_web.py — rag_web.html 语义检索页结构 / 选择器一致性单元测试

纯标准库实现（unittest + html.parser + re），无需任何第三方依赖。核心目标：
守住 JS 里引用了不存在的元素 id / class 导致 querySelector 返回 null 的整类 bug，
同时校验检索交互关键元素、语音输入接入、深色模式与可访问性属性。
"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent.parent / "rag_web.html"
VOICE_JS_PATH = Path(__file__).resolve().parent.parent / "voice-controller.js"


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.classes = set()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.tags.append((tag, d))
        if "id" in d and d["id"]:
            self.ids.add(d["id"])
        if "class" in d and d["class"]:
            for c in d["class"].split():
                self.classes.add(c)


def _load():
    text = HTML_PATH.read_text(encoding="utf-8")
    parser = _Collector()
    parser.feed(text)
    blocks = re.findall(r"<script>(.*?)</script>", text, re.DOTALL)
    script = blocks[-1] if blocks else ""
    voice_js = VOICE_JS_PATH.read_text(encoding="utf-8") if VOICE_JS_PATH.exists() else ""
    return text, parser, script, voice_js


class TestRagWebStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script, cls.voice_js = _load()

    def test_file_exists(self):
        self.assertTrue(HTML_PATH.exists(), f"缺少文件: {HTML_PATH}")
        self.assertIn("<!DOCTYPE html>", self.text)

    def test_has_script_block(self):
        self.assertTrue(self.script.strip(), "未找到内联 <script> 正文")

    def test_id_selectors_resolve(self):
        refs = set(re.findall(r"""['"]#([A-Za-z][\w-]*)['"]""", self.script))
        self.assertTrue(refs, "脚本中未发现任何 #id 选择器")
        missing = sorted(r for r in refs if r not in self.p.ids)
        self.assertFalse(
            missing,
            f"脚本引用了不存在的元素 id: {missing}\n实际 id: {sorted(self.p.ids)}",
        )

    def test_class_selectors_resolve(self):
        refs = set(re.findall(r"""querySelector(?:All)?\(['"]\.([A-Za-z][\w-]*)""", self.script))
        missing = sorted(r for r in refs if r not in self.p.classes)
        self.assertFalse(missing, f"脚本引用了不存在的 class: {missing}")

    def test_required_ids_present(self):
        required = {
            "themeToggle", "queryInput", "searchBtn", "results", "meta",
            "voiceBtn", "voiceStatus", "toast",
        }
        missing = sorted(required - self.p.ids)
        self.assertFalse(missing, f"缺少关键元素 id: {missing}")

    def test_api_endpoint_wired(self):
        # 检索页应调用 /api/rag 接口
        self.assertIn("/api/rag", self.script, "应调用 /api/rag 接口")
        self.assertIn("encodeURIComponent", self.script, "应对检索词做 URL 编码")

    def test_back_link_present(self):
        # 新页面应提供返回总入口的链接（统一导航体验）
        self.assertIn('href="index.html"', self.text, "应提供返回总入口的链接")

    def test_voice_shared_module_wired(self):
        self.assertIn('src="voice-controller.js"', self.text,
                      "应引入共享语音模块 voice-controller.js")
        self.assertIn("new VoiceController(", self.script, "应实例化共享语音控制器")
        self.assertIn("voiceBtn", self.script, "应为 voiceBtn 实例化 VoiceController")

    def test_voice_graceful_degradation(self):
        combined = self.script + "\n" + self.voice_js
        self.assertIn("不支持语音识别", combined,
                      "应处理浏览器不支持语音识别的情况（voice-controller.js）")

    def test_accessibility_attributes(self):
        toggle = next((d for t, d in self.p.tags if d.get("id") == "themeToggle"), None)
        self.assertIsNotNone(toggle)
        self.assertIn("aria-label", toggle, "themeToggle 缺少 aria-label")
        toast = next((d for t, d in self.p.tags if d.get("id") == "toast"), None)
        self.assertIsNotNone(toast)
        self.assertEqual(toast.get("role"), "status", "toast 缺少 role=status")

    def test_dark_mode_support(self):
        self.assertIn('[data-theme="dark"]', self.text, "缺少深色模式样式")
        self.assertIn("data-theme", self.script, "脚本缺少 data-theme 切换逻辑")

    def test_global_error_filter_present(self):
        self.assertIn('"Script error."', self.script,
                      "缺少屏蔽跨域 Script error 的全局错误过滤器")


if __name__ == "__main__":
    unittest.main(verbosity=2)
