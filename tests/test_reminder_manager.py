#!/usr/bin/env python3
"""
tests/test_reminder_manager.py — reminder_manager.py 核心函数单元测试

通过 mock 替换 Windows 专属调用和硬编码路径，在 macOS/Linux 上验证
load / save / add / cancel / get_pending / preset 等纯逻辑函数。
纯标准库实现，无需第三方依赖。
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# 确保能导入仓库根目录的模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _patch_reminder_paths(tmpdir):
    """将 reminder_manager 中的硬编码 Windows 路径替换为临时目录。"""
    reminder_dir = os.path.join(tmpdir, "reminders")
    reminder_file = os.path.join(reminder_dir, "reminders.json")
    return reminder_dir, reminder_file


class TestLoadSaveReminders(unittest.TestCase):
    """测试 load_reminders / save_reminders 的读写逻辑。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.reminder_dir, self.reminder_file = _patch_reminder_paths(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("reminder_manager.REMINDER_FILE", new="")
    @patch("reminder_manager.REMINDER_DIR", new="")
    def test_load_empty_when_no_file(self):
        import reminder_manager
        reminder_manager.REMINDER_FILE = self.reminder_file
        reminder_manager.REMINDER_DIR = self.reminder_dir
        result = reminder_manager.load_reminders()
        self.assertEqual(result, [])

    @patch("reminder_manager.REMINDER_FILE", new="")
    @patch("reminder_manager.REMINDER_DIR", new="")
    def test_save_and_load_roundtrip(self):
        import reminder_manager
        reminder_manager.REMINDER_FILE = self.reminder_file
        reminder_manager.REMINDER_DIR = self.reminder_dir
        data = [{"id": 1, "message": "测试", "status": "pending"}]
        reminder_manager.save_reminders(data)
        loaded = reminder_manager.load_reminders()
        self.assertEqual(loaded, data)
        # 验证文件确实存在
        self.assertTrue(os.path.exists(self.reminder_file))

    @patch("reminder_manager.REMINDER_FILE", new="")
    @patch("reminder_manager.REMINDER_DIR", new="")
    def test_save_creates_directory(self):
        import reminder_manager
        nested_dir = os.path.join(self.tmpdir, "deep", "nested", "reminders")
        nested_file = os.path.join(nested_dir, "reminders.json")
        reminder_manager.REMINDER_FILE = nested_file
        reminder_manager.REMINDER_DIR = nested_dir
        reminder_manager.save_reminders([{"id": 1}])
        self.assertTrue(os.path.exists(nested_file))


class TestAddReminder(unittest.TestCase):
    """测试 add_reminder 的 ID 自增与数据结构。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.reminder_dir, self.reminder_file = _patch_reminder_paths(self.tmpdir)
        import reminder_manager
        reminder_manager.REMINDER_DIR = self.reminder_dir
        reminder_manager.REMINDER_FILE = self.reminder_file

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_add_first_reminder(self, mock_task):
        import reminder_manager
        remind_at = datetime(2026, 8, 1, 10, 0, 0)
        result = reminder_manager.add_reminder(remind_at, "开会")
        self.assertEqual(result["id"], 1)
        self.assertEqual(result["message"], "开会")
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["remind_at"], "2026-08-01 10:00:00")
        self.assertIsNotNone(result["task_name"])

    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_add_increments_id(self, mock_task):
        import reminder_manager
        # 先添加一个
        reminder_manager.add_reminder(datetime(2026, 8, 1, 10, 0), "第一个")
        result = reminder_manager.add_reminder(datetime(2026, 8, 1, 11, 0), "第二个")
        self.assertEqual(result["id"], 2)

    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_add_persists_to_file(self, mock_task):
        import reminder_manager
        reminder_manager.add_reminder(datetime(2026, 8, 1, 10, 0), "持久化测试")
        loaded = reminder_manager.load_reminders()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["message"], "持久化测试")


class TestCancelReminder(unittest.TestCase):
    """测试 cancel_reminder 的状态变更。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.reminder_dir, self.reminder_file = _patch_reminder_paths(self.tmpdir)
        import reminder_manager
        reminder_manager.REMINDER_DIR = self.reminder_dir
        reminder_manager.REMINDER_FILE = self.reminder_file

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("reminder_manager.delete_windows_task")
    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_cancel_pending_reminder(self, mock_create, mock_delete):
        import reminder_manager
        added = reminder_manager.add_reminder(datetime(2026, 8, 1, 10, 0), "待取消")
        result = reminder_manager.cancel_reminder(added["id"])
        self.assertTrue(result)
        loaded = reminder_manager.load_reminders()
        cancelled = [r for r in loaded if r["id"] == added["id"]][0]
        self.assertEqual(cancelled["status"], "cancelled")

    def test_cancel_nonexistent_id(self):
        import reminder_manager
        result = reminder_manager.cancel_reminder(9999)
        self.assertFalse(result)

    @patch("reminder_manager.delete_windows_task")
    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_cancel_already_sent(self, mock_create, mock_delete):
        import reminder_manager
        added = reminder_manager.add_reminder(datetime(2026, 8, 1, 10, 0), "已发送")
        # 手动改为 sent 状态
        reminders = reminder_manager.load_reminders()
        reminders[0]["status"] = "sent"
        reminder_manager.save_reminders(reminders)
        result = reminder_manager.cancel_reminder(added["id"])
        self.assertFalse(result)


class TestGetPendingReminders(unittest.TestCase):
    """测试 get_pending_reminders 的过滤逻辑。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.reminder_dir, self.reminder_file = _patch_reminder_paths(self.tmpdir)
        import reminder_manager
        reminder_manager.REMINDER_DIR = self.reminder_dir
        reminder_manager.REMINDER_FILE = self.reminder_file

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_when_no_reminders(self):
        import reminder_manager
        self.assertEqual(reminder_manager.get_pending_reminders(), [])

    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_filters_by_status(self, mock_task):
        import reminder_manager
        reminder_manager.add_reminder(datetime(2026, 8, 1, 10, 0), "提醒1")
        reminder_manager.add_reminder(datetime(2026, 8, 1, 11, 0), "提醒2")
        # 取消第二个
        reminder_manager.cancel_reminder(2)
        pending = reminder_manager.get_pending_reminders()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], 1)


class TestPresetReminders(unittest.TestCase):
    """测试 preset_reminders 返回预设时间字典。"""

    def test_returns_dict(self):
        import reminder_manager
        presets = reminder_manager.preset_reminders()
        self.assertIsInstance(presets, dict)
        self.assertGreater(len(presets), 0)

    def test_values_are_datetime(self):
        import reminder_manager
        presets = reminder_manager.preset_reminders()
        for key, val in presets.items():
            self.assertIsInstance(val, datetime, f"{key} 的值不是 datetime")

    def test_future_times(self):
        import reminder_manager
        now = datetime.now()
        presets = reminder_manager.preset_reminders()
        for key, val in presets.items():
            self.assertGreater(val, now, f"{key} 的时间应晚于当前时间")


if __name__ == "__main__":
    unittest.main(verbosity=2)
