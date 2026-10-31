#!/usr/bin/env python3
"""tests/test_priority_consistency.py — 待办优先级枚举的一致性

优先级名字散落在数据层（`PRIORITY_ORDER`）、桌面端（`PRIORITY_COLORS`
与下拉选项）、i18n（`pri_high` / `pri_medium` / `pri_low`）和网页端
（`<option>` 与 `PRI` 标签表）。新增一档优先级却漏改其中一处时不会报错：
下拉里选不到、颜色静默回落成灰色、或网页端直接显示 i18n key。

这里把唯一枚举钉在 `wiki_data.PRIORITY_ORDER`，其余各处必须与它对齐。
纯标准库 + AST：`wiki_tabs_todo` 依赖 PySide6，CI 的裸测试步骤里不能 import。
"""
import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import wiki_data  # noqa: E402
import wiki_i18n  # noqa: E402

TAB_FILE = ROOT / "wiki_tabs_todo.py"
WEB_FILE = ROOT / "todo_web.html"


def module_literal(file_name, name):
    """取模块级赋值 `name = {...}` 的字面量值（不 import 目标模块）。"""
    tree = ast.parse((ROOT / file_name).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("{} 里找不到模块级字面量 {}".format(file_name, name))


class PriorityEnumerationTest(unittest.TestCase):
    def test_enumeration_is_not_empty(self):
        self.assertTrue(wiki_data.PRIORITY_ORDER)

    def test_default_priority_belongs_to_the_enumeration(self):
        """默认优先级写错（例如改名后漏改）会让归一生效成一个不存在的档位。"""
        self.assertIn(wiki_data.DEFAULT_PRIORITY, wiki_data.PRIORITY_ORDER)


class DesktopTabTest(unittest.TestCase):
    def test_color_mapping_covers_every_priority(self):
        """少一档颜色不会报错，只是 `.get` 静默回落成 TEXT2。"""
        colors = module_literal("wiki_tabs_todo.py", "PRIORITY_COLORS")
        self.assertEqual(set(colors), set(wiki_data.PRIORITY_ORDER))

    def test_tab_does_not_keep_a_second_priority_list(self):
        """下拉选项必须由枚举派生；脚本里再出现档位字面量就是第二份数据源。"""
        tree = ast.parse(TAB_FILE.read_text(encoding="utf-8"))
        hits = [node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and node.value in wiki_data.PRIORITY_ORDER]
        self.assertEqual(sorted(hits), sorted(wiki_data.PRIORITY_ORDER),
                         "wiki_tabs_todo.py 里出现了优先级字面量 {}："
                         "除 PRIORITY_COLORS 的键以外，选项与默认值都应取自 "
                         "wiki_data.PRIORITY_ORDER / DEFAULT_PRIORITY".format(hits))


class I18nTest(unittest.TestCase):
    def test_every_priority_has_a_label_in_both_languages(self):
        for lang in ("zh", "en"):
            missing = ["pri_" + p for p in wiki_data.PRIORITY_ORDER
                       if "pri_" + p not in wiki_i18n.I18N[lang]]
            self.assertEqual(missing, [], "{} 缺少优先级文案 {}".format(lang, missing))


class WebPageTest(unittest.TestCase):
    """todo_web.html 是静态页面，只能靠文本对齐；它也是优先级枚举的一份副本。"""

    @classmethod
    def setUpClass(cls):
        cls.html = WEB_FILE.read_text(encoding="utf-8")

    def test_select_offers_exactly_the_configured_priorities(self):
        values = re.findall(r'<option value="([^"]+)"', self.html)
        self.assertEqual(set(values), set(wiki_data.PRIORITY_ORDER))

    def test_select_defaults_to_the_default_priority(self):
        selected = re.findall(r'<option value="([^"]+)"[^>]*\bselected\b', self.html)
        self.assertEqual(selected, [wiki_data.DEFAULT_PRIORITY])

    def test_label_table_covers_every_priority(self):
        match = re.search(r"const PRI = \{([^}]*)\}", self.html)
        self.assertIsNotNone(match, "todo_web.html 缺少 PRI 标签表")
        keys = re.findall(r"(\w+)\s*:", match.group(1))
        self.assertEqual(set(keys), set(wiki_data.PRIORITY_ORDER))


if __name__ == "__main__":
    unittest.main(verbosity=2)
