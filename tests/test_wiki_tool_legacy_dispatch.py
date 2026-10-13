#!/usr/bin/env python3
"""wiki_tool.py 旧模块统一接线测试。

覆盖三件事：
1. 7 个新子命令各自路由到正确的模块文件，且透传参数正确
   （monkeypatch _load_legacy，不加载真模块，无副作用）；
2. 帮助文本包含全部新命令；
3. 旧模块 main(argv=None) 重构真的生效——只调安全入口（--help 触发
   SystemExit；memo 空参仅打印 help），绝不触发同步、起 server 或联网扫描。
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import wiki_tool  # noqa: E402

# argv -> (唯一模块名, 相对路径, 期望透传给模块 main 的参数)
EXPECTED_ROUTES = {
    ("video", "x.mp4", "--interval", "5"): (
        "_mywiki_video_analyze", "modules/video-analysis/analyze.py",
        ["x.mp4", "--interval", "5"]),
    ("memo", "list"): (
        "_mywiki_memo_sync", "modules/memo-sync/sync.py", ["list"]),
    ("sync-obsidian", "--vault", "documents"): (
        "_mywiki_obsidian_sync", "modules/obsidian-sync/sync.py",
        ["--vault", "documents"]),
    ("serve",): (
        "_mywiki_mcp_server", "modules/shared-wiki/mcp_server.py", []),
    ("agents",): (
        "_mywiki_agent_registry", "modules/shared-wiki/agent_registry.py", []),
    ("obsidian",): (
        "_mywiki_obsidian_bridge", "modules/shared-wiki/obsidian_bridge.py", []),
    ("broadcast", "wiki.updated", "daily/x.md"): (
        "_mywiki_agent_registry", "modules/shared-wiki/agent_registry.py",
        ["broadcast", "wiki.updated", "daily/x.md"]),
}

HELP_LINES = (
    "python wiki_tool.py video <path>",
    "python wiki_tool.py memo <sub>",
    "python wiki_tool.py sync-obsidian",
    "python wiki_tool.py serve",
    "python wiki_tool.py agents",
    "python wiki_tool.py obsidian",
    "python wiki_tool.py broadcast <event> [rel]",
)


def _run_with_argv(argv):
    """以给定 argv 调用 wiki_tool.main()，返回 (返回值, stdout 文本)。"""
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["wiki_tool.py"] + argv), redirect_stdout(buf):
        rc = wiki_tool.main()
    return rc, buf.getvalue()


class LegacyDispatchRoutingTest(unittest.TestCase):
    """7 个新命令路由到正确的模块文件，且参数透传正确。"""

    def setUp(self):
        self.loaded = []
        self.received = {}

        def fake_load(module_name, rel_path):
            def main(argv=None):
                self.loaded.append((module_name, rel_path))
                self.received[(module_name, rel_path)] = (
                    list(argv) if argv is not None else None)
                return 0
            return SimpleNamespace(main=main)

        patcher = mock.patch.object(wiki_tool, "_load_legacy", side_effect=fake_load)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_routes_and_argv_passthrough(self):
        for argv, (module_name, rel_path, expected) in EXPECTED_ROUTES.items():
            with self.subTest(cmd=argv[0]):
                rc, _ = _run_with_argv(list(argv))
                self.assertEqual(rc, 0)
                self.assertEqual(self.loaded, [(module_name, rel_path)])
                self.assertEqual(self.received[(module_name, rel_path)], expected)
                self.loaded.clear()
                self.received.clear()


class LegacyDispatchHelpTextTest(unittest.TestCase):
    """帮助文本包含全部新命令。"""

    def test_help_lists_all_new_commands(self):
        _, out = _run_with_argv(["help"])
        for line in HELP_LINES:
            self.assertIn(line, out)


class LegacyArgvRefactorTest(unittest.TestCase):
    """旧模块 main(argv=None) 重构真的生效（只调安全入口，无副作用）。"""

    @staticmethod
    def _load(unique_name, rel_path):
        return wiki_tool._load_legacy(unique_name, rel_path)

    def test_analyze_help_exits(self):
        mod = self._load("_test_video_analyze", "modules/video-analysis/analyze.py")
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit) as ctx:
            mod.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_memo_no_subcommand_prints_help(self):
        mod = self._load("_test_memo_sync", "modules/memo-sync/sync.py")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.main([])
        self.assertIsNone(rc)
        self.assertIn("push", buf.getvalue())

    def test_obsidian_sync_help_exits(self):
        mod = self._load("_test_obsidian_sync", "modules/obsidian-sync/sync.py")
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit) as ctx:
            mod.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
