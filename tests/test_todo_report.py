#!/usr/bin/env python3
"""tests/test_todo_report.py — 待办数据层与周报/月报生成单元测试

纯标准库，不依赖 PySide6，可在 CI 无头环境运行。
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wiki_data
import wiki_report


class TestTodos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.todo_file = os.path.join(self.tmp, "todos.json")
        self._orig = wiki_data.TODO_FILE
        wiki_data.TODO_FILE = self.todo_file

    def tearDown(self):
        wiki_data.TODO_FILE = self._orig

    def test_add_and_load(self):
        wiki_data.add_todo("任务A", priority="high")
        todos = wiki_data.load_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["text"], "任务A")
        self.assertEqual(todos[0]["priority"], "high")
        self.assertFalse(todos[0]["done"])

    def test_add_empty_raises(self):
        with self.assertRaises(ValueError):
            wiki_data.add_todo("   ")
        self.assertEqual(wiki_data.load_todos(), [])

    def test_id_increment(self):
        a = wiki_data.add_todo("A")
        b = wiki_data.add_todo("B")
        self.assertEqual(a["id"], 1)
        self.assertEqual(b["id"], 2)

    def test_normalize_priority(self):
        self.assertEqual(wiki_data.normalize_priority("HIGH"), "high")
        self.assertEqual(wiki_data.normalize_priority("bogus"), "medium")
        self.assertEqual(wiki_data.normalize_priority(None), "medium")

    def test_toggle(self):
        t = wiki_data.add_todo("A")
        updated = wiki_data.toggle_todo(t["id"])
        self.assertTrue(updated["done"])
        self.assertTrue(updated["done_at"])
        back = wiki_data.toggle_todo(t["id"])
        self.assertFalse(back["done"])
        self.assertEqual(back["done_at"], "")

    def test_toggle_missing(self):
        self.assertIsNone(wiki_data.toggle_todo(999))

    def test_delete(self):
        t = wiki_data.add_todo("A")
        self.assertTrue(wiki_data.delete_todo(t["id"]))
        self.assertFalse(wiki_data.delete_todo(t["id"]))
        self.assertEqual(wiki_data.load_todos(), [])

    def test_sort_and_pending(self):
        wiki_data.add_todo("低", priority="low")
        wiki_data.add_todo("高", priority="high")
        mid = wiki_data.add_todo("中", priority="medium")
        wiki_data.toggle_todo(mid["id"])
        self.assertEqual([t["text"] for t in wiki_data.pending_todos()], ["高", "低"])
        ordered = [t["text"] for t in wiki_data.sort_todos(wiki_data.load_todos())]
        self.assertEqual(ordered[0], "高")
        self.assertEqual(ordered[1], "低")
        self.assertEqual(ordered[-1], "中")  # 已完成排最后

    def test_load_corrupt_returns_empty(self):
        with open(self.todo_file, "w", encoding="utf-8") as f:
            f.write("{ not json ]")
        self.assertEqual(wiki_data.load_todos(), [])


class TestReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.daily = os.path.join(self.tmp, "daily")
        self.mood = os.path.join(self.tmp, "mood")
        os.makedirs(self.daily)
        os.makedirs(self.mood)
        self._d = wiki_report.DAILY_DIR
        self._m = wiki_report.MOOD_DIR
        self._t = wiki_data.TODO_FILE
        wiki_report.DAILY_DIR = self.daily
        wiki_report.MOOD_DIR = self.mood
        wiki_data.TODO_FILE = os.path.join(self.tmp, "todos.json")

    def tearDown(self):
        wiki_report.DAILY_DIR = self._d
        wiki_report.MOOD_DIR = self._m
        wiki_data.TODO_FILE = self._t

    def _write_daily(self, ds, body):
        with open(os.path.join(self.daily, f"{ds}.md"), "w", encoding="utf-8") as f:
            f.write(f"# {ds} Diary\n{body}")

    def _write_mood(self, ds, moods):
        with open(os.path.join(self.mood, f"{ds}.json"), "w", encoding="utf-8") as f:
            json.dump([{"mood": m} for m in moods], f)

    def test_empty_period(self):
        data = wiki_report.collect_report("2026-09-01", "2026-09-07")
        self.assertEqual(data["days"], 7)
        self.assertEqual(data["diaries"], {})
        self.assertEqual(data["mood_counter"], {})
        self.assertIn("本周期无心情记录", wiki_report.render_report(data))

    def test_diary_and_mood(self):
        self._write_daily("2026-09-15", "今天写了代码")
        self._write_mood("2026-09-15", ["开心", "开心", "平静"])
        data = wiki_report.collect_report("2026-09-10", "2026-09-16")
        self.assertEqual(list(data["diaries"].keys()), ["2026-09-15"])
        self.assertNotIn("Diary", data["diaries"]["2026-09-15"])  # 标题已剥离
        self.assertEqual(data["mood_counter"], {"开心": 2, "平静": 1})
        self.assertIn("开心：2 次", wiki_report.render_report(data))

    def test_swap_dates(self):
        data = wiki_report.collect_report("2026-09-16", "2026-09-10")
        self.assertEqual(data["start"], "2026-09-10")
        self.assertEqual(data["end"], "2026-09-16")

    def test_weekly_range(self):
        self.assertIn("2026-09-12 ~ 2026-09-18", wiki_report.weekly_report("2026-09-18"))

    def test_monthly_range(self):
        self.assertIn("2026-09-01 ~ 2026-09-18", wiki_report.monthly_report("2026-09-18"))

    def test_todos_in_report(self):
        wiki_data.add_todo("写报告", priority="high")
        data = wiki_report.collect_report("2026-09-01", "2026-09-30")
        self.assertEqual(len(data["todos_pending"]), 1)
        self.assertIn("写报告", wiki_report.render_report(data))


if __name__ == "__main__":
    unittest.main(verbosity=2)
