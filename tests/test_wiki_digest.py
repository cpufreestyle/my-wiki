#!/usr/bin/env python3
"""tests/test_wiki_digest.py — wiki_digest（复刻 Notion AI 每日摘要）行为测试。

覆盖当天笔记收集（文件名 / mtime 两种命中）、抽取式摘要结构、
AI 路径（注入假 llm_qa 模块，不联网）与各级兜底、空天行为。
测试一律传临时 root，不写 brain/ daily/ wiki/ 真实内容。
"""
import sys
import tempfile
import types
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import wiki_digest

DAY = date(2026, 10, 13)
DAY_TS = datetime(2026, 10, 13, 12, 0, 0).timestamp()
OTHER_TS = datetime(2026, 10, 12, 12, 0, 0).timestamp()


def _write(root, rel, text, mtime=None):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mtime is not None:
        import os
        os.utime(path, (mtime, mtime))
    return path


def _vault():
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    for name in ("brain", "daily", "wiki"):
        (root / name).mkdir()
    return tmp, root


def _fake_llm_qa(answer, available=True, raises=False):
    """构造假 llm_qa 模块并塞进 sys.modules，返回清理函数。"""
    mod = types.ModuleType("llm_qa")

    def _generate(prompt, model=None, timeout=None, system=None):
        if raises:
            raise RuntimeError("模型炸了")
        return answer

    mod.ollama_available = lambda timeout=2.0: available
    mod.generate = _generate
    orig = sys.modules.get("llm_qa")
    sys.modules["llm_qa"] = mod

    def _restore():
        if orig is None:
            sys.modules.pop("llm_qa", None)
        else:
            sys.modules["llm_qa"] = orig

    return _restore


class GatherDayNotesTest(unittest.TestCase):
    """gather_day_notes：文件名前缀或 mtime 命中当天。"""

    def test_hit_by_name(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        _write(root, "daily/2026-10-13-日记.md", "# 日记\n\n今天有事。")
        # 名字不带当天日期，mtime 也推到前一天，确保只按名字命中
        _write(root, "daily/2026-10-12-昨天.md", "# 昨天\n\n昨天有事。",
               mtime=OTHER_TS)
        notes = wiki_digest.gather_day_notes(root, DAY)
        self.assertEqual([n["rel"] for n in notes], ["daily/2026-10-13-日记.md"])

    def test_hit_by_mtime(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        _write(root, "brain/旧名字.md", "# 甲\n\n正文", mtime=DAY_TS)
        notes = wiki_digest.gather_day_notes(root, DAY)
        self.assertEqual([n["rel"] for n in notes], ["brain/旧名字.md"])

    def test_empty_day(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        _write(root, "brain/a.md", "# 甲\n\n正文", mtime=OTHER_TS)
        self.assertEqual(wiki_digest.gather_day_notes(root, DAY), [])


class ExtractiveDigestTest(unittest.TestCase):
    """extractive_digest：结构、标签分布、要点摘录。"""

    def _notes(self):
        return [
            {"rel": "brain/a.md",
             "text": "---\ntitle: 甲\ntags: [x, y]\n---\n\n# 甲\n\n第一句内容足够长可以被摘录。第二句也足够长可以摘录出来。第三句同样足够长但超出两句上限。"},
            {"rel": "daily/b.md",
             "text": "# 乙\n\n只有一句话的笔记内容也比较长。"},
        ]

    def test_structure(self):
        text = wiki_digest.extractive_digest(self._notes())
        self.assertIn("# 每日摘要", text)
        self.assertIn("共 2 篇笔记有更新。", text)
        self.assertIn("## 今日笔记", text)
        self.assertIn("- [甲](brain/a.md)", text)
        self.assertIn("- [乙](daily/b.md)", text)

    def test_tag_distribution_sorted(self):
        text = wiki_digest.extractive_digest(self._notes())
        self.assertIn("## 标签分布", text)
        self.assertIn("- x × 1", text)
        self.assertIn("- y × 1", text)

    def test_sentences_capped_at_two(self):
        text = wiki_digest.extractive_digest(self._notes())
        # 切句按中英文句末标点分裂，摘录句不带句末标点
        self.assertIn("- 第一句内容足够长可以被摘录\n", text)
        self.assertIn("- 第二句也足够长可以摘录出来\n", text)
        self.assertNotIn("第三句同样足够长", text)

    def test_no_tags_fallback(self):
        notes = [{"rel": "brain/a.md", "text": "# 甲\n\n一句话内容也要足够长才可以。"}]
        text = wiki_digest.extractive_digest(notes)
        self.assertIn("（今日笔记没有标签）", text)

    def test_empty_notes(self):
        text = wiki_digest.extractive_digest([])
        self.assertIn("共 0 篇笔记有更新。", text)


class BuildDigestTest(unittest.TestCase):
    """build_digest：落盘、frontmatter、各级兜底。"""

    def _two_notes(self, root):
        _write(root, "daily/2026-10-13-a.md", "# 甲\n\n今天的收获相当丰富。")
        _write(root, "daily/2026-10-13-b.md", "# 乙\n\n又完成了一件事情。")

    def test_extractive_mode(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        self._two_notes(root)
        path, mode = wiki_digest.build_digest(root, DAY, use_ai=False)
        self.assertEqual(mode, "extractive")
        self.assertEqual(path, root / "daily" / "digest" / "2026-10-13.md")
        text = path.read_text(encoding="utf-8")
        self.assertIn("mode: extractive", text)
        self.assertIn("notes: 2", text)
        self.assertIn("共 2 篇", text)

    def test_empty_day_returns_none(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        path, mode = wiki_digest.build_digest(root, DAY, use_ai=False)
        self.assertIsNone(path)
        self.assertEqual(mode, "empty")

    def test_ai_mode_when_model_available(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(_fake_llm_qa("模型生成的中文摘要。"))
        self._two_notes(root)
        path, mode = wiki_digest.build_digest(root, DAY, use_ai=True)
        self.assertEqual(mode, "ai")
        text = path.read_text(encoding="utf-8")
        self.assertIn("mode: ai", text)
        self.assertIn("模型生成的中文摘要。", text)

    def test_falls_back_when_ollama_unavailable(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(_fake_llm_qa("不该出现", available=False))
        self._two_notes(root)
        path, mode = wiki_digest.build_digest(root, DAY, use_ai=True)
        self.assertEqual(mode, "extractive")
        self.assertNotIn("不该出现", path.read_text(encoding="utf-8"))

    def test_falls_back_when_generate_raises(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(_fake_llm_qa("", raises=True))
        self._two_notes(root)
        path, mode = wiki_digest.build_digest(root, DAY, use_ai=True)
        self.assertEqual(mode, "extractive")
        self.assertIn("共 2 篇", path.read_text(encoding="utf-8"))

    def test_falls_back_when_generate_empty(self):
        tmp, root = _vault()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(_fake_llm_qa("   "))
        self._two_notes(root)
        path, mode = wiki_digest.build_digest(root, DAY, use_ai=True)
        self.assertEqual(mode, "extractive")


if __name__ == "__main__":
    unittest.main()
