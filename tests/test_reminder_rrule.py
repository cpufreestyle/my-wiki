#!/usr/bin/env python3
"""
tests/test_reminder_rrule.py — reminder_rrule.py 规则引擎与 reminder_manager
重复提醒集成（add / advance / COUNT / UNTIL / schtasks 映射）单元测试。

覆盖 RRULE 子集解析校验、发生时间展开语义（对齐 python-dateutil）、
中文描述，以及 reminder_manager 的重复提醒推进与耗尽逻辑。
纯标准库实现，无需第三方依赖。
"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# 确保能导入仓库根目录的模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import reminder_rrule
from reminder_rrule import (
    RRuleError,
    describe_rule,
    iter_occurrences,
    next_occurrence,
    parse_rrule,
)


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class TestParseRRule(unittest.TestCase):
    """RRULE 解析与校验"""

    def test_minimal_defaults(self):
        rule = parse_rrule("FREQ=DAILY")
        self.assertEqual(rule["freq"], "DAILY")
        self.assertEqual(rule["interval"], 1)
        self.assertIsNone(rule["count"])
        self.assertIsNone(rule["until"])
        self.assertIsNone(rule["byday"])
        self.assertIsNone(rule["bymonthday"])

    def test_full_rule_case_insensitive(self):
        rule = parse_rrule("freq=weekly;interval=2;byday=mo,fr;count=5")
        self.assertEqual(rule["freq"], "WEEKLY")
        self.assertEqual(rule["interval"], 2)
        self.assertEqual(rule["byday"], ["MO", "FR"])
        self.assertEqual(rule["count"], 5)

    def test_until_datetime_and_z(self):
        rule = parse_rrule("FREQ=DAILY;UNTIL=20260930T235959Z")
        self.assertEqual(rule["until"], datetime(2026, 9, 30, 23, 59, 59))

    def test_until_date_is_end_of_day(self):
        rule = parse_rrule("FREQ=DAILY;UNTIL=20260930")
        self.assertEqual(rule["until"], datetime(2026, 9, 30, 23, 59, 59))

    def test_until_bad_format(self):
        with self.assertRaises(RRuleError):
            parse_rrule("FREQ=DAILY;UNTIL=2026-09-30")

    def test_until_invalid_date(self):
        with self.assertRaises(RRuleError):
            parse_rrule("FREQ=DAILY;UNTIL=20260230")

    def test_empty_or_missing_freq(self):
        with self.assertRaises(RRuleError):
            parse_rrule("")
        with self.assertRaises(RRuleError):
            parse_rrule("INTERVAL=2")

    def test_bad_freq(self):
        with self.assertRaises(RRuleError):
            parse_rrule("FREQ=HOURLY")

    def test_bad_numbers(self):
        for text in ("FREQ=DAILY;INTERVAL=0", "FREQ=DAILY;COUNT=abc",
                     "FREQ=DAILY;COUNT=-1"):
            with self.assertRaises(RRuleError, msg=text):
                parse_rrule(text)

    def test_bad_byday(self):
        with self.assertRaises(RRuleError):
            parse_rrule("FREQ=WEEKLY;BYDAY=XX")

    def test_bad_bymonthday(self):
        with self.assertRaises(RRuleError):
            parse_rrule("FREQ=MONTHLY;BYMONTHDAY=32")

    def test_byday_only_for_weekly(self):
        with self.assertRaises(RRuleError):
            parse_rrule("FREQ=DAILY;BYDAY=MO")

    def test_bymonthday_only_for_monthly(self):
        with self.assertRaises(RRuleError):
            parse_rrule("FREQ=WEEKLY;BYMONTHDAY=1")

    def test_count_and_until_conflict(self):
        with self.assertRaises(RRuleError):
            parse_rrule("FREQ=DAILY;COUNT=3;UNTIL=20260930")

    def test_unknown_key(self):
        with self.assertRaises(RRuleError):
            parse_rrule("FREQ=DAILY;BYHOUR=9")


class TestIterOccurrences(unittest.TestCase):
    """发生时间展开语义（对齐 python-dateutil rrule 子集）"""

    def test_daily_series(self):
        rule = parse_rrule("FREQ=DAILY")
        got = [_fmt(d) for d in iter_occurrences(rule, datetime(2026, 1, 1, 8, 0), count=3)]
        self.assertEqual(got, ["2026-01-01 08:00:00", "2026-01-02 08:00:00",
                               "2026-01-03 08:00:00"])

    def test_daily_interval(self):
        rule = parse_rrule("FREQ=DAILY;INTERVAL=3")
        got = [_fmt(d) for d in iter_occurrences(rule, datetime(2026, 1, 1), count=3)]
        self.assertEqual(got, ["2026-01-01 00:00:00", "2026-01-04 00:00:00",
                               "2026-01-07 00:00:00"])

    def test_daily_until_inclusive(self):
        rule = parse_rrule("FREQ=DAILY;UNTIL=20260104")
        got = [_fmt(d) for d in iter_occurrences(rule, datetime(2026, 1, 1))]
        # UNTIL DATE 形式含当天（23:59:59 边界）
        self.assertEqual(len(got), 4)
        self.assertEqual(got[-1], "2026-01-04 00:00:00")

    def test_no_occurrence_before_until(self):
        rule = parse_rrule("FREQ=DAILY;UNTIL=20260101")
        got = list(iter_occurrences(rule, datetime(2026, 1, 5, 8, 0)))
        self.assertEqual(got, [])

    def test_dtstart_hits_rule_is_first(self):
        # 2026-09-30 是周三，dtstart 命中 BYDAY=WE 时算第一次发生
        rule = parse_rrule("FREQ=WEEKLY;BYDAY=WE")
        got = list(iter_occurrences(rule, datetime(2026, 9, 30, 9, 0), count=2))
        self.assertEqual(_fmt(got[0]), "2026-09-30 09:00:00")
        self.assertEqual(_fmt(got[1]), "2026-10-07 09:00:00")

    def test_weekly_byday(self):
        # dtstart 周三，首个命中的 BYDAY 是当周周五
        rule = parse_rrule("FREQ=WEEKLY;BYDAY=MO,FR")
        got = [_fmt(d) for d in iter_occurrences(rule, datetime(2026, 9, 30, 9, 0), count=4)]
        self.assertEqual(got, ["2026-10-02 09:00:00", "2026-10-05 09:00:00",
                               "2026-10-09 09:00:00", "2026-10-12 09:00:00"])

    def test_weekly_byday_interval(self):
        rule = parse_rrule("FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,FR")
        got = [_fmt(d) for d in iter_occurrences(rule, datetime(2026, 9, 28, 9, 0), count=4)]
        self.assertEqual(got, ["2026-09-28 09:00:00", "2026-10-02 09:00:00",
                               "2026-10-12 09:00:00", "2026-10-16 09:00:00"])

    def test_weekly_without_byday(self):
        rule = parse_rrule("FREQ=WEEKLY;INTERVAL=2")
        got = [_fmt(d) for d in iter_occurrences(rule, datetime(2026, 9, 28, 9, 0), count=3)]
        self.assertEqual(got, ["2026-09-28 09:00:00", "2026-10-12 09:00:00",
                               "2026-10-26 09:00:00"])

    def test_monthly_bymonthday(self):
        rule = parse_rrule("FREQ=MONTHLY;BYMONTHDAY=15")
        got = [_fmt(d) for d in iter_occurrences(rule, datetime(2026, 9, 20, 9, 0), count=4)]
        self.assertEqual(got, ["2026-10-15 09:00:00", "2026-11-15 09:00:00",
                               "2026-12-15 09:00:00", "2027-01-15 09:00:00"])

    def test_monthly_bymonthday_list(self):
        rule = parse_rrule("FREQ=MONTHLY;BYMONTHDAY=1,15")
        got = [_fmt(d) for d in iter_occurrences(rule, datetime(2026, 9, 20, 9, 0), count=4)]
        self.assertEqual(got, ["2026-10-01 09:00:00", "2026-10-15 09:00:00",
                               "2026-11-01 09:00:00", "2026-11-15 09:00:00"])

    def test_monthly_skips_missing_day(self):
        # 每月 31 号：2/4/6/9/11 月不存在，跳过（dateutil 语义）
        rule = parse_rrule("FREQ=MONTHLY")
        got = [_fmt(d) for d in iter_occurrences(rule, datetime(2026, 1, 31, 9, 0), count=4)]
        self.assertEqual(got, ["2026-01-31 09:00:00", "2026-03-31 09:00:00",
                               "2026-05-31 09:00:00", "2026-07-31 09:00:00"])

    def test_yearly_leap_day(self):
        # 默认 5 年兜底 horizon：2024 -> 2028 在界内，2032 被截断
        rule = parse_rrule("FREQ=YEARLY")
        got = [_fmt(d) for d in iter_occurrences(rule, datetime(2024, 2, 29, 9, 0))]
        self.assertEqual(got, ["2024-02-29 09:00:00", "2028-02-29 09:00:00"])
        # 显式扩大 horizon 后取到 2032（闰日不存在的年份被跳过）
        got = [_fmt(d) for d in iter_occurrences(rule, datetime(2024, 2, 29, 9, 0),
                                                  horizon_days=366 * 10)]
        self.assertEqual(got[:3], ["2024-02-29 09:00:00", "2028-02-29 09:00:00",
                                   "2032-02-29 09:00:00"])

    def test_horizon_cap_terminates(self):
        rule = parse_rrule("FREQ=DAILY")
        got = list(iter_occurrences(rule, datetime(2026, 1, 1), horizon_days=10))
        self.assertEqual(len(got), 11)
        self.assertEqual(_fmt(got[-1]), "2026-01-11 00:00:00")

    def test_bad_dtstart_type(self):
        with self.assertRaises(RRuleError):
            list(iter_occurrences(parse_rrule("FREQ=DAILY"), "2026-01-01"))


class TestNextOccurrence(unittest.TestCase):
    """next_occurrence：严格晚于参照点；不应用 COUNT"""

    def test_default_after_dtstart(self):
        rule = parse_rrule("FREQ=DAILY")
        nxt = next_occurrence(rule, datetime(2026, 1, 1, 8, 0))
        self.assertEqual(_fmt(nxt), "2026-01-02 08:00:00")

    def test_strictly_after_ref(self):
        rule = parse_rrule("FREQ=DAILY")
        nxt = next_occurrence(rule, datetime(2026, 1, 1, 8, 0),
                               after=datetime(2026, 1, 5, 8, 0))
        self.assertEqual(_fmt(nxt), "2026-01-06 08:00:00")

    def test_none_when_until_exceeded(self):
        rule = parse_rrule("FREQ=DAILY;UNTIL=20260105T080000")
        nxt = next_occurrence(rule, datetime(2026, 1, 1, 8, 0),
                              after=datetime(2026, 1, 5, 9, 0))
        self.assertIsNone(nxt)

    def test_ignores_rule_count(self):
        # COUNT 由调用方按已触发次数管理，next_occurrence 不提前截断
        rule = parse_rrule("FREQ=DAILY;COUNT=1")
        nxt = next_occurrence(rule, datetime(2026, 1, 1, 8, 0),
                              after=datetime(2026, 1, 3, 8, 0))
        self.assertEqual(_fmt(nxt), "2026-01-04 08:00:00")


class TestDescribeRule(unittest.TestCase):
    """中文可读描述"""

    def test_daily(self):
        self.assertEqual(describe_rule("FREQ=DAILY"), "每天")

    def test_daily_interval(self):
        self.assertEqual(describe_rule("FREQ=DAILY;INTERVAL=2"), "每隔 2 天")

    def test_weekly_byday(self):
        self.assertEqual(
            describe_rule("FREQ=WEEKLY;BYDAY=FR,MO;INTERVAL=2;COUNT=5"),
            "周一、周五，每隔 2 周，共 5 次")

    def test_weekly_without_byday(self):
        self.assertEqual(describe_rule("FREQ=WEEKLY", datetime(2026, 9, 28, 9, 0)),
                         "每周一")

    def test_monthly(self):
        self.assertEqual(describe_rule("FREQ=MONTHLY;BYMONTHDAY=15"), "每月 15 号")
        self.assertEqual(describe_rule("FREQ=MONTHLY;INTERVAL=2;BYMONTHDAY=15"),
                         "每隔 2 个月的 15 号")

    def test_yearly(self):
        self.assertEqual(describe_rule("FREQ=YEARLY", datetime(2024, 2, 29)),
                         "每年 2 月 29 日")

    def test_until_suffix(self):
        self.assertEqual(describe_rule("FREQ=DAILY;UNTIL=20261231T235959"),
                         "每天，至 2026-12-31 23:59")


class TestReminderManagerRecurring(unittest.TestCase):
    """reminder_manager 重复提醒集成：add / advance / 耗尽 / schtasks 映射"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import reminder_manager
        self.mgr = reminder_manager
        self.mgr.REMINDER_DIR = os.path.join(self.tmpdir, "reminders")
        self.mgr.REMINDER_FILE = os.path.join(self.mgr.REMINDER_DIR, "reminders.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_add_with_rrule_stores_rule_text(self, mock_task):
        added = self.mgr.add_reminder(datetime(2026, 10, 1, 9, 0), "周会",
                                      rrule="FREQ=WEEKLY;BYDAY=MO")
        self.assertEqual(added["rrule"], "FREQ=WEEKLY;BYDAY=MO")
        self.assertEqual(added["fired_count"], 0)
        self.assertTrue(mock_task.called)

    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_add_rejects_invalid_rrule(self, mock_task):
        with self.assertRaises(RRuleError):
            self.mgr.add_reminder(datetime(2026, 10, 1, 9, 0), "坏规则",
                                  rrule="FREQ=HOURLY")
        self.assertEqual(self.mgr.load_reminders(), [])
        self.assertFalse(mock_task.called)

    @patch("reminder_manager.delete_windows_task")
    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_advance_recurring_schedules_next(self, _c, _d):
        added = self.mgr.add_reminder(datetime(2026, 10, 1, 9, 0), "喝水",
                                      rrule="FREQ=DAILY")
        updated = self.mgr.advance_reminder(added["id"], now=datetime(2026, 10, 1, 9, 0, 1))
        self.assertEqual(updated["status"], "pending")
        self.assertEqual(updated["remind_at"], "2026-10-02 09:00:00")
        self.assertEqual(updated["fired_count"], 1)

    @patch("reminder_manager.delete_windows_task")
    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_advance_count_exhausted_marks_done(self, _c, _d):
        added = self.mgr.add_reminder(datetime(2026, 10, 1, 9, 0), "两次",
                                      rrule="FREQ=DAILY;COUNT=2")
        first = self.mgr.advance_reminder(added["id"], now=datetime(2026, 10, 1, 9, 0, 1))
        self.assertEqual(first["status"], "pending")
        self.assertEqual(first["remind_at"], "2026-10-02 09:00:00")
        second = self.mgr.advance_reminder(added["id"], now=datetime(2026, 10, 2, 9, 0, 1))
        self.assertEqual(second["status"], "done")
        self.assertEqual(second["fired_count"], 2)

    @patch("reminder_manager.delete_windows_task")
    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_advance_until_exhausted_marks_done(self, _c, _d):
        added = self.mgr.add_reminder(datetime(2026, 10, 1, 9, 0), "截止",
                                      rrule="FREQ=DAILY;UNTIL=20261001T090000")
        updated = self.mgr.advance_reminder(added["id"], now=datetime(2026, 10, 1, 9, 0, 1))
        self.assertEqual(updated["status"], "done")

    @patch("reminder_manager.delete_windows_task")
    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_advance_one_shot_marks_sent(self, _c, mock_delete):
        added = self.mgr.add_reminder(datetime(2026, 10, 1, 9, 0), "一次性")
        updated = self.mgr.advance_reminder(added["id"], now=datetime(2026, 10, 1, 9, 0, 1))
        self.assertEqual(updated["status"], "sent")
        self.assertIsNone(updated.get("rrule"))
        self.assertTrue(mock_delete.called)

    def test_advance_missing_id(self):
        self.assertIsNone(self.mgr.advance_reminder(9999))

    @patch("reminder_manager.create_windows_task", return_value=True)
    def test_describe_reminder_rule(self, _c):
        added = self.mgr.add_reminder(datetime(2026, 10, 1, 9, 0), "描述",
                                      rrule="FREQ=DAILY")
        loaded = self.mgr.load_reminders()[0]
        self.assertEqual(self.mgr.describe_reminder_rule(loaded), "每天")
        one_shot = self.mgr.add_reminder(datetime(2026, 10, 1, 10, 0), "无规则")
        self.assertIsNone(self.mgr.describe_reminder_rule(one_shot))

    def test_schtasks_schedule_args_mapping(self):
        from reminder_manager import _schtasks_schedule_args
        dt = datetime(2026, 10, 1, 9, 0)  # 周四
        self.assertEqual(_schtasks_schedule_args("FREQ=DAILY;INTERVAL=2", dt),
                         ["/sc", "daily", "/mo", "2"])
        self.assertEqual(_schtasks_schedule_args("FREQ=WEEKLY;BYDAY=MO,FR", dt),
                         ["/sc", "weekly", "/mo", "1", "/d", "MO,FR"])
        self.assertEqual(_schtasks_schedule_args("FREQ=WEEKLY", dt),
                         ["/sc", "weekly", "/mo", "1", "/d", "TH"])
        self.assertEqual(_schtasks_schedule_args("FREQ=MONTHLY;BYMONTHDAY=1,15", dt),
                         ["/sc", "monthly", "/mo", "1", "/d", "1,15"])
        self.assertEqual(_schtasks_schedule_args("FREQ=MONTHLY", dt),
                         ["/sc", "monthly", "/mo", "1", "/d", "1"])
        self.assertIsNone(_schtasks_schedule_args("FREQ=YEARLY", dt))
        self.assertIsNone(_schtasks_schedule_args(None, dt))
        self.assertIsNone(_schtasks_schedule_args("GARBAGE", dt))


if __name__ == "__main__":
    unittest.main(verbosity=2)
