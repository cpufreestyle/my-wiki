#!/usr/bin/env python3
"""
tests/test_wiki_links.py — wiki_links.py 双链引擎与 wiki_tool.py 新子命令
（capture / links / backlinks / orphans）单元测试。

全部使用临时目录构造的假 vault，纯标准库，不触碰真实笔记数据。
"""
import os
import subprocess
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import wiki_links


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class LinkEngineTests(unittest.TestCase):
    """双链解析 / 解析 / 反向链接 / 孤儿与失效链接"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _write(self.tmp, "projects/Alpha.md",
               "见 [[Beta]] 与 [[people/Bob|鲍勃]]，锚点见 [[concepts/X#章节]]。\n")
        _write(self.tmp, "concepts/X.md",
               "回链 [[projects/Alpha]]；自链 [[concepts/X]]。\n")
        _write(self.tmp, "daily/2026-09-26.md",
               "相对链接 [[../concepts/X]]，失效 [[missing/Note]]。\n")
        _write(self.tmp, "people/Bob.md", "鲍勃的档案。\n")
        _write(self.tmp, "Beta.md", "根目录孤儿笔记。\n")
        _write(self.tmp, "INDEX.md", "- [[projects/Alpha]]\n- [[people/Bob]]\n")
        _write(self.tmp, "inbox/quick-capture.md", "- 收件箱不参与链接图\n")
        _write(self.tmp, ".codebuddy/memory/m.md", "工具目录记忆 [[projects/Alpha]]\n")
        self.graph = wiki_links.scan_links(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_extract_links_strips_alias_and_anchor(self):
        links = wiki_links.extract_links("[[a#b|c]] 和 [[d/e]] 和 [[f|g|h]]")
        self.assertEqual(links, ["a", "d/e", "f"])

    def test_extract_links_empty(self):
        self.assertEqual(wiki_links.extract_links("没有链接"), [])
        self.assertEqual(wiki_links.extract_links(""), [])

    def test_iter_notes_skips_inbox_and_hidden(self):
        notes = list(wiki_links.iter_notes(self.tmp))
        self.assertIn("projects/Alpha.md", notes)
        self.assertFalse(any(n.startswith("inbox/") for n in notes))
        self.assertFalse(any(n.startswith(".") for n in notes))

    def test_resolve_root_relative(self):
        rel = wiki_links.resolve_target("projects/Alpha", "daily/x.md", self.tmp)
        self.assertEqual(rel, "projects/Alpha.md")
        rel = wiki_links.resolve_target("projects/Alpha.md", "x.md", self.tmp)
        self.assertEqual(rel, "projects/Alpha.md")

    def test_resolve_relative_to_source(self):
        rel = wiki_links.resolve_target("../concepts/X", "daily/2026-09-26.md", self.tmp)
        self.assertEqual(rel, "concepts/X.md")

    def test_resolve_bare_stem(self):
        rel = wiki_links.resolve_target("Beta", "projects/Alpha.md", self.tmp)
        self.assertEqual(rel, "Beta.md")

    def test_resolve_bare_stem_case_insensitive(self):
        rel = wiki_links.resolve_target("beta", "projects/Alpha.md", self.tmp)
        self.assertEqual(rel, "Beta.md")

    def test_resolve_missing_returns_none(self):
        self.assertIsNone(wiki_links.resolve_target("missing/Note", "daily/x.md", self.tmp))

    def test_scan_links_map(self):
        links = self.graph["links"]
        self.assertEqual(links["projects/Alpha.md"],
                         ["Beta.md", "people/Bob.md", "concepts/X.md"])
        self.assertEqual(links["daily/2026-09-26.md"], ["concepts/X.md"])

    def test_scan_detects_dangling(self):
        self.assertIn("missing/Note", self.graph["dangling"])
        self.assertEqual(self.graph["dangling"]["missing/Note"],
                         ["daily/2026-09-26.md"])

    def test_backlinks_ignore_self_links(self):
        back = wiki_links.build_backlinks(self.graph)
        self.assertEqual(back["projects/Alpha.md"], ["INDEX.md", "concepts/X.md"])
        # X 自链自己，不作为自己的反向链接
        self.assertNotIn("concepts/X.md", back.get("concepts/X.md", []))

    def test_orphans(self):
        back = wiki_links.build_backlinks(self.graph)
        orphans = wiki_links.find_orphans(self.graph, back,
                                           exclude=("INDEX.md", "README.md"))
        self.assertEqual(orphans, ["daily/2026-09-26.md"])

    def test_find_unresolved_sorted(self):
        unresolved = wiki_links.find_unresolved(self.graph)
        self.assertEqual(unresolved, [("missing/Note", ["daily/2026-09-26.md"])])

    def test_resolve_note_arg(self):
        self.assertEqual(wiki_links.resolve_note_arg("projects/Alpha", self.tmp),
                         "projects/Alpha.md")
        self.assertEqual(wiki_links.resolve_note_arg("Alpha", self.tmp),
                         "projects/Alpha.md")
        self.assertIsNone(wiki_links.resolve_note_arg("不存在", self.tmp))


class WikiToolCommandTests(unittest.TestCase):
    """wiki_tool.py 新子命令（进程级冒烟 + 单元）"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _write(self.tmp, "projects/Alpha.md", "见 [[Beta]]。\n")
        _write(self.tmp, "concepts/X.md", "回链 [[projects/Alpha]]。\n")
        _write(self.tmp, "Beta.md", "孤儿。\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *cli_args):
        env = dict(os.environ, MYWIKI_ROOT=str(self.tmp))
        return subprocess.run(
            [sys.executable, "wiki_tool.py", *cli_args],
            cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60)

    def test_capture_creates_inbox_file(self):
        result = self._run("capture", "买牛奶")
        self.assertEqual(result.returncode, 0, result.stderr)
        inbox = self.tmp / "inbox" / "quick-capture.md"
        self.assertTrue(inbox.exists())
        content = inbox.read_text(encoding="utf-8")
        self.assertIn("# 快速捕捉收件箱", content)
        self.assertIn("- [ ]", content)
        self.assertIn("买牛奶", content)

    def test_capture_skips_duplicate(self):
        self._run("capture", "买牛奶")
        result = self._run("capture", "买牛奶")
        self.assertEqual(result.returncode, 0)
        self.assertIn("[SKIP]", result.stdout)
        content = (self.tmp / "inbox" / "quick-capture.md").read_text(encoding="utf-8")
        self.assertEqual(content.count("买牛奶"), 1)

    def test_capture_writes_only_inbox_not_daily(self):
        self._run("capture", "写日报之前")
        self.assertFalse((self.tmp / "daily").exists())

    def test_backlinks_command(self):
        result = self._run("backlinks", "projects/Alpha")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("concepts/X.md", result.stdout)

    def test_links_command_with_arg(self):
        result = self._run("links", "projects/Alpha")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Beta.md", result.stdout)

    def test_links_command_without_arg(self):
        result = self._run("links")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TOP LINKS", result.stdout)

    def test_orphans_command(self):
        result = self._run("orphans")
        self.assertIn("concepts/X.md", result.stdout)
        self.assertNotIn("projects/Alpha.md", result.stdout)

    def test_backlinks_unknown_note(self):
        result = self._run("backlinks", "不存在的笔记")
        self.assertEqual(result.returncode, 0)
        self.assertIn("[NOT FOUND]", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
