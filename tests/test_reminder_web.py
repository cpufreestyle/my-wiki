#!/usr/bin/env python3
"""
tests/test_reminder_web.py — reminder_web.html 结构 / 选择器一致性单元测试

纯标准库实现（unittest + html.parser + re），无需任何第三方依赖，可直接在
CI 中运行。核心目标：**防住 JS 里引用了不存在的元素 id / class 导致
`querySelector` 返回 null 的整类 bug**（正是之前 getBoundingClientRect 报错
那一类的根因），同时守住关键的可访问性（a11y）属性不被误删。
"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent.parent / "reminder_web.html"


class _Collector(HTMLParser):
    """收集所有元素 id、class 以及 data-* 属性。"""

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.classes = set()
        self.data_attrs = []          # 每个元素的 {attr: value} for data-*
        self.tags = []                # (tag, attrs_dict)
        self.preset_cards = []        # 每张预设卡片的属性字典

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.tags.append((tag, d))
        if "id" in d and d["id"]:
            self.ids.add(d["id"])
        if "class" in d and d["class"]:
            for c in d["class"].split():
                self.classes.add(c)
        data = {k: v for k, v in d.items() if k.startswith("data-")}
        if data:
            self.data_attrs.append(data)
        if "class" in d and "preset-card" in d.get("class", "").split():
            self.preset_cards.append(d)


def _load():
    text = HTML_PATH.read_text(encoding="utf-8")
    parser = _Collector()
    parser.feed(text)
    # 提取 <script> 正文
    m = re.search(r"<script>(.*?)</script>", text, re.DOTALL)
    script = m.group(1) if m else ""
    return text, parser, script


class TestReminderWebStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script = _load()

    # ---- 文件存在且可解析 ----
    def test_file_exists(self):
        self.assertTrue(HTML_PATH.exists(), f"缺少文件: {HTML_PATH}")
        self.assertIn("<!DOCTYPE html>", self.text)

    def test_has_script_block(self):
        self.assertTrue(self.script.strip(), "未找到 <script> 正文")

    # ---- 选择器一致性：每个 #id 选择器都必须有对应元素 ----
    def test_id_selectors_resolve(self):
        """脚本里所有字符串形式的 '#id' 选择器都必须能在 DOM 中找到。"""
        # 匹配 "#id" / '#id' 两种引号
        refs = set(re.findall(r"""['"]#([A-Za-z][\w-]*)['"]""", self.script))
        self.assertTrue(refs, "脚本中未发现任何 #id 选择器（解析可能出错）")
        missing = sorted(r for r in refs if r not in self.p.ids)
        self.assertFalse(
            missing,
            f"脚本引用了不存在的元素 id（会导致 querySelector 返回 null）: {missing}\n"
            f"实际存在的 id: {sorted(self.p.ids)}",
        )

    # ---- class 选择器一致性 ----
    def test_class_selectors_resolve(self):
        refs = set(re.findall(r"""querySelector(?:All)?\(['"]\.([A-Za-z][\w-]*)""", self.script))
        missing = sorted(r for r in refs if r not in self.p.classes)
        self.assertFalse(
            missing,
            f"脚本引用了不存在的 class: {missing}\n实际 class: {sorted(self.p.classes)}",
        )

    # ---- 关键交互元素必须存在 ----
    def test_required_ids_present(self):
        required = {
            "themeToggle", "toast", "pendingSection", "pendingList",
            "customBtn", "viewBtn", "contentModal", "customModal",
            "reminderText", "customTime", "customText",
            "saveContentBtn", "saveCustomBtn",
        }
        missing = sorted(required - self.p.ids)
        self.assertFalse(missing, f"缺少关键元素 id: {missing}")

    # ---- 预设卡片的 data-* 与 JS 读取的字段一致 ----
    def test_preset_cards_dataset(self):
        cards = self.p.preset_cards
        self.assertGreaterEqual(len(cards), 6, "预设卡片数量异常")
        for c in cards:
            self.assertIn("data-name", c, f"预设卡片缺少 data-name: {c}")
            self.assertTrue(
                ("data-hours" in c) or ("data-key" in c),
                f"预设卡片需含 data-hours 或 data-key: {c}",
            )

    def test_preset_keys_match_logic(self):
        """HTML 中 data-key 的取值必须都在 getPresetTime 的 switch 分支里被处理。"""
        html_keys = {c["data-key"] for c in self.p.preset_cards if "data-key" in c}
        handled = set(re.findall(r'case\s+"([\w_]+)"', self.script))
        unhandled = sorted(html_keys - handled)
        self.assertFalse(
            unhandled,
            f"存在未被 getPresetTime 处理的 data-key: {unhandled}（handled={sorted(handled)}）",
        )

    # ---- 可访问性关键属性 ----
    def test_accessibility_attributes(self):
        # themeToggle 需有 aria-label
        toggle = next((d for t, d in self.p.tags if d.get("id") == "themeToggle"), None)
        self.assertIsNotNone(toggle)
        self.assertIn("aria-label", toggle, "themeToggle 缺少 aria-label")
        # 模态框需 role=dialog + aria-modal
        dialogs = [d for t, d in self.p.tags if d.get("role") == "dialog"]
        self.assertGreaterEqual(len(dialogs), 2, "对话框数量不足")
        for d in dialogs:
            self.assertEqual(d.get("aria-modal"), "true", "对话框缺少 aria-modal=true")
        # toast 需 role=status
        toast = next((d for t, d in self.p.tags if d.get("id") == "toast"), None)
        self.assertIsNotNone(toast)
        self.assertEqual(toast.get("role"), "status", "toast 缺少 role=status")

    # ---- 深色模式与错误过滤 ----
    def test_dark_mode_support(self):
        self.assertIn('[data-theme="dark"]', self.text, "缺少深色模式样式")
        self.assertIn('data-theme', self.script, "脚本缺少 data-theme 切换逻辑")

    def test_global_error_filter_present(self):
        self.assertIn('"Script error."', self.script,
                      "缺少屏蔽跨域 Script error 的全局错误过滤器")


if __name__ == "__main__":
    unittest.main(verbosity=2)
