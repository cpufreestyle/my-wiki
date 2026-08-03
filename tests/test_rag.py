#!/usr/bin/env python3
"""
tests/test_rag.py — rag.py 核心函数单元测试

覆盖 tokenize / cosine / chunk_text / RAGEngine.search(BM25) 等纯逻辑函数，
纯标准库实现，无需第三方依赖。
"""
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 确保能导入仓库根目录的模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag import tokenize, cosine, chunk_text, RAGEngine


# ── tokenize ──────────────────────────────────────────────────────────

class TestTokenize(unittest.TestCase):
    def test_english_words(self):
        tokens = tokenize("hello world")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_chinese_bigram(self):
        tokens = tokenize("语义检索")
        # 字符 bigram: c:语义, c:义检, c:检索
        self.assertIn("c:语义", tokens)
        self.assertIn("c:义检", tokens)
        self.assertIn("c:检索", tokens)

    def test_mixed_text(self):
        tokens = tokenize("hello 世界")
        self.assertIn("hello", tokens)
        self.assertIn("c:世界", tokens)

    def test_empty_and_none(self):
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize(None), [])

    def test_single_chinese_char(self):
        tokens = tokenize("中")
        self.assertEqual(tokens, ["c:中"])

    def test_case_insensitive(self):
        tokens = tokenize("Hello WORLD")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_numbers(self):
        tokens = tokenize("abc 123")
        self.assertIn("abc", tokens)
        self.assertIn("123", tokens)

    def test_single_char_english_filtered(self):
        # 单字符英文/数字不应出现（len > 1 过滤）
        tokens = tokenize("a b c")
        self.assertEqual(tokens, [])


# ── cosine ────────────────────────────────────────────────────────────

class TestCosine(unittest.TestCase):
    def test_identical_vectors(self):
        self.assertAlmostEqual(cosine([1, 2, 3], [1, 2, 3]), 1.0)

    def test_orthogonal_vectors(self):
        self.assertAlmostEqual(cosine([1, 0], [0, 1]), 0.0)

    def test_opposite_vectors(self):
        self.assertAlmostEqual(cosine([1, 0], [-1, 0]), -1.0)

    def test_empty_input(self):
        self.assertEqual(cosine([], [1, 2]), 0.0)
        self.assertEqual(cosine([1, 2], []), 0.0)

    def test_zero_vector(self):
        self.assertEqual(cosine([0, 0], [1, 2]), 0.0)


# ── chunk_text ────────────────────────────────────────────────────────

class TestChunkText(unittest.TestCase):
    def test_single_block(self):
        text = "这是一段简短的文本，用于测试分块功能的基本行为。\n第二行内容补充说明。"
        blocks = chunk_text(text)
        self.assertEqual(len(blocks), 1)

    def test_splits_on_empty_line(self):
        # 构造超过 max_chars 且在空行处断开的文本
        para1 = "A" * 300
        para2 = "B" * 300
        text = f"{para1}\n\n{para2}"
        blocks = chunk_text(text, max_chars=200)
        self.assertGreaterEqual(len(blocks), 2)

    def test_filters_short_blocks(self):
        # 非常短的块（<=20 字符）应被过滤
        text = "短\n\n" + "这是一段足够长的文本内容，用于测试分块功能是否正常工作。" * 20
        blocks = chunk_text(text, max_chars=100)
        for b in blocks:
            self.assertGreater(len(b), 20)

    def test_empty_input(self):
        self.assertEqual(chunk_text(""), [])

    def test_heading_break(self):
        long_para = "内容行。" * 50  # > 600 chars
        text = f"{long_para}\n# 标题\n下一段内容"
        blocks = chunk_text(text, max_chars=200)
        self.assertGreaterEqual(len(blocks), 1)


# ── RAGEngine (BM25 search) ──────────────────────────────────────────

class TestRAGEngineBM25(unittest.TestCase):
    """用临时目录模拟 wiki 结构，测试 BM25 检索链路。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # 创建最小 wiki 结构
        for cat in ("daily", "projects", "concepts"):
            (Path(self.tmpdir) / cat).mkdir(exist_ok=True)
        # 写入测试文档
        doc = Path(self.tmpdir) / "concepts" / "test_doc.md"
        doc.write_text("# 测试文档\n\n语义检索是信息检索的核心技术。\n", encoding="utf-8")

        doc2 = Path(self.tmpdir) / "projects" / "my_project.md"
        doc2.write_text("# 项目说明\n\n本项目使用 Python 实现了语义检索功能。\n", encoding="utf-8")

        self.engine = RAGEngine(wiki_root=self.tmpdir, mode="bm25")
        self.engine.index()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_index_populates_blocks(self):
        self.assertGreater(len(self.engine.blocks), 0, "索引后 blocks 不应为空")
        self.assertGreater(self.engine.N, 0, "N 应大于 0")
        self.assertGreater(self.engine.avgdl, 0, "avgdl 应大于 0")

    def test_search_returns_results(self):
        hits = self.engine.search("语义检索")
        self.assertIsInstance(hits, list)
        self.assertGreater(len(hits), 0, "应找到包含'语义检索'的文档")

    def test_search_result_format(self):
        hits = self.engine.search("语义检索")
        for h in hits:
            self.assertIn("rel", h)
            self.assertIn("title", h)
            self.assertIn("score", h)
            self.assertIn("snippet", h)
            self.assertIsInstance(h["score"], float)
            self.assertGreater(h["score"], 0)

    def test_search_no_match(self):
        hits = self.engine.search("完全不存在的关键词xyzabc")
        self.assertEqual(hits, [])

    def test_search_limit(self):
        hits = self.engine.search("语义", limit=1)
        self.assertLessEqual(len(hits), 1)

    def test_detect_mode_default(self):
        eng = RAGEngine(wiki_root=self.tmpdir)
        self.assertIn(eng.mode, ("bm25", "ollama"))

    def test_format_snippet_truncation(self):
        # _format 应对长文本做截断
        long_block = {"rel": "x.md", "title": "x", "text": "A" * 300}
        result = self.engine._format([(1.0, long_block)])
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["snippet"].endswith("..."))


# ── RAGEngine cache ──────────────────────────────────────────────────

class TestRAGEngineCache(unittest.TestCase):
    def test_load_missing_cache(self):
        tmpdir = tempfile.mkdtemp()
        try:
            eng = RAGEngine(wiki_root=tmpdir, mode="bm25")
            self.assertEqual(eng.cache, {})
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_save_and_load_cache(self):
        tmpdir = tempfile.mkdtemp()
        try:
            wiki = Path(tmpdir)
            (wiki / "wiki").mkdir()
            eng = RAGEngine(wiki_root=tmpdir, mode="bm25")
            eng.cache["test_key"] = "test_value"
            eng._save_cache()
            # 重新加载
            eng2 = RAGEngine(wiki_root=tmpdir, mode="bm25")
            self.assertEqual(eng2.cache.get("test_key"), "test_value")
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
