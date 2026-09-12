#!/usr/bin/env python3
"""
tests/test_collect_context.py — 多源上下文采集器（scripts/collect_context.py）单元测试

纯标准库实现（unittest + tempfile + importlib），无需第三方依赖，也不会真正
调用 lark-cli / wecom-cli。核心目标是守住 2026-09-10 评审后修复的几条回归：

  1. 飞书消息分页：窗口内超一页时必须拉全；被页数上限截断时不得推进
     last_synced（否则未同步区间的消息会被永久跳过）。
  2. 企微「调用失败」与「无数据」分开计数，真故障不被当成"最近没消息"掩盖。
  3. 长空档（两轮间隔 > 拉取窗口）时自动放大窗口，避免静默丢消息。
  4. dedup 索引命中 / 失效回退，且只在前言区间匹配 dedup_key。
  5. save_note 的 write / append / update / skip 四种动作回报正确。
  6. CLI 调用失败按指数退避重试；授权失效则快速失败并升级为 [alert]（不重试）。
  7. 会话列表分页拉全，不再被写死的 --page-size 20 硬截断。
  8. post 富文本 / merge_forward 合并转发 / 媒体消息不再被静默丢弃。
  9. 妙记采集不再用 os.chdir 污染进程全局工作目录。
"""
import contextlib
import importlib.util
import io
import json
import re
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "collect_context.py"


def _load_module():
    """按绝对路径加载被测模块（tests 目录不在 sys.path 上，故用 importlib）。"""
    spec = importlib.util.spec_from_file_location("collect_context", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()


def _quiet():
    """吞掉采集器的 stderr 输出，保持测试输出干净。"""
    return contextlib.redirect_stderr(io.StringIO())


class _TmpModuleState(unittest.TestCase):
    """把模块级的运行态文件重定向到临时目录，避免污染真实 config/。"""

    ATTRS = ("INDEX_FILE", "STATE_FILE", "LOG_FILE")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self._saved = {a: getattr(mod, a) for a in self.ATTRS}
        for a in self.ATTRS:
            setattr(mod, a, self.root / f".{a.lower()}")
        mod._reset_index_cache()
        self.addCleanup(self._restore)

    def _restore(self):
        for a, v in self._saved.items():
            setattr(mod, a, v)
        mod._reset_index_cache()


# ---- 拉取起点 / 窗口 --------------------------------------------------------

class NarrowStartTests(unittest.TestCase):
    def test_no_last_synced_uses_window(self):
        start, ls = mod._narrow_start(7, None)
        self.assertIsNone(ls)
        delta = datetime.now(mod.CST) - datetime.fromisoformat(start)
        self.assertAlmostEqual(delta.total_seconds(), 7 * 86400, delta=180)

    def test_recent_last_synced_wins(self):
        ls = (datetime.now(mod.CST) - timedelta(days=1)).isoformat(timespec="seconds")
        start, _ = mod._narrow_start(7, ls)
        self.assertEqual(datetime.fromisoformat(start).isoformat(timespec="seconds"), ls)

    def test_stale_last_synced_falls_back_to_window(self):
        ls = (datetime.now(mod.CST) - timedelta(days=30)).isoformat(timespec="seconds")
        start, _ = mod._narrow_start(7, ls)
        self.assertGreater(datetime.fromisoformat(start), datetime.fromisoformat(ls))


class EffectiveDaysTests(unittest.TestCase):
    def test_no_record_keeps_days(self):
        self.assertEqual(mod._effective_days({}, 7), 7)

    def test_broken_timestamp_keeps_days(self):
        self.assertEqual(mod._effective_days({"last_run_at": "不是时间"}, 7), 7)

    def test_short_gap_keeps_days(self):
        state = {"last_run_at": (datetime.now(mod.CST)
                                 - timedelta(days=1)).isoformat(timespec="seconds")}
        self.assertEqual(mod._effective_days(state, 7), 7)

    def test_long_gap_widens_window(self):
        state = {"last_run_at": (datetime.now(mod.CST)
                                 - timedelta(days=18)).isoformat(timespec="seconds")}
        with _quiet():
            eff = mod._effective_days(state, 7)
        self.assertGreater(eff, 7)
        self.assertGreaterEqual(eff, 19)


# ---- 前言解析 / dedup 查找 -------------------------------------------------

class FrontmatterTests(unittest.TestCase):
    def test_merge_updates_existing_and_adds_new_key(self):
        txt = "---\nsource: feishu\nchat_id: c1\n---\n\n# T\n\nbody\n"
        out = mod._merge_frontmatter(txt, {"chat_id": "c2", "last_synced": "2026-09-10T00:00:00+08:00"})
        self.assertIn("chat_id: c2", out)
        self.assertNotIn("chat_id: c1", out)
        self.assertIn("last_synced: 2026-09-10T00:00:00+08:00", out)
        self.assertIn("source: feishu", out)
        self.assertIn("body", out)

    def test_merge_noop_on_non_frontmatter(self):
        txt = "# 没有前言\n\n正文\n"
        self.assertEqual(mod._merge_frontmatter(txt, {"a": "b"}), txt)


class FindExistingTests(_TmpModuleState):
    def test_matches_frontmatter_only(self):
        cat = self.vault / "chat"
        cat.mkdir(parents=True)
        (cat / "x.md").write_text(
            "---\nsource: feishu\n---\n\n- 消息正文里提到 chat_id: oc_abc\n",
            encoding="utf-8")
        self.assertIsNone(mod._find_existing(self.vault, "chat", "chat_id: oc_abc"))

    def test_index_hit_then_fallback_scan(self):
        rep = {}
        p = mod.save_note("chat", "2026-09-10", "feishu", "群A", "- a",
                          meta={"chat_id": "c9"}, dedup_key="chat_id: c9",
                          vault=self.vault, report=rep)
        self.assertEqual(rep["action"], "write")
        # 索引命中
        self.assertEqual(mod._find_existing(self.vault, "chat", "chat_id: c9"), p)
        # 清空缓存 -> 回退全目录扫描并能回填索引
        mod._reset_index_cache()
        self.assertEqual(mod._find_existing(self.vault, "chat", "chat_id: c9"), p)
        self.assertEqual(mod._index_map("chat").get("chat_id: c9"), p.name)

    def test_index_not_registered_when_key_missing_from_frontmatter(self):
        mod.save_note("chat", "2026-09-10", "feishu", "群A", "- a",
                      dedup_key="chat_id: 未写入前言", vault=self.vault)
        self.assertNotIn("chat_id: 未写入前言", mod._index_map("chat"))
        self.assertIsNone(mod._find_existing(self.vault, "chat", "chat_id: 未写入前言"))

    def test_stale_index_entry_falls_back(self):
        cat = self.vault / "chat"
        cat.mkdir(parents=True)
        mod._reset_index_cache()
        mod._index_map("chat")["chat_id: gone"] = "已删除.md"
        self.assertIsNone(mod._find_existing(self.vault, "chat", "chat_id: gone"))


# ---- save_note 动作回报 ----------------------------------------------------

class SaveNoteActionTests(_TmpModuleState):
    def _save(self, body, meta=None, append=False):
        rep = {}
        path = mod.save_note("chat", "2026-09-10", "feishu", "群A", body,
                             meta=meta, dedup_key="chat_id: c1",
                             append=append, vault=self.vault, report=rep)
        return path, rep["action"]

    def test_actions_sequence(self):
        p, action = self._save("- **t1** (a): hi", meta={"chat_id": "c1"})
        self.assertEqual(action, "write")

        _, action = self._save("- **t1** (a): hi", meta={"chat_id": "c1"})
        self.assertEqual(action, "skip")

        _, action = self._save("- **t1** (a): hi\n- **t2** (b): yo",
                               meta={"chat_id": "c1"}, append=True)
        self.assertEqual(action, "append")

        # 无新行、仅 last_synced 变化 -> update（不算新增量）
        _, action = self._save("- **t1** (a): hi\n- **t2** (b): yo",
                               meta={"chat_id": "c1", "last_synced": "2026-09-10T00:00:00+08:00"},
                               append=True)
        self.assertEqual(action, "update")

    def test_append_dedupes_boundary_lines(self):
        self._save("- **t1** (a): hi", meta={"chat_id": "c1"})
        p, _ = self._save("- **t1** (a): hi\n- **t2** (b): yo",
                          meta={"chat_id": "c1"}, append=True)
        txt = p.read_text(encoding="utf-8")
        self.assertEqual(txt.count("- **t1** (a): hi"), 1)
        self.assertIn("- **t2** (b): yo", txt)


class CountsTests(unittest.TestCase):
    def test_action_mapping_and_touched(self):
        counts = mod._new_counts()
        for action in ("write", "append", "update", "skip", "未知"):
            mod._count_action(counts, {"action": action})
        self.assertEqual(counts["created"], 1)
        self.assertEqual(counts["appended"], 1)
        self.assertEqual(counts["updated"], 1)
        self.assertEqual(counts["skipped"], 2)  # skip + 未知动作兜底
        self.assertEqual(mod._touched(counts), 3)
        self.assertNotIn("touched", counts)  # touched 是派生值，不落盘

    def test_set_action_ignores_none(self):
        mod._set_action(None, "write")  # 不应抛异常
        rep = {}
        mod._set_action(rep, "append")
        self.assertEqual(rep["action"], "append")


# ---- 企微退避状态 ----------------------------------------------------------

class WecomStateTests(_TmpModuleState):
    def test_error_does_not_pollute_empty_counter(self):
        state = {}
        with _quiet():
            mod._wecom_record(state, had_data=False, error=True)
        self.assertEqual(state.get("wecom_consecutive_empty", 0), 0)
        self.assertEqual(state["wecom_consecutive_error"], 1)
        self.assertFalse(mod._wecom_should_skip(state)[0])

    def test_three_errors_trigger_backoff_with_error_reason(self):
        state = {}
        with _quiet():
            for _ in range(3):
                mod._wecom_record(state, had_data=False, error=True)
        skip, reason = mod._wecom_should_skip(state)
        self.assertTrue(skip)
        self.assertIn("调用失败", reason)

    def test_empty_trigger_backoff(self):
        state = {}
        with _quiet():
            for _ in range(3):
                mod._wecom_record(state, had_data=False)
        skip, reason = mod._wecom_should_skip(state)
        self.assertTrue(skip)
        self.assertIn("无数据", reason)

    def test_data_resets_both_counters(self):
        state = {}
        with _quiet():
            mod._wecom_record(state, had_data=False, error=True)
            mod._wecom_record(state, had_data=False, error=True)
            mod._wecom_record(state, had_data=True)
        self.assertEqual(state["wecom_consecutive_empty"], 0)
        self.assertEqual(state["wecom_consecutive_error"], 0)

    def test_backoff_only_within_same_day(self):
        state = {"wecom_consecutive_empty": 5, "wecom_last_attempt_date": "2000-01-01"}
        self.assertFalse(mod._wecom_should_skip(state)[0])

    def test_state_persisted_to_disk(self):
        with _quiet():
            mod._wecom_record({}, had_data=False, error=True)
        saved = json.loads(mod.STATE_FILE.read_text(encoding="utf-8"))
        self.assertEqual(saved["wecom_consecutive_error"], 1)


# ---- 飞书分页 --------------------------------------------------------------

PAGE_SIZE = 2


def _msg(i):
    return {"create_time": "2026-09-09T10:00:00+08:00", "content": f"M{i}",
            "sender": {"name": "a"}}


def _token_of(args):
    return args[args.index("--page-token") + 1] if "--page-token" in args else None


class LarkPaginationTests(unittest.TestCase):
    def setUp(self):
        self._orig_run = mod._run_cli
        self.addCleanup(self._restore)
        self.calls = []

    def _restore(self):
        mod._run_cli = self._orig_run

    def test_collects_all_pages_until_short_page(self):
        def fake(cli, *args, dry_run=False, **kw):
            tok = _token_of(list(args))
            self.calls.append(tok)
            if tok is None:
                return {"data": {"messages": [_msg(1), _msg(2)], "page_token": "p2"}}
            return {"data": {"messages": [_msg(3)]}}  # 不足一页 -> 停止
        mod._run_cli = fake
        items, truncated, failed = mod._fetch_lark_messages(
            "c1", "2026-09-01T00:00:00+08:00", {"feishu": {"page_size": PAGE_SIZE}}, False)
        self.assertEqual([m["content"] for m in items], ["M1", "M2", "M3"])
        self.assertEqual(self.calls, [None, "p2"])
        self.assertFalse(truncated)
        self.assertFalse(failed)

    def test_marks_truncated_when_max_pages_exhausted(self):
        def fake(cli, *args, dry_run=False, **kw):
            return {"data": {"messages": [_msg(1), _msg(2)], "page_token": "always"}}
        mod._run_cli = fake
        cfg = {"feishu": {"page_size": PAGE_SIZE, "max_pages": 3}}
        items, truncated, failed = mod._fetch_lark_messages("c1", "s", cfg, False)
        self.assertEqual(len(items), 6)
        self.assertTrue(truncated)
        self.assertFalse(failed)

    def test_first_page_failure_is_reported(self):
        mod._run_cli = lambda *a, **k: None
        items, truncated, failed = mod._fetch_lark_messages("c1", "s", {}, False)
        self.assertEqual(items, [])
        self.assertTrue(failed)

    def test_later_page_failure_keeps_partial_results(self):
        def fake(cli, *args, dry_run=False, **kw):
            if _token_of(list(args)):
                return None
            return {"data": {"messages": [_msg(1), _msg(2)], "page_token": "p2"}}
        mod._run_cli = fake
        items, truncated, failed = mod._fetch_lark_messages(
            "c1", "s", {"feishu": {"page_size": PAGE_SIZE}}, False)
        self.assertEqual(len(items), 2)
        self.assertFalse(failed)   # 已拿到部分，不判定为调用失败
        self.assertFalse(truncated)

    def test_missing_messages_key_on_first_page_is_failure(self):
        mod._run_cli = lambda *a, **k: {"data": {"code": 1, "msg": "boom"}}
        with _quiet():
            items, truncated, failed = mod._fetch_lark_messages("c1", "s", {}, False)
        self.assertEqual(items, [])
        self.assertTrue(failed)

    def test_empty_messages_is_not_failure(self):
        mod._run_cli = lambda *a, **k: {"data": {"messages": []}}
        items, truncated, failed = mod._fetch_lark_messages("c1", "s", {}, False)
        self.assertEqual(items, [])
        self.assertFalse(failed)
        self.assertFalse(truncated)


class FeishuCollectTests(_TmpModuleState):
    """端到端（不含真实 CLI）：截断时不得推进 last_synced。"""

    def _install_fake(self, page_token):
        def fake(cli, *args, dry_run=False, **kw):
            args = list(args)
            if len(args) >= 2 and args[0] == "im" and args[1] == "+chat-list":
                return {"data": {"chats": [{"chat_id": "c1", "name": "群A"}]}}
            body = {"messages": [_msg(0), _msg(1)]}
            if page_token:
                body["page_token"] = page_token
            return {"data": body}
        mod._run_cli = fake
        self.addCleanup(lambda: setattr(mod, "_run_cli", self._orig_run))

    def setUp(self):
        super().setUp()
        self._orig_run = mod._run_cli
        self.cfg = {"enabled": {"feishu": True},
                    "feishu": {"max_chats": 5, "page_size": PAGE_SIZE}}

    def _seed_note(self, last_synced):
        p = mod.save_note("chat", "2026-09-10", "feishu", "群A", "- **old** (a): 历史",
                          meta={"chat_id": "c1", "last_synced": last_synced},
                          dedup_key="chat_id: c1", vault=self.vault)
        return p

    def test_truncated_run_does_not_advance_last_synced(self):
        old = "2026-09-01T00:00:00+08:00"
        path = self._seed_note(old)
        self._install_fake(page_token="always")  # 每页都有下一页 -> 触发截断
        self.cfg["feishu"]["max_pages"] = 2
        with _quiet():
            counts = mod.collect_feishu(self.cfg, 7, False, self.vault)
        self.assertEqual(mod._parse_frontmatter(path).get("last_synced"), old)
        self.assertGreaterEqual(counts["appended"], 1)

    def test_complete_run_advances_last_synced(self):
        old = "2026-09-01T00:00:00+08:00"
        path = self._seed_note(old)
        self._install_fake(page_token=None)  # 单页拉全
        with _quiet():
            mod.collect_feishu(self.cfg, 7, False, self.vault)
        self.assertEqual(mod._parse_frontmatter(path).get("last_synced"),
                         "2026-09-09T10:00:00+08:00")


# ---- 运行日志 --------------------------------------------------------------

class RunLogTests(_TmpModuleState):
    def test_append_run_log_writes_jsonl(self):
        mod._append_run_log({"ts": "2026-09-10T10:00:00+08:00", "result": {"feishu": {"created": 1}}})
        mod._append_run_log({"ts": "2026-09-11T10:00:00+08:00", "result": {}})
        lines = mod.LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["result"]["feishu"]["created"], 1)

    def test_broken_log_path_is_silent(self):
        mod.LOG_FILE = Path("/definitely/not/writable/.log.jsonl")
        mod._append_run_log({"ts": "x"})  # 不应抛异常


# ---- 授权失效识别 / CLI 重试 ----------------------------------------------

class AuthErrorDetectionTests(unittest.TestCase):
    def test_recognises_markers(self):
        for text in ("need_user_authorization (user: ou_x)",
                     '{"subtype": "token_missing"}',
                     "invalid_access_token",
                     "Authentication failed"):
            self.assertTrue(mod._looks_like_auth_error(text), text)

    def test_network_errors_are_not_auth(self):
        for text in ("", "connection reset by peer", "ETIMEDOUT", "503 service unavailable"):
            self.assertFalse(mod._looks_like_auth_error(text), text)

    def test_alert_text_names_the_right_command(self):
        self.assertIn("lark-cli auth login",
                      mod._auth_alert_text(Path("/x/@larksuite/cli/scripts/run.js")))
        self.assertIn("企业微信", mod._auth_alert_text(Path("/x/@wecom/cli/bin/wecom.js")))
        self.assertTrue(mod._auth_alert_text(Path("/x/other.js")))


class ParseCliJsonTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(mod._parse_cli_json('{"a": 1}'), {"a": 1})

    def test_json_after_log_prefix(self):
        self.assertEqual(mod._parse_cli_json('some log\n{"a": 1}'), {"a": 1})

    def test_unparsable_returns_none(self):
        with _quiet():
            self.assertIsNone(mod._parse_cli_json("not json at all"))


class CliRunnerTests(unittest.TestCase):
    """_run_cli：指数退避重试、授权快速失败、cwd 透传。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        stub = Path(self.tmp.name) / "run.js"
        stub.write_text("// stub", encoding="utf-8")
        self._saved = (mod.QCLOW_NODE, mod.LARK_CLI)
        mod.QCLOW_NODE = stub
        mod.LARK_CLI = stub
        self.addCleanup(self._restore)
        self.sleeps = []

    def _restore(self):
        mod.QCLOW_NODE, mod.LARK_CLI = self._saved

    @staticmethod
    def _result(rc=0, stdout="", stderr=""):
        return mock.Mock(returncode=rc, stdout=stdout, stderr=stderr)

    def test_retries_then_succeeds(self):
        calls = []

        def counting_run(cmd, **kw):
            calls.append(cmd)
            if len(calls) == 1:
                return self._result(rc=1, stdout="", stderr="flake")
            return self._result(rc=0, stdout='{"data": {"ok": 1}}')

        with mock.patch.object(mod.subprocess, "run", side_effect=counting_run), \
                mock.patch.object(mod.time, "sleep", side_effect=self.sleeps.append), \
                _quiet():
            out = mod._run_cli(mod.LARK_CLI, "im", "+chat-list", retries=1)
        self.assertEqual(out, {"data": {"ok": 1}})
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.sleeps, [1])  # 指数退避首档 1s

    def test_exponential_backoff_and_give_up(self):
        with mock.patch.object(mod.subprocess, "run",
                               return_value=self._result(rc=1, stdout="", stderr="flake")), \
                mock.patch.object(mod.time, "sleep", side_effect=self.sleeps.append), \
                _quiet():
            self.assertIsNone(mod._run_cli(mod.LARK_CLI, "x", retries=2))
        self.assertEqual(self.sleeps, [1, 2])

    def test_auth_failure_fails_fast_without_retry(self):
        stderr = '{"error": {"subtype": "token_missing", "message": "need_user_authorization"}}'
        run_mock = mock.Mock(return_value=self._result(rc=1, stdout="", stderr=stderr))
        with mock.patch.object(mod.subprocess, "run", run_mock), \
                mock.patch.object(mod.time, "sleep", side_effect=self.sleeps.append), \
                _quiet():
            self.assertIsNone(mod._run_cli(mod.LARK_CLI, "x", retries=3))
        self.assertEqual(run_mock.call_count, 1)
        self.assertEqual(self.sleeps, [])

    def test_timeout_is_retried(self):
        run_mock = mock.Mock(side_effect=[subprocess.TimeoutExpired("cmd", 120),
                                          self._result(rc=0, stdout='{"ok": true}')])
        with mock.patch.object(mod.subprocess, "run", run_mock), \
                mock.patch.object(mod.time, "sleep", side_effect=self.sleeps.append), \
                _quiet():
            self.assertEqual(mod._run_cli(mod.LARK_CLI, "x"), {"ok": True})
        self.assertEqual(run_mock.call_count, 2)

    def test_dry_run_does_not_execute(self):
        run_mock = mock.Mock()
        with mock.patch.object(mod.subprocess, "run", run_mock), _quiet():
            self.assertIsNone(mod._run_cli(mod.LARK_CLI, "x", dry_run=True))
        run_mock.assert_not_called()

    def test_missing_runtime_is_reported(self):
        mod.QCLOW_NODE = Path(self.tmp.name) / "不存在"
        with _quiet():
            self.assertIsNone(mod._run_cli(mod.LARK_CLI, "x"))

    def test_cwd_is_passed_to_subprocess(self):
        workdir = Path(self.tmp.name)
        run_mock = mock.Mock(return_value=self._result(rc=0, stdout='{"ok": true}'))
        with mock.patch.object(mod.subprocess, "run", run_mock), _quiet():
            mod._run_cli(mod.LARK_CLI, "x", cwd=workdir)
        self.assertEqual(run_mock.call_args.kwargs.get("cwd"), workdir)


# ---- 富文本 / 媒体内容解析 -------------------------------------------------

class LarkContentTests(unittest.TestCase):
    def test_plain_text_passthrough(self):
        self.assertEqual(mod._extract_lark_content({"content": "hello"}),
                         "hello")

    def test_card_tags_are_stripped(self):
        m = {"content": '<card title="t">**正文**</card>'}
        self.assertEqual(mod._extract_lark_content(m), "**正文**")

    def test_post_json_is_rendered(self):
        m = {"message_type": "post",
             "content": json.dumps({
                 "title": "日报",
                 "content": [[{"tag": "text", "text": "今天"},
                              {"tag": "a", "text": "详见", "href": "http://x"}],
                             [{"tag": "at", "user_name": "Michael"},
                              {"tag": "text", "text": "请看"}]],
             })}
        out = mod._extract_lark_content(m)
        self.assertIn("日报", out)
        self.assertIn("今天详见", out)
        self.assertIn("@Michael请看", out)

    def test_post_with_invalid_json_falls_back_to_raw(self):
        m = {"message_type": "post", "content": "不是 JSON 的富文本"}
        self.assertEqual(mod._extract_lark_content(m), "不是 JSON 的富文本")

    def test_merge_forward_gets_placeholder(self):
        m = {"message_type": "merge_forward", "content": json.dumps({"title": "聊天记录"})}
        self.assertEqual(mod._extract_lark_content(m), "[合并转发] 聊天记录")
        self.assertEqual(mod._extract_lark_content(
            {"message_type": "merge_forward", "content": "x"}), "[合并转发]")

    def test_media_types_get_placeholder(self):
        self.assertEqual(mod._extract_lark_content({"message_type": "image", "content": ""}),
                         "[image]")
        self.assertEqual(mod._extract_lark_content({"message_type": "file", "content": ""}),
                         "[file]")

    def test_non_string_media_content(self):
        self.assertEqual(mod._extract_lark_content(
            {"message_type": "image", "content": {"k": "v"}}), "[image]")

    def test_non_string_text_content_is_empty(self):
        self.assertEqual(mod._extract_lark_content(
            {"message_type": "text", "content": {"k": "v"}}), "")

    def test_render_post_without_title(self):
        out = mod._render_post({"content": [[{"tag": "text", "text": "A"}],
                                            [{"tag": "text", "text": "B"}]]})
        self.assertEqual(out, "A / B")

    def test_render_post_ignores_unknown_and_malformed_nodes(self):
        out = mod._render_post({"content": ["不是数组",
                                            [{"tag": "unknown", "text": "X"},
                                             "不是字典",
                                             {"tag": "text", "text": "Y"}]]})
        self.assertEqual(out, "Y")


# ---- 会话列表分页 ----------------------------------------------------------

class LarkChatPaginationTests(unittest.TestCase):
    def setUp(self):
        self._orig_run = mod._run_cli
        self.addCleanup(lambda: setattr(mod, "_run_cli", self._orig_run))
        self.tokens = []

    def test_collects_all_chat_pages(self):
        def fake(cli, *args, dry_run=False, **kw):
            tok = _token_of(list(args))
            self.tokens.append(tok)
            if tok is None:
                return {"data": {"chats": [{"chat_id": "c1"}, {"chat_id": "c2"}],
                                 "page_token": "p2"}}
            return {"data": {"chats": [{"chat_id": "c3"}]}}  # 不足一页 -> 停止
        mod._run_cli = fake
        chats, failed = mod._fetch_lark_chats(
            {"feishu": {"chat_page_size": 2}}, False)
        self.assertEqual([c["chat_id"] for c in chats], ["c1", "c2", "c3"])
        self.assertEqual(self.tokens, [None, "p2"])
        self.assertFalse(failed)

    def test_never_caps_at_page_size(self):
        """回归：旧实现写死 --page-size 20，第 21 个会话永远采不到。"""
        page = [{"chat_id": f"c{i}"} for i in range(20)]
        pages = [{"data": {"chats": page, "page_token": "p2"}},
                 {"data": {"chats": [{"chat_id": "c20"}]}}]
        seq = iter(pages)
        mod._run_cli = lambda *a, **k: next(seq)
        chats, failed = mod._fetch_lark_chats({"feishu": {"chat_page_size": 20}}, False)
        self.assertEqual(len(chats), 21)
        self.assertEqual(chats[-1]["chat_id"], "c20")

    def test_failure_on_first_page_is_reported(self):
        mod._run_cli = lambda *a, **k: None
        chats, failed = mod._fetch_lark_chats({}, False)
        self.assertEqual(chats, [])
        self.assertTrue(failed)

    def test_later_page_failure_keeps_first_page(self):
        seq = iter([{"data": {"chats": [{"chat_id": "c1"}, {"chat_id": "c2"}],
                              "page_token": "p2"}},
                    None])
        mod._run_cli = lambda *a, **k: next(seq)
        chats, failed = mod._fetch_lark_chats({"feishu": {"chat_page_size": 2}}, False)
        self.assertEqual(len(chats), 2)
        self.assertFalse(failed)

    def test_missing_chats_key_is_failure(self):
        mod._run_cli = lambda *a, **k: {"data": {"code": 1}}
        with _quiet():
            chats, failed = mod._fetch_lark_chats({}, False)
        self.assertTrue(failed)

    def test_warns_when_max_pages_exhausted(self):
        mod._run_cli = lambda *a, **k: {
            "data": {"chats": [{"chat_id": "c1"}, {"chat_id": "c2"}],
                     "page_token": "always"}}
        with _quiet():
            chats, failed = mod._fetch_lark_chats(
                {"feishu": {"chat_page_size": 2, "chat_max_pages": 2}}, False)
        self.assertEqual(len(chats), 4)
        self.assertFalse(failed)


# ---- 源码卫生 --------------------------------------------------------------

class SourceHygieneTests(unittest.TestCase):
    def test_no_global_chdir(self):
        """回归：妙记采集不得再用 os.chdir 污染进程全局工作目录。

        只匹配真实调用（含括号），避免把注释/docstring 里的说明文字也算进来。
        """
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\bos\.chdir\s*\(", src),
                          "发现真实 os.chdir() 调用，应改用 subprocess 的 cwd 参数")


if __name__ == "__main__":
    unittest.main(verbosity=2)
