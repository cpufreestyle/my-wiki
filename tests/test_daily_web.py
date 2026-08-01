#!/usr/bin/env python3
"""
tests/test_daily_web.py — daily_web.html 结构 / 选择器一致性单元测试

纯标准库实现（unittest + html.parser + re），无需任何第三方依赖。核心目标：
守住 JS 里引用了不存在的元素 id / class 导致 querySelector 返回 null 的整类 bug，
同时校验关键交互元素、深色模式与可访问性属性。
"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent.parent / "daily_web.html"


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
    m = re.search(r"<script>(.*?)</script>", text, re.DOTALL)
    script = m.group(1) if m else ""
    return text, parser, script


class TestDailyWebStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script = _load()

    def test_file_exists(self):
        self.assertTrue(HTML_PATH.exists(), f"缺少文件: {HTML_PATH}")
        self.assertIn("<!DOCTYPE html>", self.text)

    def test_has_script_block(self):
        self.assertTrue(self.script.strip(), "未找到 <script> 正文")

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
            "themeToggle", "toast", "todayLabel", "tagsBtn",
            "templateBtn", "editor", "saveBtn", "tagDisplay", "status",
        }
        missing = sorted(required - self.p.ids)
        self.assertFalse(missing, f"缺少关键元素 id: {missing}")

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

    def test_ctrl_s_save_binding_present(self):
        self.assertIn('"s"', self.script, "脚本应绑定 Ctrl/Cmd+S 保存")
        self.assertIn("saveDaily", self.script, "脚本应定义 saveDaily")



    def test_card_height_control_present(self):
        # 卡片高度调节：滑块面板 + 控件 + 卡片 min-height 绑定变量
        self.assertIn("height-panel", self.p.classes, "缺少 .height-panel 卡片高度面板")
        for i in ["cardHeight", "cardHeightVal"]:
            self.assertIn(i, self.p.ids, f"缺少卡片高度控件 id: {i}")
        self.assertIn("var(--card-h)", self.text, "卡片 min-height 应绑定 --card-h 变量")
        self.assertIn('LS_CARD_H = "mywiki-card-h"', self.script,
                      "应定义卡片高度 localStorage key(mywiki-card-h)")
        self.assertIn("localStorage.setItem(LS_CARD_H", self.script,
                      "卡片高度应持久化到 localStorage")

if __name__ == "__main__":
    unittest.main(verbosity=2)
