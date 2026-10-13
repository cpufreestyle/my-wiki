#!/usr/bin/env python3
"""tests/test_immutable_guard.py — 只读内容目录守卫的行为单元测试

AGENTS.md 规定 brain/ / daily/ / wiki/ 是用户内容，Agent 只读不写；此前这条规则没有任何
自动化拦截——测试只要 import 到一个会写笔记的函数，就可能往用户真实 vault 里落文件，
而 3 秒的单元测试跑完后没人会去翻。这里守住拦截本身。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _immutable_guard import changes, snapshot


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="immutable_guard_"))
        (self.tmp / "daily").mkdir()
        (self.tmp / "daily" / "2026-10-09.md").write_text("原文", encoding="utf-8")
        (self.tmp / "daily" / ".obsidian").mkdir()
        (self.tmp / "daily" / ".obsidian" / "workspace.json").write_text(
            "{}", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_snapshot_skips_editor_config_dirs(self):
        """".obsidian 是 Obsidian 自己的窗口状态，每次点一下就变，不该当用户内容守。"""
        paths = set(snapshot(("daily",), root=self.tmp))
        self.assertNotIn(os.path.join("daily", ".obsidian", "workspace.json"), paths)
        self.assertIn(os.path.join("daily", "2026-10-09.md"), paths)

    def test_untouched_tree_reports_no_changes(self):
        before = snapshot(("daily",), root=self.tmp)
        self.assertEqual(changes(before, snapshot(("daily",), root=self.tmp)), [])

    def test_modifying_a_file_is_reported(self):
        before = snapshot(("daily",), root=self.tmp)
        (self.tmp / "daily" / "2026-10-09.md").write_text("被测试改了", encoding="utf-8")
        report = changes(before, snapshot(("daily",), root=self.tmp))
        self.assertEqual(len(report), 1, report)
        self.assertIn("2026-10-09.md", report[0])

    def test_new_and_deleted_files_are_reported(self):
        before = snapshot(("daily",), root=self.tmp)
        (self.tmp / "daily" / "dropped.md").write_text("x", encoding="utf-8")
        os.remove(self.tmp / "daily" / "2026-10-09.md")
        report = "\n".join(changes(before, snapshot(("daily",), root=self.tmp)))
        self.assertIn("dropped.md", report)
        self.assertIn("2026-10-09.md", report)

    def test_report_names_the_offending_path(self):
        """守卫要能指名道姓：只说「有变化」等于让人重跑一遍去找。"""
        before = snapshot(("daily",), root=self.tmp)
        (self.tmp / "daily" / "sub").mkdir()
        (self.tmp / "daily" / "sub" / "note.md").write_text("x", encoding="utf-8")
        report = "\n".join(changes(before, snapshot(("daily",), root=self.tmp)))
        self.assertIn(os.path.join("daily", "sub", "note.md"), report)


class DeclaredDirsTest(unittest.TestCase):
    def test_agents_md_dirs_are_covered(self):
        """规则改了目录列表时，守卫不能继续守着旧三份。"""
        from _immutable_guard import IMMUTABLE_DIRS
        self.assertEqual(set(IMMUTABLE_DIRS), {"brain", "daily", "wiki"})
        for name in IMMUTABLE_DIRS:
            self.assertTrue((Path(__file__).resolve().parent.parent / name).is_dir(),
                            "{} 不在仓库里".format(name))


class RunnerWiringTest(unittest.TestCase):
    """run_all.py 真的会把「写进只读目录的用例」变成非零退出码。

    在临时根目录里复刻一份 <tmp>/tests/{run_all.py,_immutable_guard.py} 加一个探针用例，
    REPO_ROOT 由被测文件自身位置推导，所以探针写的是 <tmp>/daily/——绝不碰仓库里的真实内容。
    """

    PROBE_WRITING = (
        "import unittest\n"
        "from pathlib import Path\n"
        "class Probe(unittest.TestCase):\n"
        "    def test_write(self):\n"
        "        root = Path(__file__).resolve().parent.parent\n"
        "        (root / 'daily').mkdir(parents=True, exist_ok=True)\n"
        "        (root / 'daily' / 'oops.md').write_text('written by probe', encoding='utf-8')\n"
    )
    PROBE_CLEAN = (
        "import unittest\n"
        "class Probe(unittest.TestCase):\n"
        "    def test_nothing(self):\n"
        "        self.assertTrue(True)\n"
    )

    def run_probe(self, probe_source):
        tmp = Path(tempfile.mkdtemp(prefix="immutable_runner_"))
        self.addCleanup(shutil.rmtree, tmp, True)
        tests_dir = tmp / "tests"
        tests_dir.mkdir()
        source_dir = Path(__file__).resolve().parent
        for name in ("run_all.py", "_immutable_guard.py"):
            shutil.copy(source_dir / name, tests_dir / name)
        (tests_dir / "test_probe.py").write_text(probe_source, encoding="utf-8")
        (tmp / "daily").mkdir()
        result = subprocess.run(
            [sys.executable, "run_all.py"], cwd=tests_dir,
            capture_output=True, text=True)
        return result

    def test_writing_probe_fails_the_runner_and_names_the_path(self):
        result = self.run_probe(self.PROBE_WRITING)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(os.path.join("daily", "oops.md"), result.stdout + result.stderr)

    def test_clean_probe_keeps_the_runner_green(self):
        """守卫不能是「永远失败」，否则上一个用例的存在毫无意义。"""
        result = self.run_probe(self.PROBE_CLEAN)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
