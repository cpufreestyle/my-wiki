#!/usr/bin/env python3
"""
tests/test_apple_ui.py — Apple 皮肤静态契约

apple-ui.css 是通过「位于各页 <style> 之后引入，同特异度后者胜出」来统一
换肤的。这种接法脆弱且不可见：任何一页漏挂 link、样式表被改成选择器嵌套
玻璃、或把仅表可见性的 .show 做成玻璃面，页面都不会报错，只会悄悄变丑。
这几个测试把这些约定钉住。
"""
import io
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "assets" / "web" / "apple-ui.css"
PAGES = [
    "index.html", "rag_web.html", "mood_web.html", "daily_web.html",
    "reminder_web.html", "graph_web.html", "mood_report_web.html",
    "face_mood_web.html", "todo_web.html",
]
SHEET_REF = "assets/web/apple-ui.css"


class AppleSkinWiringTests(unittest.TestCase):
    """换肤接入点：每个页面都必须挂上同一张样式表，且位置在内联样式之后。"""

    def test_all_pages_link_the_sheet(self):
        missing = [
            p for p in PAGES
            if SHEET_REF not in io.open(ROOT / p, encoding="utf-8").read()
        ]
        self.assertEqual(missing, [], "这些页面漏挂了统一皮肤：%s" % missing)

    def test_link_comes_after_inline_styles(self):
        """link 必须在内联 </style> 之后，否则会被同特异度的内联规则盖掉。"""
        wrong = []
        for p in PAGES:
            html = io.open(ROOT / p, encoding="utf-8").read()
            at_link = html.find(SHEET_REF)
            at_style = html.rfind("</style>", 0, at_link)
            if at_style < 0:
                wrong.append(p + "(无内联 style)")
        self.assertEqual(wrong, [], "这些页面的 link 位置不在内联样式之后：%s" % wrong)

    def test_every_page_has_exactly_one_link(self):
        for p in PAGES:
            html = io.open(ROOT / p, encoding="utf-8").read()
            self.assertEqual(
                html.count("apple-ui.css"), 1,
                "%s 应只引入一次皮肤样式表" % p,
            )


class AppleSkinContentTests(unittest.TestCase):
    """皮肤本体：必须真的提供 Apple 材质语言与无障碍兜底。"""

    @classmethod
    def setUpClass(cls):
        cls.css = io.open(SHEET, encoding="utf-8").read()

    def test_sheet_exists_and_is_substantial(self):
        self.assertTrue(SHEET.exists(), "缺少 %s" % SHEET)
        self.assertGreater(len(self.css.splitlines()), 300, "皮肤内容过少")

    def test_defines_light_and_dark_tokens(self):
        self.assertIn(":root", self.css, "缺少浅色 token")
        self.assertIn('[data-theme="dark"]', self.css, "缺少深色 token")
        for var in ["--glass-fill", "--accent", "--radius-card"]:
            self.assertIn(var, self.css, "缺少设计变量 %s" % var)

    def test_glass_uses_backdrop_filter(self):
        self.assertIn("backdrop-filter", self.css, "没有背景模糊就没有玻璃材质")
        self.assertIn("saturate", self.css, "玻璃饱和提升是 Apple 材质特征之一")

    def test_reduced_transparency_falls_back_to_opaque(self):
        self.assertIn(
            "prefers-reduced-transparency", self.css,
            "关闭透明度时必须退化为不透明材质，否则玻璃面文字不可读",
        )

    def test_reduced_motion_kills_animation(self):
        self.assertIn(
            "prefers-reduced-motion", self.css,
            "减弱动效偏好必须被尊重",
        )

    def test_no_nested_glass(self):
        """玻璃容器不能互相嵌套——Apple 材质只在内容之上放一层。

        卡片内部的子区块（栅格、引用来源、记录列表）若也套上 backdrop-filter，
        就形成玻璃套玻璃：模糊采样的是玻璃而不是真实背景，观感发糊且费 GPU。
        """
        for cls in [".result-list", ".sources", ".records"]:
            start = self.css.find(cls + " {")
            if start < 0:
                continue
            end = self.css.find("}", start)
            block = self.css[start:end]
            self.assertNotIn(
                "backdrop-filter", block,
                "%s 是卡片内部子区块，不应再套玻璃（会玻璃套玻璃）" % cls,
            )

    def test_show_is_not_a_surface(self):
        """.show 只表可见性（JS 增删它来显示 toast），绝不能做成玻璃面。"""
        selector_block = self.css[self.css.find("/* ---- 玻璃卡片"):]
        selector_block = selector_block[:selector_block.find("/* ---- 列表行")]
        self.assertNotIn(
            ".show", selector_block,
            ".show 是状态类而非容器，做成玻璃面会污染所有被 add('show') 的元素",
        )


if __name__ == "__main__":
    unittest.main()
