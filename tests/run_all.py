#!/usr/bin/env python3
"""
tests/run_all.py — 一键运行 tests/ 下的全部单元测试

用法：
    python3 tests/run_all.py

自动发现本目录下所有 test_*.py 并依次运行，新增测试文件无需改动本脚本
（避免手工清单漏注册导致测试被静默跳过）。任何一项失败即以非零退出码
结束，便于 CI / 提交前自检。
"""
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

LOADER = unittest.TestLoader()


def discover_suites():
    """返回按文件名排序的测试模块名列表。"""
    return sorted(p.stem for p in TESTS_DIR.glob("test_*.py"))


def build_suite():
    suite = unittest.TestSuite()
    for name in discover_suites():
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
