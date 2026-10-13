#!/usr/bin/env python3
"""tests/test_wiki_publish.py — wiki_publish（复刻 Obsidian Publish）行为测试。

覆盖 frontmatter 解析、行内/块级渲染、危险协议拦截、静态站点构建
（首页 / 标签页 / 反向链接 / 搜索索引 / 输出目录保护）与 CLI 入口。
仅 import 标准库与一方模块，符合 CI 依赖契约（tests/test_ci_dependency_contract.py）。
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import wiki_publish

BT = chr(96)
FENCE = BT * 3


def _write(root, rel, text):
    """在临时 vault 里写一篇笔记，自动建父目录。"""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _vault():
    """建一个最小临时 vault：brain/daily/wiki 三个来源目录。"""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    for name in ("brain", "daily", "wiki"):
        (root / name).mkdir()
    return tmp, root


class ParseFrontmatterTest(unittest.TestCase):
    """parse_frontmatter：极简 YAML 子集，不引入 pyyaml。"""

    def test_key_value_and_indented_list(self):
        meta, body = wiki_publish.parse_frontmatter(
            "---\ntitle: 甲\ntags:\n  - x\n  - y\n---\n\n正文")
        self.assertEqual(meta["title"], "甲")
        self.assertEqual(meta["tags"], ["x", "y"])
        self.assertEqual(body.strip(), "正文")

    def test_inline_list_stays_string(self):
        meta, _ = wiki_publish.parse_frontmatter("---\ntags: [a, b]\n---\n正文")
        self.assertEqual(meta["tags"], "[a, b]")

    def test_empty_value_becomes_list(self):
        meta, _ = wiki_publish.parse_frontmatter("---\ntags:\n---\n正文")
        self.assertEqual(meta["tags"], [])

    def test_no_frontmatter_returns_original(self):
        meta, body = wiki_publish.parse_frontmatter("# 标题\n\n正文")
        self.assertEqual(meta, {})
        self.assertIn("正文", body)

    def test_unclosed_frontmatter_is_body(self):
        meta, body = wiki_publish.parse_frontmatter("---\ntitle: x\n正文")
        self.assertEqual(meta, {})
        self.assertIn("正文", body)


class RenderInlineTest(unittest.TestCase):
    """render_markdown 行内：加粗/斜体/代码/链接/图片。"""

    def test_bold_italic_code(self):
        out = wiki_publish.render_markdown("**粗** *斜* " + BT + "code" + BT)
        self.assertIn("<strong>粗</strong>", out)
        self.assertIn("<em>斜</em>", out)
        self.assertIn("<code>code</code>", out)

    def test_wikilink_broken_renders_span(self):
        out = wiki_publish.render_markdown("见 [[不存在]]。")
        self.assertIn("wikilink-broken", out)
        self.assertIn("不存在", out)

    def test_dangerous_scheme_blocked(self):
        out = wiki_publish.render_markdown("[x](javascript:alert(1))")
        self.assertNotIn("javascript:", out)
        self.assertIn('href="#"', out)
        # URL 里的一层平衡括号不该被截断成正文残留
        self.assertNotIn(")", out.replace("</a>", ""))

    def test_normal_links_and_image(self):
        out = wiki_publish.render_markdown(
            "[外](https://e.com) ![图](a.png)")
        self.assertIn('<a href="https://e.com">外</a>', out)
        self.assertIn('<img src="a.png"', out)


class RenderBlockTest(unittest.TestCase):
    """render_markdown 块级：标题/列表/任务/表格/围栏/引用。"""

    def test_heading_gets_id(self):
        out = wiki_publish.render_markdown("## 小节")
        self.assertIn('<h2 id="小节">小节</h2>', out)

    def test_nested_list_stays_inside_li(self):
        out = wiki_publish.render_markdown("- 甲\n  - 乙")
        self.assertIn("<li>甲<ul><li>乙</li></ul></li>", out)

    def test_task_list_checkbox(self):
        out = wiki_publish.render_markdown("- [ ] 待办\n- [x] 完成")
        self.assertIn('<input type="checkbox" disabled> 待办', out)
        self.assertIn('<input type="checkbox" checked disabled> 完成', out)

    def test_table(self):
        md = "| 列一 | 列二 |\n| --- | --- |\n| 1 | 2 |"
        out = wiki_publish.render_markdown(md)
        self.assertIn("<table>", out)
        self.assertIn("<th>列一</th>", out)
        self.assertIn("<td>2</td>", out)

    def test_fenced_code(self):
        md = FENCE + "python\nprint(1)\n" + FENCE
        out = wiki_publish.render_markdown(md)
        self.assertIn("<pre><code", out)
        self.assertIn("print(1)", out)

    def test_mixed_unordered_and_ordered_not_merged(self):
        out = wiki_publish.render_markdown("- 甲\n\n1. 乙")
        self.assertIn("<li>甲</li>", out)
        self.assertIn("<ol><li>乙</li></ol>", out)
        self.assertNotIn("<li>甲<ol>", out)


class CollectNotesTest(unittest.TestCase):
    """collect_notes：title/tags/words 兜底链。"""

    def test_collect_fields(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        _write(root, "brain/a.md",
               "---\ntitle: 甲\ntags: [x, y]\n---\n\n# 甲\n\n正文内容。")
        notes = wiki_publish.collect_notes(root, ("brain",))
        self.assertEqual(len(notes), 1)
        note = notes[0]
        self.assertEqual(note["rel"], "brain/a.md")
        self.assertEqual(note["title"], "甲")
        self.assertEqual(note["tags"], ["x", "y"])
        self.assertGreater(note["words"], 0)

    def test_title_falls_back_to_h1_then_stem(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        _write(root, "brain/a.md", "# 一级标题\n\n正文")
        _write(root, "brain/b.md", "没有标题的正文")
        notes = {n["rel"]: n for n in wiki_publish.collect_notes(root, ("brain",))}
        self.assertEqual(notes["brain/a.md"]["title"], "一级标题")
        self.assertEqual(notes["brain/b.md"]["title"], "b")

    def test_empty_source_dir_skipped(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        self.assertEqual(wiki_publish.collect_notes(root, ("brain",)), [])


class BuildSiteTest(unittest.TestCase):
    """build_site：输出结构、反向链接、搜索索引、目录保护。"""

    def _site(self, root, out, **kw):
        return wiki_publish.build_site(root, out_dir=out, **kw)

    def test_build_outputs_exist(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "dist"
        _write(root, "brain/a.md",
               "---\ntitle: 甲\ntags: [x]\n---\n\n# 甲\n\n正文，见 [[b]]。")
        _write(root, "brain/sub/b.md", "# 乙\n\n回到 [[a]]。")
        stats = self._site(root, out)
        self.assertEqual(stats["notes"], 2)
        # out_dir 是 resolve 过的（macOS /var -> /private/var）
        self.assertEqual(Path(stats["out_dir"]), out.resolve())
        self.assertTrue((out / "index.html").is_file())
        self.assertTrue((out / "tags.html").is_file())
        self.assertTrue((out / "assets" / "style.css").is_file())
        self.assertTrue((out / "assets" / "search.js").is_file())
        self.assertTrue((out / "notes" / "brain" / "a.html").is_file())
        self.assertTrue((out / "notes" / "brain" / "sub" / "b.html").is_file())

    def test_backlinks_section(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "dist"
        _write(root, "brain/a.md", "# 甲\n\n见 [[b]]。")
        _write(root, "brain/b.md", "# 乙\n\n正文")
        self._site(root, out)
        page = (out / "notes" / "brain" / "b.html").read_text(encoding="utf-8")
        self.assertIn('<section class="backlinks"><h2>反向链接</h2>', page)
        self.assertIn("甲", page)

    def test_search_data_parseable(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "dist"
        _write(root, "brain/a.md", "# 甲\n\n可搜索的正文内容")
        self._site(root, out)
        js = (out / "assets" / "search.js").read_text(encoding="utf-8")
        self.assertIn("window.SEARCH_INDEX", js)
        data_js = (out / "assets" / "search-data.js").read_text(encoding="utf-8")
        self.assertTrue(data_js.startswith("window.SEARCH_INDEX = "))
        payload = data_js.split("=", 1)[1].strip().rstrip(";")
        data = json.loads(payload)
        self.assertTrue(any(e["title"] == "甲" for e in data))

    def test_guard_rejects_protected_dirs(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        for bad in (root, root / "brain", root.parent):
            with self.assertRaises(ValueError):
                self._site(root, bad)

    def test_clean_removes_stale_files(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "dist"
        _write(root, "brain/a.md", "# 甲\n\n正文")
        self._site(root, out)
        stale = out / "notes" / "stale.html"
        stale.write_text("old", encoding="utf-8")
        self._site(root, out, clean=True)
        self.assertFalse(stale.exists())

    def test_default_out_dir_under_root(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        _write(root, "brain/a.md", "# 甲\n\n正文")
        stats = self._site(root, None)
        self.assertEqual(stats["out_dir"], str((root / "dist-publish").resolve()))


class CliTest(unittest.TestCase):
    """main()：MYWIKI_ROOT 环境变量指定 vault。"""

    def test_cli_publish_via_env(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "cli-dist"
        _write(root, "brain/a.md", "# 甲\n\n正文")
        old = os.environ.get("MYWIKI_ROOT")
        os.environ["MYWIKI_ROOT"] = str(root)
        try:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                code = wiki_publish.main(["--out", str(out), "--clean"])
        finally:
            if old is None:
                os.environ.pop("MYWIKI_ROOT", None)
            else:
                os.environ["MYWIKI_ROOT"] = old
        self.assertEqual(code, 0)
        self.assertTrue((out / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
