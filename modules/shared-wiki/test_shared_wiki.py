#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_shared_wiki.py — shared-wiki 内核（wiki_core / agent_registry /
obsidian_bridge / mcp_server）的单元测试

用法:
    python3 tests/run_all.py                      # 统一运行器会自动收集本文件
    python3 modules/shared-wiki/test_shared_wiki.py   # 单独运行

所有写操作都落在临时目录：内核的真实 WIKI_ROOT 指向仓库外的 Obsidian vault
（`find_wiki_root()`），若隔离失效就会把测试笔记写进用户的知识库。
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# 让脚本能 import 同目录模块
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import wiki_core  # noqa: E402


class TempWikiRootMixin:
    """把内核写操作重定向到临时 wiki 根目录"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="shared_wiki_test_")).resolve()
        cls.real_root = wiki_core.WIKI_ROOT
        wiki_core.WIKI_ROOT = cls.tmp
        wiki_core.CATEGORIES = ["daily", "projects", "concepts", "people", "brain"]

    @classmethod
    def tearDownClass(cls):
        wiki_core.WIKI_ROOT = cls.real_root
        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestWikiCore(TempWikiRootMixin, unittest.TestCase):
    """wiki_core 读写、检索与清单"""

    def test_frontmatter_round_trip(self):
        meta = {"title": "T", "tags": ["a", "b"], "type": "daily", "date": "2026-07-12"}
        fm = wiki_core.build_frontmatter(meta)
        parsed, body = wiki_core.parse_frontmatter(fm + "hello world")
        self.assertEqual(parsed.get("title"), "T")
        self.assertEqual(parsed.get("tags"), ["a", "b"])
        self.assertEqual(body, "hello world")

    def test_write_and_read_note(self):
        path = wiki_core.write_note("daily/2026-07-12.md", "# 今天\n测试内容")
        self.assertTrue(Path(path).exists())
        note = wiki_core.read_note("daily/2026-07-12.md")
        self.assertIn("测试内容", note["body"])

    def test_read_note_adds_frontmatter_with_title(self):
        wiki_core.write_note("daily/2026-07-12.md", "# 今天\n测试内容")
        note = wiki_core.read_note("daily/2026-07-12.md")
        self.assertEqual(note["meta"].get("title"), "2026-07-12")

    def test_append_keeps_previous_body(self):
        wiki_core.write_note("daily/2026-07-12.md", "# 今天\n测试内容")
        wiki_core.write_note("daily/2026-07-12.md", "追加的行", append=True)
        body = wiki_core.read_note("daily/2026-07-12.md")["body"]
        self.assertIn("测试内容", body)
        self.assertIn("追加的行", body)

    def test_search_hits_written_note(self):
        wiki_core.write_note("projects/proj_a.md", "关于 Alpha 项目的研究")
        hits = wiki_core.search("Alpha")
        self.assertTrue(any("proj_a" in h["rel"] for h in hits), hits)

    def test_search_by_tag_hits(self):
        wiki_core.write_note("concepts/c1.md", "概念一", {"title": "C1", "tags": ["idea"]})
        hits = wiki_core.search_by_tag("idea")
        self.assertTrue(any("c1" in h["rel"] for h in hits), hits)

    def test_list_notes_returns_written_notes(self):
        wiki_core.write_note("daily/2026-07-12.md", "正文")
        wiki_core.write_note("projects/proj_a.md", "正文")
        wiki_core.write_note("concepts/c1.md", "正文")
        self.assertGreaterEqual(len(wiki_core.list_notes()), 3)

    def test_create_daily_note_is_idempotent(self):
        first = wiki_core.create_daily_note("2026-01-01")
        second = wiki_core.create_daily_note("2026-01-01")
        self.assertEqual(first, "daily/2026-01-01.md")
        self.assertEqual(first, second)

    def test_update_index_writes_index_file(self):
        wiki_core.write_note("daily/2026-07-12.md", "正文")
        index_path = Path(wiki_core.update_index())
        self.assertTrue(index_path.exists())

    def test_query_links_returns_related_notes(self):
        wiki_core.write_note("projects/proj_a.md", "关于 Alpha 项目的研究")
        self.assertGreaterEqual(len(wiki_core.query_links("Alpha")), 1)

    def test_export_manifest_structure(self):
        wiki_core.write_note("daily/2026-07-12.md", "正文")
        wiki_core.write_note("projects/proj_a.md", "正文")
        wiki_core.write_note("concepts/c1.md", "正文")
        manifest = wiki_core.export_manifest()
        self.assertGreaterEqual(manifest["note_count"], 3)
        self.assertIn("categories", manifest)

    def test_kernel_writes_stay_inside_temp_root(self):
        """隔离守卫：真实 vault 不能被测试写入"""
        wiki_core.write_note("daily/2026-07-13.md", "正文")
        self.assertTrue((self.tmp / "daily" / "2026-07-13.md").exists())
        self.assertFalse((Path(self.real_root) / "daily" / "2026-07-13.md").exists())


class TestAgentRegistry(unittest.TestCase):
    """agent_registry 发现、注册与广播"""

    def setUp(self):
        import agent_registry
        self.agent_registry = agent_registry
        self.real_path = agent_registry.REGISTRY_PATH
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="registry_test_"))
        agent_registry.REGISTRY_PATH = self.tmp_dir / "registry.json"

    def tearDown(self):
        self.agent_registry.REGISTRY_PATH = self.real_path
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_discover_includes_obsidian(self):
        found = self.agent_registry.discover(auto_register=True)
        self.assertIn("Obsidian", [a["name"] for a in found])

    def test_discover_returns_list(self):
        self.assertIsInstance(self.agent_registry.discover(auto_register=True), list)

    def test_register_persists(self):
        self.agent_registry.register("TestAgent", "http://localhost:9999", "测试", ["wiki.read"])
        agents = self.agent_registry.list_agents()
        self.assertTrue(any(a["name"] == "TestAgent" for a in agents), agents)

    def test_broadcast_survives_unreachable_agent(self):
        result = self.agent_registry.broadcast("wiki.updated", {"rel": "daily/x.md"})
        self.assertIsInstance(result, dict)
        self.assertIn("sent", result)

    def test_registry_never_touches_shipped_file(self):
        self.agent_registry.register("TestAgent", "http://localhost:9999", "测试", ["wiki.read"])
        self.assertFalse(self.real_path.exists() and "TestAgent" in self.real_path.read_text(encoding="utf-8"))


class TestObsidianBridge(unittest.TestCase):
    """obsidian_bridge 只读探测与 URI 构造（不打开 Obsidian）"""

    def setUp(self):
        import obsidian_bridge
        self.bridge = obsidian_bridge

    def test_discover_vaults_returns_list(self):
        self.assertIsInstance(self.bridge.discover_vaults(), list)

    def test_vault_name_is_non_empty_string(self):
        name = self.bridge.vault_name()
        self.assertIsInstance(name, str)
        self.assertTrue(len(name) > 0, repr(name))

    def test_open_note_returns_command_string(self):
        cmd = self.bridge.open_note("daily/2026-07-12.md")
        self.assertIsInstance(cmd, str)
        self.assertTrue("open" in cmd or "obsidian://" in cmd, repr(cmd))

    def test_detect_wiki_vault_does_not_crash(self):
        vault = self.bridge.detect_wiki_vault()
        self.assertTrue(vault is None or isinstance(vault, dict))


class TestMcpServer(TempWikiRootMixin, unittest.TestCase):
    """mcp_server 工具表、dispatch 与最小 JSON-RPC stdio 协议"""

    def setUp(self):
        import mcp_server
        self.server = mcp_server

    def test_tools_cover_all_nine_declared_tools(self):
        tool_names = {t["name"] for t in self.server.TOOLS}
        expected = {"wiki_search", "wiki_read", "wiki_write", "wiki_append",
                    "wiki_list", "wiki_daily", "wiki_tags", "wiki_agents", "wiki_index"}
        self.assertTrue(expected.issubset(tool_names), tool_names)

    def test_dispatch_wiki_daily(self):
        self.assertEqual(self.server._dispatch("wiki_daily", {"date": "2026-03-03"}),
                         "daily/2026-03-03.md")

    def test_dispatch_wiki_index_returns_path(self):
        self.assertIn("INDEX.md", self.server._dispatch("wiki_index", {}))

    def test_dispatch_unknown_tool_returns_error_prefix(self):
        self.assertTrue(self.server._dispatch("no_such_tool", {}).startswith("[ERROR]"))

    def test_serve_minimal_jsonrpc_answers_every_request(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "wiki_daily", "arguments": {"date": "2026-05-05"}}},
        ]
        input_text = "\n".join(json.dumps(r) for r in requests) + "\n"

        read_fd, write_fd = os.pipe()
        os.write(write_fd, input_text.encode("utf-8"))
        os.close(write_fd)

        old_stdin, old_stdout = sys.stdin, sys.stdout
        captured = io.StringIO()
        exit_code = None
        stdin_pipe = os.fdopen(read_fd, "r", encoding="utf-8")
        sys.stdin = stdin_pipe
        sys.stdout = captured
        try:
            self.server.serve_minimal_jsonrpc()
        except SystemExit as exc:
            exit_code = exc.code
        finally:
            sys.stdin, sys.stdout = old_stdin, old_stdout
            stdin_pipe.close()

        responses = [line for line in captured.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(responses), 3, responses)
        ids = set()
        for line in responses:
            ids.add(json.loads(line).get("id"))
        self.assertTrue({1, 2, 3}.issubset(ids), ids)
        self.assertEqual(exit_code, 0)

    def test_jsonrpc_flow_writes_only_into_temp_root(self):
        """dispatch 走的是被隔离的 wiki_core，真实 vault 不应出现这则日记"""
        self.server._dispatch("wiki_daily", {"date": "2026-06-06"})
        self.assertTrue((self.tmp / "daily" / "2026-06-06.md").exists())
        self.assertFalse((Path(self.real_root) / "daily" / "2026-06-06.md").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
