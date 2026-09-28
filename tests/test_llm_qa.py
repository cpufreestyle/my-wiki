"""test_llm_qa.py — 本地 LLM 问答（llm_qa）的纯逻辑测试。

不真正调用 Ollama：替换网络边界（ollama_available / generate / retrieve），验证：
  - 检索为空时直接给出「没有找到」，不去问模型；
  - Ollama 不可用时优雅降级为 retrieval-only，且仍返回 sources；
  - 生成失败同样降级，error 里带原因；
  - 正常路径返回 mode=llm 与带编号的引用来源；
  - generate() 失败时返回 (None, err) 而不抛异常。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import llm_qa  # noqa: E402

FAKE_HITS = [
    {"rel": "a.md", "title": "A", "score": 3.0, "snippet": "片段一" * 10},
    {"rel": "b.md", "title": "B", "score": 2.0, "snippet": "片段二" * 10},
]


class ContextBuildTests(unittest.TestCase):
    """_build_context：片段编号 + 字符预算截断。"""

    def test_numbers_sources(self):
        ctx, kept = llm_qa._build_context(FAKE_HITS)
        self.assertEqual(kept, 2)
        self.assertIn("[1]", ctx)
        self.assertIn("[2]", ctx)

    def test_respects_char_budget(self):
        ctx, kept = llm_qa._build_context(FAKE_HITS, max_chars=10)
        self.assertLessEqual(kept, 2)
        self.assertLessEqual(len(ctx), 10)


class AnswerTests(unittest.TestCase):
    """answer()：空问题 / 无命中 / 模型不可用 / 生成失败 / 正常生成。"""

    def setUp(self):
        self.orig = {
            "retrieve": llm_qa.retrieve,
            "ollama_available": llm_qa.ollama_available,
            "generate": llm_qa.generate,
        }

    def tearDown(self):
        for k, v in self.orig.items():
            setattr(llm_qa, k, v)

    def test_empty_query_short_circuits(self):
        llm_qa.retrieve = lambda *a, **k: (FAKE_HITS, None)
        r = llm_qa.answer("   ")
        self.assertFalse(r["ok"])
        self.assertEqual(r["sources"], [])
        self.assertEqual(r["mode"], "retrieval-only")

    def test_no_hits_returns_friendly_message(self):
        llm_qa.retrieve = lambda *a, **k: ([], None)
        llm_qa.ollama_available = lambda *a, **k: True
        llm_qa.generate = lambda *a, **k: ("不该被调用", None)
        r = llm_qa.answer("某个不存在的话题")
        self.assertTrue(r["ok"])
        self.assertEqual(r["mode"], "retrieval-only")
        self.assertIn("没有找到", r["answer"])

    def test_ollama_down_falls_back_to_retrieval(self):
        llm_qa.retrieve = lambda *a, **k: (FAKE_HITS, None)
        llm_qa.ollama_available = lambda *a, **k: False
        llm_qa.generate = lambda *a, **k: ("不该被调用", None)
        r = llm_qa.answer("测试问题")
        self.assertTrue(r["ok"], "降级不应把整体标成失败")
        self.assertIsNone(r["answer"])
        self.assertEqual(r["mode"], "retrieval-only")
        self.assertIn("Ollama", r["error"])
        self.assertEqual(len(r["sources"]), 2)

    def test_generate_failure_falls_back_with_reason(self):
        llm_qa.retrieve = lambda *a, **k: (FAKE_HITS, None)
        llm_qa.ollama_available = lambda *a, **k: True
        llm_qa.generate = lambda *a, **k: (None, "连接超时")
        r = llm_qa.answer("测试问题")
        self.assertTrue(r["ok"])
        self.assertIsNone(r["answer"])
        self.assertEqual(r["mode"], "retrieval-only")
        self.assertIn("连接超时", r["error"])

    def test_success_returns_llm_mode_and_sources(self):
        llm_qa.retrieve = lambda *a, **k: (FAKE_HITS, None)
        llm_qa.ollama_available = lambda *a, **k: True
        llm_qa.generate = lambda *a, **k: ("这是答案[1]", None)
        r = llm_qa.answer("测试问题")
        self.assertTrue(r["ok"])
        self.assertEqual(r["mode"], "llm")
        self.assertEqual(r["answer"], "这是答案[1]")
        self.assertIsNone(r["error"])
        self.assertEqual([s["index"] for s in r["sources"]], [1, 2])

    def test_retrieve_error_reported(self):
        llm_qa.retrieve = lambda *a, **k: ([], "索引损坏")
        r = llm_qa.answer("测试问题")
        self.assertFalse(r["ok"])
        self.assertIn("索引损坏", r["error"])


class GenerateContractTests(unittest.TestCase):
    """generate() 契约：失败返回 (None, err)，绝不抛异常。"""

    def test_returns_tuple_on_unreachable_ollama(self):
        old = llm_qa.OLLAMA_URL
        try:
            llm_qa.OLLAMA_URL = "http://127.0.0.1:1"
            text, err = llm_qa.generate("hi", timeout=2)
        finally:
            llm_qa.OLLAMA_URL = old
        self.assertIsNone(text)
        self.assertIsInstance(err, str)


if __name__ == "__main__":
    unittest.main()
