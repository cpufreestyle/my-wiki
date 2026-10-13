#!/usr/bin/env python3
"""
tests/run_all.py — 一键运行项目的全部单元测试

用法：
    python3 tests/run_all.py

两处发现根：
  1. 本目录下的 test_*.py（网页与业务逻辑测试）
  2. modules/<模块>/test_*.py（与被测代码同目录的模块内核测试）
新增测试文件无需改动本脚本（避免手工清单漏注册导致测试被静默跳过）。
任何一项失败即以非零退出码结束，便于 CI / 提交前自检。

只读内容目录守卫：跑全套前对 brain/ daily/ wiki/ 做一次快照，跑完比对。
用例只要真实写进了这些用户内容目录，这里就会打印指名路径的报告并非零退出
（详见 tests/_immutable_guard.py 与 tests/test_immutable_guard.py）。
"""
import importlib.util
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
MODULES_DIR = TESTS_DIR.parent / "modules"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from _immutable_guard import changes, snapshot  # noqa: E402

LOADER = unittest.TestLoader()


def discover_suites():
    """返回按文件名排序的测试模块名列表。"""
    return sorted(p.stem for p in TESTS_DIR.glob("test_*.py"))


def discover_module_paths():
    """返回 tests/ 之外、与被测代码同目录的模块测试文件。"""
    return sorted(MODULES_DIR.glob("*/test_*.py"))


def load_module_test(path):
    """按文件路径加载模块测试（目录名含连字符，不能按包名 import）。"""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def build_suite():
    suite = unittest.TestSuite()
    for name in discover_suites():
        try:
            module = __import__(name)
        except ImportError as e:
            raise SystemExit(f"无法导入测试模块 {name}: {e}")
        suite.addTests(LOADER.loadTestsFromModule(module))
    for path in discover_module_paths():
        tests = LOADER.loadTestsFromModule(load_module_test(path))
        if tests.countTestCases() == 0:
            raise SystemExit(f"{path} 未定义任何 unittest 用例，不会被 CI 执行")
        suite.addTests(tests)
    return suite


def report_immutability(before):
    """比对只读目录快照；有写入就打印报告并返回 False。"""
    violations = changes(before, snapshot())
    if not violations:
        return True
    print("", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    print("只读内容目录被改写（AGENTS.md：brain/ daily/ wiki/ 用户内容，Agent 只读）：",
          file=sys.stderr)
    for line in violations:
        print("  " + line, file=sys.stderr)
    print("修法：把该用例的写入目标重定向到临时目录，参考 "
          "modules/shared-wiki/test_shared_wiki.py 里对 wiki_core.WIKI_ROOT 的处理。",
          file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    return False


if __name__ == "__main__":
    before = snapshot()
    tests_passed = False
    try:
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(build_suite())
        tests_passed = result.wasSuccessful()
    finally:
        dirs_untouched = report_immutability(before)
    sys.exit(0 if tests_passed and dirs_untouched else 1)
