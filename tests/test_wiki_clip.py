#!/usr/bin/env python3
"""tests/test_wiki_clip.py — wiki_clip（复刻 Notion Web Clipper）行为测试。

覆盖 HTML 正文抽取（噪音剔除 / 标题兜底 / 摘要兜底）、剪藏落盘
（frontmatter / h1 跳过 / 来源标注）与 slug、YAML 引号、抓取失败路径。
全程 monkeypatch fetch_url，不联网；仅 import 标准库与一方模块。
"""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import wiki_clip

FIXTURE_HTML = (
    "<html><head><title>页面标题</title>"
    "<meta property='og:title' content='OG标题'>"
    "<meta name='description' content='这是 meta 描述'>"
    "</head><body>"
    "<nav>导航噪音内容</nav>"
    "<article>"
    "<h1>正文主标题</h1>"
    "<p>第一段内容足够长，可以被采集下来作为正文块使用。</p>"
    "<h2>小节标题</h2>"
    "<ul><li>列表项一</li><li>列表项二</li></ul>"
    "<blockquote>引用内容</blockquote>"
    "<pre>代码块内容</pre>"
    "<script>var noise = 1;</script>"
    "<style>.noise { color: red; }</style>"
    "</article>"
    "<footer>页脚噪音内容</footer>"
    "<aside>侧栏噪音内容</aside>"
    "</body></html>"
)


def _blocks_text(data):
    return "\n".join(text for _tag, text in data["blocks"])


class SlugifyTest(unittest.TestCase):
    """_slugify：保留中英文与数字。"""

    def test_mixed(self):
        self.assertEqual(
            wiki_clip._slugify("Hello World! 测试"), "hello-world-测试")

    def test_punctuation_only_falls_back(self):
        self.assertEqual(wiki_clip._slugify("!!!"), "clip")
        self.assertEqual(wiki_clip._slugify(""), "clip")


class YamlQuoteTest(unittest.TestCase):
    """_yaml_quote：仅含特殊字符时加引号。"""

    def test_plain_chinese_not_quoted(self):
        self.assertEqual(wiki_clip._yaml_quote("中文标题"), "中文标题")

    def test_url_quoted(self):
        self.assertEqual(
            wiki_clip._yaml_quote("https://e.com/x"), '"https://e.com/x"')


class ExtractMainTextTest(unittest.TestCase):
    """extract_main_text：标题 / 摘要 / 正文块。"""

    def test_title_from_title_tag(self):
        data = wiki_clip.extract_main_text(FIXTURE_HTML)
        self.assertEqual(data["title"], "页面标题")

    def test_title_falls_back_to_og_then_h1(self):
        html = ("<html><head><meta property='og:title' content='OG标题'>"
                "</head><body><h1>一级标题</h1><p>正文</p></body></html>")
        self.assertEqual(wiki_clip.extract_main_text(html)["title"], "OG标题")
        html2 = "<html><body><h1>仅有一级标题</h1><p>正文</p></body></html>"
        self.assertEqual(
            wiki_clip.extract_main_text(html2)["title"], "仅有一级标题")

    def test_excerpt_from_meta_description(self):
        data = wiki_clip.extract_main_text(FIXTURE_HTML)
        self.assertEqual(data["excerpt"], "这是 meta 描述")

    def test_excerpt_falls_back_to_first_long_paragraph(self):
        html = ("<html><head><title>t</title></head><body>"
                "<p>短</p><p>这是一段足够长的正文可以用来兜底当作摘要。</p>"
                "</body></html>")
        data = wiki_clip.extract_main_text(html)
        self.assertIn("足够长", data["excerpt"])

    def test_noise_tags_dropped(self):
        data = wiki_clip.extract_main_text(FIXTURE_HTML)
        text = _blocks_text(data)
        for noise in ("导航噪音", "页脚噪音", "侧栏噪音", "var noise",
                      ".noise", "color: red"):
            self.assertNotIn(noise, text)

    def test_content_blocks_kept(self):
        data = wiki_clip.extract_main_text(FIXTURE_HTML)
        text = _blocks_text(data)
        self.assertIn("第一段内容足够长", text)
        self.assertIn("小节标题", text)
        self.assertIn("列表项一", text)
        self.assertIn("引用内容", text)
        self.assertIn("代码块内容", text)

    def test_h1_kept_in_blocks_for_title_fallback(self):
        # blocks 保留标题层级（供无 <title> 时兜底与 Markdown 重建），
        # 落盘时才跳过 h1——见 ClipUrlTest
        data = wiki_clip.extract_main_text(FIXTURE_HTML)
        self.assertTrue(any(t == "h1" for t, _ in data["blocks"]))


class ClipUrlTest(unittest.TestCase):
    """clip_url：monkeypatch fetch_url，不联网。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._orig_fetch = wiki_clip.fetch_url
        wiki_clip.fetch_url = lambda url, timeout=15: FIXTURE_HTML
        self.addCleanup(self._restore)

    def _restore(self):
        wiki_clip.fetch_url = self._orig_fetch

    def test_path_and_frontmatter(self):
        path = wiki_clip.clip_url("https://example.com/x", self.root)
        self.assertTrue(path.is_file())
        self.assertEqual(
            path.relative_to(self.root).as_posix(),
            "inbox/clips/%s-页面标题.md" % date.today().isoformat())
        text = path.read_text(encoding="utf-8")
        self.assertIn("title: 页面标题", text)
        self.assertIn("source: \"https://example.com/x\"", text)
        self.assertIn("clipped: ", text)
        self.assertIn("# 页面标题", text)

    def test_h1_skipped_but_headings_kept(self):
        path = wiki_clip.clip_url("https://example.com/x", self.root)
        text = path.read_text(encoding="utf-8")
        # 标题已由 frontmatter + "# 标题" 承载，正文里的 h1 不重复落盘
        self.assertNotIn("正文主标题", text)
        self.assertIn("## 小节标题", text)

    def test_noise_not_written(self):
        path = wiki_clip.clip_url("https://example.com/x", self.root)
        text = path.read_text(encoding="utf-8")
        for noise in ("导航噪音", "页脚噪音", "侧栏噪音", "var noise"):
            self.assertNotIn(noise, text)

    def test_quote_and_list_rendered(self):
        path = wiki_clip.clip_url("https://example.com/x", self.root)
        text = path.read_text(encoding="utf-8")
        self.assertIn("> 引用内容", text)
        self.assertIn("- 列表项一", text)

    def test_title_override(self):
        path = wiki_clip.clip_url("https://e.com/a", self.root, title="自定义")
        self.assertIn("自定义", path.name)
        self.assertIn("title: 自定义", path.read_text(encoding="utf-8"))


class FetchUrlTest(unittest.TestCase):
    """fetch_url：非法 URL 包成 RuntimeError。"""

    def test_bad_url_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            wiki_clip.fetch_url("not-a-url")


if __name__ == "__main__":
    unittest.main()
