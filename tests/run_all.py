#!/usr/bin/env python3
"""
tests/run_all.py — 一键运行所有网页结构测试

用法：
    python3 tests/run_all.py

等价于依次运行 test_mood_web / test_reminder_web / test_index，
任何一项失败即以非零退出码结束，便于 CI / 提交前自检。
"""
import sys
import unittest

LOADER = unittest.TestLoader()
SUITES = [
    "test_mood_web",
    "test_reminder_web",
    "test_index",
]


def build_suite():
    suite = unittest.TestSuite()
    for name in SUITES:
        try:
            module = __import__(name)
        except ImportError as e:
            raise SystemExit(f"无法导入测试模块 {name}: {e}")
        suite.addTests(LOADER.loadTestsFromModule(module))
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(build_suite())
    sys.exit(0 if result.wasSuccessful() else 1)
