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

import rag as rag_module
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


# ── 去重：brain/ 副本与大小写变体 ──────────────────────────────────────

class TestSourceDeduplication(unittest.TestCase):
    """brain/ 与顶层目录存放同一批文档；macOS 上还会有仅大小写不同的文件名。

    不去重会让同一篇笔记被索引多次，top-k 里出现多条分数相同的重复项。
    """

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmpdir = tempfile.mkdtemp()
        wiki = Path(self.tmpdir)
        (wiki / "daily").mkdir(parents=True)
        (wiki / "brain" / "daily").mkdir(parents=True)
        (wiki / "concepts").mkdir(parents=True)

        (wiki / "daily" / "2026-05-23.md").write_text(
            "# 日记" + chr(10) + chr(10) + "今天去唱歌。" + chr(10), encoding="utf-8")
        # brain/ 下的同路径副本
        (wiki / "brain" / "daily" / "2026-05-23.md").write_text(
            "# 日记" + chr(10) + chr(10) + "今天去唱歌。" + chr(10), encoding="utf-8")
        # 仅大小写不同的两个文件名
        (wiki / "concepts" / "LLM_Wiki.md").write_text(
            "# LLM Wiki" + chr(10) + chr(10) + "用 LLM 构建 wiki。" + chr(10), encoding="utf-8")
        (wiki / "concepts" / "llm_wiki.md").write_text(
            "# LLM Wiki" + chr(10) + chr(10) + "用 LLM 构建 wiki。" + chr(10), encoding="utf-8")

        self.engine = RAGEngine(wiki_root=self.tmpdir, mode="bm25")
        self.engine.index()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_brain_copy_not_double_indexed(self):
        rels = [b["rel"] for b in self.engine.blocks]
        self.assertEqual(
            len(rels), len(set(rels)),
            "同一篇笔记不应被索引两次：%s" % rels,
        )

    def test_canonical_path_drops_brain_prefix(self):
        rels = [b["rel"] for b in self.engine.blocks]
        self.assertFalse(
            any(r.startswith("brain/") for r in rels),
            "规范路径应去掉 brain/ 前缀，实际：%s" % rels,
        )

    def test_case_variant_not_double_indexed(self):
        rels = [b["rel"] for b in self.engine.blocks]
        lowered = [r.lower() for r in rels]
        self.assertEqual(
            len(lowered), len(set(lowered)),
            "大小写变体应被视为同一篇笔记，实际：%s" % rels,
        )


# ── RRF 融合 ──────────────────────────────────────────────────────────

def _hit(rel, snippet):
    return {"rel": rel, "title": rel, "score": 1.0, "snippet": snippet}


class TestRRFMerge(unittest.TestCase):
    def test_two_ranks_agree_beats_single_top(self):
        """一路排第 6、另一路也排第 6，应胜过只在单路排第 1。"""
        a = [_hit("x.md", "s%d" % i) for i in range(6)]
        b = [_hit("y.md", "t0"), _hit("x.md", "s0")]
        out = RAGEngine._rrf_merge([a, b], limit=10)
        self.assertEqual(out[0]["rel"], "x.md", "两路都召回的片段应排第一")

    def test_doc_multi_chunk_accumulates(self):
        """一篇笔记命中多个片段时，各片段贡献在文档级累加。

        只按片段计分而不累加的话，6 个中等名次片段（各约 0.016）会输给
        1 个排第一的片段（0.0164），多片段证据被白白浪费。
        """
        a = [_hit("a.md", "only")]
        b = [_hit("b.md", "b1"), _hit("b.md", "b2"), _hit("b.md", "b3")]
        out = RAGEngine._rrf_merge([a, b], limit=10)
        self.assertEqual(out[0]["rel"], "b.md", "多片段证据应在文档级胜出")
        b_hits = [h for h in out if h["rel"] == "b.md"]
        self.assertEqual(len(b_hits), rag_module.MAX_CHUNKS_PER_DOC,
                         "展示片段数应受 MAX_CHUNKS_PER_DOC 限制")

    def test_two_roads_agree_beats_single_road_top(self):
        """同一片段被两路同时召回时，贡献累加，胜过只被单路召回的片段。"""
        a = [_hit("x.md", "s0"), _hit("y.md", "y0")]
        b = [_hit("y.md", "y0")]
        out = RAGEngine._rrf_merge([a, b], limit=10)
        self.assertEqual(out[0]["rel"], "y.md", "两路都召回的文档应排第一")

    def test_doc_score_is_shared_across_its_chunks(self):
        """同一文档的多个片段共享该文档的融合分。"""
        a = [_hit("a.md", "a1"), _hit("a.md", "a2")]
        out = RAGEngine._rrf_merge([a], limit=10)
        scores = {h["score"] for h in out}
        self.assertEqual(len(scores), 1, "同文档片段应共享同一分数：%s" % scores)

    def test_per_doc_chunk_cap(self):
        b = [_hit("b.md", "b%d" % i) for i in range(6)] + [_hit("a.md", "a0")]
        out = RAGEngine._rrf_merge([b], limit=10)
        self.assertEqual(
            sum(1 for h in out if h["rel"] == "b.md"), 2,
            "同一篇笔记最多保留 2 个片段，实际：%s" % [h["rel"] for h in out],
        )
        self.assertIn("a.md", [h["rel"] for h in out], "限流后应给其它笔记留出名额")

    def test_limit_respected(self):
        a = [_hit("d%d.md" % i, "s") for i in range(20)]
        self.assertEqual(len(RAGEngine._rrf_merge([a], limit=3)), 3)

    def test_empty(self):
        self.assertEqual(RAGEngine._rrf_merge([[], []], limit=5), [])


# ── 嵌入分批 ──────────────────────────────────────────────────────────


class TestEmbedBatching(unittest.TestCase):
    """整库一次性提交会让 Ollama runner 连接重置（400），必须分批。"""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmpdir = tempfile.mkdtemp()
        wiki = Path(self.tmpdir)
        (wiki / "concepts").mkdir(parents=True)
        (wiki / "concepts" / "a.md").write_text(
            "# 标题" + chr(10) + chr(10) + "内容内容。" + chr(10), encoding="utf-8")
        self.engine = RAGEngine(wiki_root=self.tmpdir, mode="ollama")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, n_blocks, fail_batch_indices=()):
        """用假的 requests 驱动 _embed_blocks，返回 (embedded 数, 各批大小)。

        _embed_blocks 内部是函数级 import requests，所以必须注入
        sys.modules["requests"] 才能生效——patch rag.requests 无效。
        """
        import sys as _sys
        sizes = []

        class FakeResp:
            def __init__(self, texts):
                self._texts = texts

            def raise_for_status(self):
                if len(sizes) - 1 in fail_batch_indices:
                    raise RuntimeError("connection reset by peer")

            def json(self):
                return {"embeddings": [[0.1, 0.2] for _ in self._texts]}

        class FakeRequests:
            @staticmethod
            def post(url, json=None, timeout=None):
                sizes.append(len(json["input"]))
                return FakeResp(json["input"])

        eng = self.engine
        eng.blocks = [{"rel": "a.md", "title": "a", "text": "段落%d" % i}
                      for i in range(n_blocks)]
        eng.cache = {}
        eng._save_cache = lambda: None
        orig = _sys.modules.get("requests")
        _sys.modules["requests"] = FakeRequests
        try:
            eng._embed_blocks(force=True)
        finally:
            if orig is not None:
                _sys.modules["requests"] = orig
            else:
                del _sys.modules["requests"]
        return sum(1 for b in eng.blocks if "_emb" in b), sizes


    def test_batch_size_is_bounded(self):
        self.assertGreater(rag_module.EMBED_BATCH, 0)
        self.assertLessEqual(rag_module.EMBED_BATCH, 64, "批次过大会触发 Ollama 400")

    def test_requests_are_split_into_batches(self):
        n = rag_module.EMBED_BATCH * 3
        embedded, sizes = self._run(n)
        self.assertEqual(sizes, [rag_module.EMBED_BATCH] * 3,
                         "%d 个块应切成 3 批，实际 %s" % (n, sizes))
        self.assertEqual(embedded, n)

    def test_partial_failure_keeps_successful_batches(self):
        """某批失败只丢该批：成功批的向量保留，且 mode 不整体降级。"""
        n = rag_module.EMBED_BATCH * 3
        embedded, sizes = self._run(n, fail_batch_indices=(0,))
        self.assertEqual(len(sizes), 3)
        self.assertEqual(
            embedded, rag_module.EMBED_BATCH * 2,
            "失败的批次应丢掉、成功批次保留，实际 embedded=%d" % embedded,
        )
        self.assertEqual(self.engine.mode, "ollama", "部分失败不应整体降级为 BM25")

    def test_total_failure_falls_back_to_bm25(self):
        """全部批次失败时整库退回 BM25，保证检索仍可用。"""
        embedded, sizes = self._run(rag_module.EMBED_BATCH, fail_batch_indices=(0,))
        self.assertEqual(embedded, 0)
        self.assertEqual(self.engine.mode, "bm25", "全部失败应退回 BM25")
