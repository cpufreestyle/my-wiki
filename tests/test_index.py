#!/usr/bin/env python3
"""
tests/test_index.py — index.html 网页端总入口门户页结构 / 导航一致性单元测试

纯标准库实现（unittest + html.parser + re），无需任何第三方依赖。核心目标：
守住门户页必须指向真实存在的模块页面（提醒 / 日记 / 心情），避免导航 404；
同时校验关键交互元素、深色模式与可访问性属性。
"""
import os
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"
ROOT = Path(__file__).resolve().parent.parent


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.classes = set()
        self.tags = []
        self.href = []  # 记录所有 <a href>

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.tags.append((tag, d))
        if "id" in d and d["id"]:
            self.ids.add(d["id"])
        if "class" in d and d["class"]:
            for c in d["class"].split():
                self.classes.add(c)
        if tag == "a" and d.get("href"):
            self.href.append(d["href"])


def _load():
    text = HTML_PATH.read_text(encoding="utf-8")
    parser = _Collector()
    parser.feed(text)
    blocks = re.findall(r"<script>(.*?)</script>", text, re.DOTALL)
    script = blocks[-1] if blocks else ""
    return text, parser, script


class TestIndexStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script = _load()

    def test_file_exists(self):
        self.assertTrue(HTML_PATH.exists(), f"缺少文件: {HTML_PATH}")
        self.assertIn("<!DOCTYPE html>", self.text)

    def test_has_script_block(self):
        self.assertTrue(self.script.strip(), "未找到内联 <script> 正文")

    def test_id_selectors_resolve(self):
        refs = set(re.findall(r"""['"]#([A-Za-z][\w-]*)['"]""", self.script))
        missing = sorted(r for r in refs if r not in self.p.ids)
        self.assertFalse(
            missing,
            f"脚本引用了不存在的元素 id: {missing}\n实际 id: {sorted(self.p.ids)}",
        )

    def test_required_ids_present(self):
        required = {"themeToggle"}
        missing = sorted(required - self.p.ids)
        self.assertFalse(missing, f"缺少关键元素 id: {missing}")

    def test_module_links_present_and_exist(self):
        # 三个模块页面都必须被导航卡片引用，且文件真实存在
        expected = {
            "reminder_web.html": "快速提醒",
            "daily_web.html": "每日日记",
            "mood_web.html": "心情记录",
        }
        hrefs = set(self.p.href)
        for page in expected:
            self.assertIn(page, hrefs, f"门户页未链接到模块页: {page}")
            target = ROOT / page
            self.assertTrue(target.exists(), f"模块页文件不存在: {target}")
        # 至少 3 个导航卡片（a.module-card）
        cards = [t for t in self.p.tags if t[0] == "a" and "module-card" in (t[1].get("class") or "")]
        self.assertGreaterEqual(len(cards), 3, "导航卡片数量不足（应有 ≥3）")

    def test_module_link_texts(self):
        # 卡片应包含可读的中文标签
        labels = " ".join(
            (t[1].get("class") or "")
            for t in self.p.tags
            if t[0] == "a" and "module-card" in (t[1].get("class") or "")
        )
        combined = self.text
        for kw in ("快速提醒", "每日日记", "心情记录"):
            self.assertIn(kw, combined, f"门户页应展示模块名: {kw}")

    def test_accessibility_attributes(self):
        toggle = next((d for t, d in self.p.tags if d.get("id") == "themeToggle"), None)
        self.assertIsNotNone(toggle)
        self.assertIn("aria-label", toggle, "themeToggle 缺少 aria-label")
        grid = next((d for t, d in self.p.tags
                     if t == "section" and d.get("aria-label")), None)
        self.assertIsNotNone(grid, "导航区 section 应提供 aria-label")

    def test_dark_mode_support(self):
        self.assertIn('[data-theme="dark"]', self.text, "缺少深色模式样式")
        self.assertIn("data-theme", self.script, "脚本缺少 data-theme 切换逻辑")

    def test_global_error_filter_present(self):
        self.assertIn('"Script error."', self.script,
                      "缺少屏蔽跨域 Script error 的全局错误过滤器")

    def test_inline_styles_complete(self):
        # 门户页自包含，不依赖外部 CSS；关键 token 应内联
        for token in ("--accent:", "--orange:", "--green:", "--border:"):
            self.assertIn(token, self.text, f"缺少内联设计 token: {token}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
