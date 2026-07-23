#!/usr/bin/env python3
"""
test_shared_wiki.py — shared-wiki 模块的测试用例

用法:
    python modules/shared-wiki/test_shared_wiki.py
"""
import os
import sys
import json
import tempfile
import shutil
import importlib
from pathlib import Path

# 让脚本能 import 同目录模块
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PASS = 0
FAIL = 0
FAILED = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        FAILED.append(name)
        print(f"  ❌ {name}  {detail}")


# ---------------------------------------------------------------------------
# 1) wiki_core 测试（用临时 wiki 根目录隔离，避免污染真实 wiki）
# ---------------------------------------------------------------------------
def test_wiki_core():
    print("\n[1] wiki_core")
    import wiki_core

    tmp = Path(tempfile.mkdtemp(prefix="wiki_test_")).resolve()
    wiki_core.WIKI_ROOT = tmp
    wiki_core.CATEGORIES = ["daily", "projects", "concepts", "people", "brain"]

    # frontmatter round-trip
    meta = {"title": "T", "tags": ["a", "b"], "type": "daily", "date": "2026-07-12"}
    fm = wiki_core.build_frontmatter(meta)
    parsed, body = wiki_core.parse_frontmatter(fm + "hello world")
    check("parse/build frontmatter", parsed.get("title") == "T" and parsed.get("tags") == ["a", "b"], str(parsed))

    # write + read
    p = wiki_core.write_note("daily/2026-07-12.md", "# 今天\n测试内容")
    check("write_note 创建文件", Path(p).exists())
    note = wiki_core.read_note("daily/2026-07-12.md")
    check("read_note 读取正文", "测试内容" in note["body"], note["body"])
    check("read_note 自动 frontmatter", note["meta"].get("title") == "2026-07-12", str(note["meta"]))

    # append
    wiki_core.write_note("daily/2026-07-12.md", "追加的行", append=True)
    note2 = wiki_core.read_note("daily/2026-07-12.md")
    check("append 追加内容", "测试内容" in note2["body"] and "追加的行" in note2["body"], note2["body"])

    # search
    wiki_core.write_note("projects/proj_a.md", "关于 Alpha 项目的研究")
    hits = wiki_core.search("Alpha")
    check("search 命中", any("proj_a" in h["rel"] for h in hits), str(hits))

    # search_by_tag
    wiki_core.write_note("concepts/c1.md", "概念一", {"title": "C1", "tags": ["idea"]})
    tag_hits = wiki_core.search_by_tag("idea")
    check("search_by_tag 命中", any("c1" in h["rel"] for h in tag_hits), str(tag_hits))

    # list_notes
    notes = wiki_core.list_notes()
    check("list_notes 数量", len(notes) >= 3, str(len(notes)))

    # create_daily_note idempotent
    r1 = wiki_core.create_daily_note("2026-01-01")
    r2 = wiki_core.create_daily_note("2026-01-01")
    check("create_daily_note 幂等", r1 == r2 == "daily/2026-01-01.md", f"{r1} / {r2}")

    # update_index
    idx = wiki_core.update_index()
    check("update_index 生成 INDEX.md", Path(idx).exists())

    # query_links
    links = wiki_core.query_links("Alpha")
    check("query_links 返回相关笔记", len(links) >= 1, str(links))

    # export_manifest
    manifest = wiki_core.export_manifest()
    check("export_manifest 结构", manifest["note_count"] >= 3 and "categories" in manifest, str(manifest)[:120])

    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 2) agent_registry 测试
# ---------------------------------------------------------------------------
def test_agent_registry():
    print("\n[2] agent_registry")

    # 备份并清空 registry，避免污染
    import agent_registry
    reg_path = agent_registry.REGISTRY_PATH
    backup = None
    if reg_path.exists():
        backup = reg_path.read_text(encoding="utf-8")
        reg_path.unlink()

    try:
        # discover 至少返回 Obsidian (always)
        found = agent_registry.discover(auto_register=True)
        names = [a["name"] for a in found]
        check("discover 含 Obsidian", "Obsidian" in names, str(names))
        check("discover 返回列表", isinstance(found, list))

        # 注册一个自定义 agent
        agent_registry.register("TestAgent", "http://localhost:9999", "测试", ["wiki.read"])
        agents = agent_registry.list_agents()
        check("register 持久化", any(a["name"] == "TestAgent" for a in agents), str(agents))

        # broadcast 到不存在的 agent（应 skip/failed，不崩溃）
        res = agent_registry.broadcast("wiki.updated", {"rel": "daily/x.md"})
        check("broadcast 不崩溃", isinstance(res, dict) and "sent" in res, str(res))
    finally:
        if backup is not None:
            reg_path.write_text(backup, encoding="utf-8")
        elif reg_path.exists():
            reg_path.unlink()


# ---------------------------------------------------------------------------
# 3) obsidian_bridge 测试（不实际打开 Obsidian）
# ---------------------------------------------------------------------------
def test_obsidian_bridge():
    print("\n[3] obsidian_bridge")
    import obsidian_bridge

    # discover_vaults 返回列表（可能为空，但不应报错）
    vaults = obsidian_bridge.discover_vaults()
    check("discover_vaults 返回列表", isinstance(vaults, list), str(vaults))

    # vault_name 返回非空字符串
    name = obsidian_bridge.vault_name()
    check("vault_name 非空", isinstance(name, str) and len(name) > 0, repr(name))

    # open_note 返回命令字符串（macOS: open obsidian://...）
    cmd = obsidian_bridge.open_note("daily/2026-07-12.md")
    check("open_note 返回命令", isinstance(cmd, str) and ("open" in cmd or "obsidian://" in cmd), repr(cmd))

    # detect_wiki_vault 不崩溃（返回 dict 或 None）
    v = obsidian_bridge.detect_wiki_vault()
    check("detect_wiki_vault 类型", v is None or isinstance(v, dict), str(v))


# ---------------------------------------------------------------------------
# 4) mcp_server 测试（用注入 stdin 模拟 JSON-RPC，不启动真实服务）
# ---------------------------------------------------------------------------
def test_mcp_server():
    print("\n[4] mcp_server")
    import mcp_server

    # TOOLS 列表完整
    tool_names = [t["name"] for t in mcp_server.TOOLS]
    expected = {"wiki_search", "wiki_read", "wiki_write", "wiki_append",
                "wiki_list", "wiki_daily", "wiki_tags", "wiki_agents", "wiki_index"}
    check("TOOLS 包含全部 9 个", expected.issubset(set(tool_names)), str(tool_names))

    # _dispatch 直接调用
    out = mcp_server._dispatch("wiki_daily", {"date": "2026-03-03"})
    check("wiki_daily dispatch", out == "daily/2026-03-03.md", str(out))

    out2 = mcp_server._dispatch("wiki_index", {})
    check("wiki_index dispatch 返回路径", "INDEX.md" in out2, str(out2))

    # 未知工具错误处理
    err = mcp_server._dispatch("no_such_tool", {})
    check("未知工具返回 ERROR", err.startswith("[ERROR]"), err)

    # 模拟 JSON-RPC over stdio（用 os.pipe 注入输入，捕获输出）
    import io
    import threading

    # 准备输入：initialize + tools/list + tools/call(wiki_daily)
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "wiki_daily", "arguments": {"date": "2026-05-05"}}},
    ]
    input_text = "\n".join(json.dumps(r) for r in requests) + "\n"

    r, w = os.pipe()
    os.write(w, input_text.encode("utf-8"))
    os.close(w)

    old_stdin = sys.stdin
    old_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdin = os.fdopen(r, "r", encoding="utf-8")
    sys.stdout = captured
    try:
        mcp_server.serve_minimal_jsonrpc()
    except SystemExit as e:
        exit_code = e.code
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout

    responses = [l for l in captured.getvalue().splitlines() if l.strip()]
    ids = set()
    for line in responses:
        try:
            obj = json.loads(line)
            ids.add(obj.get("id"))
        except Exception:
            pass
    check("JSON-RPC 返回 3 条响应", len(responses) == 3, str(responses))
    check("JSON-RPC 含 id 1/2/3", {1, 2, 3}.issubset(ids), str(ids))
    check("JSON-RPC 正常退出 code=0", exit_code == 0, str(exit_code))


# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("MyWiki shared-wiki 测试套件")
    print("=" * 60)
    test_wiki_core()
    test_agent_registry()
    test_obsidian_bridge()
    test_mcp_server()

    print("\n" + "=" * 60)
    print(f"结果: {PASS} 通过 / {FAIL} 失败")
    if FAILED:
        print("失败项: " + ", ".join(FAILED))
    print("=" * 60)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
