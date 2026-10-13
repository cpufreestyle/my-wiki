#!/usr/bin/env python3
"""tests/test_wiki_srs.py — wiki_srs（复刻 RemNote Pro / Readwise）行为测试。

覆盖问答卡/填空卡抽取与去重、SM-2 lite 调度（again/hard/good/easy）、
到期筛选、状态读写（含损坏兜底）与全库收集范围。
仅 import 标准库与一方模块，符合 CI 依赖契约。
"""
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import wiki_srs

TODAY = date(2026, 10, 13)


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _vault():
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    for name in ("brain", "daily", "wiki"):
        (root / name).mkdir()
    return tmp, root


class ExtractCardsTest(unittest.TestCase):
    """extract_cards：两种卡片形态与去重。"""

    def test_qa_pair(self):
        cards = wiki_srs.extract_cards("Q: 什么是测试\nA: 验证行为\n", "brain/a.md")
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["kind"], "qa")
        self.assertEqual(card["question"], "什么是测试")
        self.assertEqual(card["answer"], "验证行为")
        self.assertEqual(card["source"], "brain/a.md")

    def test_cloze(self):
        cards = wiki_srs.extract_cards("这是 ==重点内容== 的一句话", "brain/a.md")
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["kind"], "cloze")
        self.assertEqual(card["answer"], "重点内容")
        self.assertEqual(card["question"], "这是 〔…〕 的一句话")

    def test_dedup_by_key(self):
        md = "Q: 同一个问题\nA: 同一个答案\n\nQ: 同一个问题\nA: 另一个答案\n"
        self.assertEqual(len(wiki_srs.extract_cards(md, "s")), 1)
        md2 = "==重复== 与 ==重复=="
        self.assertEqual(len(wiki_srs.extract_cards(md2, "s")), 1)

    def test_card_id_stable(self):
        a = wiki_srs.extract_cards("Q: 稳定\nA: 一样\n", "s")[0]["id"]
        b = wiki_srs.extract_cards("Q: 稳定\nA: 一样\n", "other.md")[0]["id"]
        self.assertEqual(a, b)
        self.assertEqual(len(a), 12)


class ReviewTest(unittest.TestCase):
    """review：SM-2 lite 各评分分支。"""

    def _card(self):
        return wiki_srs.extract_cards("Q: 问题\nA: 答案\n", "s")[0]

    def test_invalid_grade_raises(self):
        with self.assertRaises(ValueError):
            wiki_srs.review(self._card(), {}, "maybe", TODAY)

    def test_good_first_time(self):
        st = wiki_srs.review(self._card(), {}, "good", TODAY)
        self.assertEqual(st["interval"], 3)
        self.assertEqual(st["due"], (TODAY + timedelta(days=3)).isoformat())

    def test_good_grows_interval(self):
        state = {}
        wiki_srs.review(self._card(), state, "good", TODAY)
        st = wiki_srs.review(self._card(), state, "good", TODAY)
        # 二次间隔 = round(上次间隔 * ease)，默认 ease 2.5
        self.assertEqual(st["interval"], 8)
        self.assertEqual(st["reps"], 2)
        self.assertEqual(
            date.fromisoformat(st["due"]) - TODAY, timedelta(days=st["interval"]))

    def test_easy_first_time(self):
        st = wiki_srs.review(self._card(), {}, "easy", TODAY)
        self.assertEqual(st["interval"], 7)
        self.assertAlmostEqual(st["ease"], 2.6)

    def test_hard_lowers_ease(self):
        st = wiki_srs.review(self._card(), {}, "hard", TODAY)
        self.assertAlmostEqual(st["ease"], 2.35)

    def test_again_resets_same_day(self):
        state = {}
        wiki_srs.review(self._card(), state, "good", TODAY)
        st = wiki_srs.review(self._card(), state, "again", TODAY)
        self.assertEqual(st["interval"], 0)
        self.assertEqual(st["due"], TODAY.isoformat())
        self.assertEqual(st["lapses"], 1)
        self.assertEqual(st["reps"], 0)

    def test_ease_floor(self):
        state = {}
        for _ in range(20):
            st = wiki_srs.review(self._card(), state, "again", TODAY)
        self.assertGreaterEqual(st["ease"], 1.3)


class DueCardsTest(unittest.TestCase):
    """due_cards：新卡/逾期/未来/limit。"""

    def _cards(self):
        return wiki_srs.extract_cards(
            "Q: 甲\nA: 一\n\nQ: 乙\nA: 二\n\nQ: 丙\nA: 三\n", "s")

    def test_new_cards_due(self):
        due = wiki_srs.due_cards(self._cards(), {}, TODAY)
        self.assertEqual(len(due), 3)

    def test_past_due_included_future_excluded(self):
        state = {}
        cards = self._cards()
        wiki_srs.review(cards[0], state, "good", TODAY)          # +3 天，未来
        wiki_srs.review(cards[1], state, "good", TODAY - timedelta(days=10))
        state[cards[1]["id"]]["due"] = (TODAY - timedelta(days=1)).isoformat()
        due = wiki_srs.due_cards(cards, state, TODAY)
        ids = [c["id"] for c in due]
        self.assertNotIn(cards[0]["id"], ids)
        self.assertIn(cards[1]["id"], ids)

    def test_limit(self):
        due = wiki_srs.due_cards(self._cards(), {}, TODAY, limit=2)
        self.assertEqual(len(due), 2)


class StateIoTest(unittest.TestCase):
    """load_state / save_state：roundtrip 与损坏兜底。"""

    def test_roundtrip(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        state = {"abc": {"due": "2026-10-14", "interval": 1}}
        wiki_srs.save_state(root, state)
        self.assertTrue((root / "srs.json").is_file())
        self.assertEqual(wiki_srs.load_state(root), state)

    def test_missing_file_returns_empty(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        self.assertEqual(wiki_srs.load_state(root), {})

    def test_corrupted_file_returns_empty(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        (root / "srs.json").write_text("{ 坏掉的 json", encoding="utf-8")
        self.assertEqual(wiki_srs.load_state(root), {})


class CollectCardsTest(unittest.TestCase):
    """collect_cards：扫 brain+daily，不收 wiki，跳过点目录。"""

    def test_scope(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        _write(root, "brain/a.md", "Q: 甲\nA: 一\n")
        _write(root, "daily/b.md", "==填空==\n")
        _write(root, "wiki/c.md", "Q: 不该收\nA: 对\n")
        _write(root, "brain/.obsidian/d.md", "Q: 隐藏\nA: 对\n")
        cards = wiki_srs.collect_cards(root)
        sources = {c["source"] for c in cards}
        self.assertEqual(sources, {"brain/a.md", "daily/b.md"})
        self.assertEqual(len(cards), 2)


if __name__ == "__main__":
    unittest.main()
