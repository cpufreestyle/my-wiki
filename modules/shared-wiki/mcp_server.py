#!/usr/bin/env python3
"""
mcp_server.py — MyWiki 共享 Wiki MCP Server

把 MyWiki 暴露为标准的 Model Context Protocol (MCP) Server，
让任何支持 MCP 的 AI Agent（Claude Desktop、Cursor、OpenClaw、
Cline 等）都能直接读写这个共享 Wiki，而无需各自实现文件逻辑。

暴露的工具 (tools):
  - wiki_search        全文搜索
  - wiki_read          读取一篇笔记
  - wiki_write         创建/覆盖笔记
  - wiki_append        向笔记追加内容
  - wiki_list          列出笔记
  - wiki_daily         创建/获取今日日记
  - wiki_tags          按标签查询
  - wiki_agents        列出发现的 Agent
  - wiki_index         重建索引

传输方式: stdio (MCP 标准)，由宿主 Agent 启动本进程。

依赖: mcp (pip install mcp)。若未安装，自动降级为 JSON-RPC over stdio 的
      最小实现，保证仍然可用。
"""
import sys
import json
import asyncio
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 复用共享内核
sys.path.insert(0, str(Path(__file__).parent))
from wiki_core import (  # noqa: E402
    search, read_note, write_note, list_notes,
    create_daily_note, search_by_tag, update_index, semantic_search,
)
from agent_registry import discover, list_agents  # noqa: E402


# ---------------------------------------------------------------------------
# 工具定义
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "wiki_search",
        "description": "在共享 Wiki 中全文搜索笔记，返回命中片段",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "wiki_read",
        "description": "按相对路径读取一篇笔记 (如 daily/2026-07-12.md)",
        "inputSchema": {
            "type": "object",
            "properties": {"rel_path": {"type": "string"}},
            "required": ["rel_path"],
        },
    },
    {
        "name": "wiki_write",
        "description": "创建或覆盖一篇笔记",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rel_path": {"type": "string", "description": "相对路径"},
                "body": {"type": "string", "description": "正文 (Markdown)"},
                "title": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["rel_path", "body"],
        },
    },
    {
        "name": "wiki_append",
        "description": "向已有笔记追加内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rel_path": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["rel_path", "body"],
        },
    },
    {
        "name": "wiki_list",
        "description": "列出 Wiki 中的笔记，可按分类过滤",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "daily/projects/concepts/people 或留空"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    {
        "name": "wiki_daily",
        "description": "获取或创建今日日记，返回相对路径",
        "inputSchema": {
            "type": "object",
            "properties": {"date": {"type": "string", "description": "YYYY-MM-DD，默认今天"}},
        },
    },
    {
        "name": "wiki_tags",
        "description": "按标签查询笔记",
        "inputSchema": {
            "type": "object",
            "properties": {"tag": {"type": "string"}},
            "required": ["tag"],
        },
    },
    {
        "name": "wiki_agents",
        "description": "列出电脑里被发现/登记的 AI Agent",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "wiki_semantic_search",
        "description": "语义检索 Wiki（BM25 或本地 Ollama embedding），比全文搜索更懂意图，返回相关片段与打分",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言查询"},
                "limit": {"type": "integer", "default": 10},
                "mode": {"type": "string", "enum": ["bm25", "ollama"], "description": "检索模式，默认 bm25"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "wiki_index",
        "description": "重建 Wiki 的 INDEX.md 统一索引",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "wiki_daily_briefing",
        "description": "获取今日简报：聚合当日日记、心情记录、待办提醒、最近 RSS 摘要，一次调用掌握全天状态",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD，默认今天"},
            },
        },
    },
]


def _dispatch(name: str, args: dict) -> str:
    """执行工具，返回文本结果。"""
    try:
        if name == "wiki_search":
            hits = search(args.get("query", ""), args.get("limit", 10))
            return json.dumps(hits, ensure_ascii=False, indent=2)
        if name == "wiki_read":
            return json.dumps(read_note(args["rel_path"]), ensure_ascii=False, indent=2)
        if name == "wiki_write":
            meta = {}
            if args.get("title"):
                meta["title"] = args["title"]
            if args.get("tags"):
                meta["tags"] = args["tags"]
            return write_note(args["rel_path"], args["body"], meta)
        if name == "wiki_append":
            return write_note(args["rel_path"], args["body"], append=True)
        if name == "wiki_list":
            notes = list_notes(args.get("category"))
            return json.dumps(
                [{"rel": n["rel"], "title": n["title"], "tags": n["tags"]} for n in notes[:args.get("limit", 50)]],
                ensure_ascii=False, indent=2,
            )
        if name == "wiki_daily":
            return create_daily_note(args.get("date"))
        if name == "wiki_tags":
            return json.dumps(search_by_tag(args["tag"]), ensure_ascii=False, indent=2)
        if name == "wiki_agents":
            return json.dumps(discover(), ensure_ascii=False, indent=2)
        if name == "wiki_semantic_search":
            hits = semantic_search(
                args.get("query", ""),
                args.get("limit", 10),
                args.get("mode"),
            )
            return json.dumps(hits, ensure_ascii=False, indent=2)
        if name == "wiki_index":
            return update_index()
        if name == "wiki_daily_briefing":
            return _daily_briefing(args.get("date"))
        return f"[ERROR] 未知工具: {name}"
    except Exception as e:
        return f"[ERROR] {name} 执行失败: {e}"


def _daily_briefing(date: str | None = None) -> str:
    """聚合今日简报：日记 + 心情 + 待办提醒 + 最近 RSS，Markdown 输出。"""
    from datetime import datetime as _dt
    from pathlib import Path as _P
    import re as _re

    d = date or _dt.now().strftime("%Y-%m-%d")
    root = _P(__file__).parent
    # wiki 根：环境变量 > 仓库根（与 rag.find_wiki_root 一致的宽松策略）
    wiki_root = root.parent
    lines = [f"# MyWiki 今日简报 — {d}", ""]

    # 1) 当日日记
    diary = None
    for base in (wiki_root, wiki_root / "daily"):
        cand = base / "daily" / f"{d}.md" if (base / "daily").is_dir() else base / f"{d}.md"
        if cand.exists():
            diary = cand
            break
    lines.append("## 📝 日记")
    if diary:
        body = diary.read_text(encoding="utf-8", errors="ignore").strip()
        lines.append(body[:1500] + ("\n…（已截断）" if len(body) > 1500 else ""))
    else:
        lines.append("（今日尚无日记）")
    lines.append("")

    # 2) 心情记录
    lines.append("## 💡 心情")
    mood_file = wiki_root / "mood" / f"{d}.json"
    if mood_file.exists():
        try:
            records = json.loads(mood_file.read_text(encoding="utf-8"))
            for r in records[:10]:
                lines.append(f"- [{r.get('time', '?')}] {r.get('mood', '?')} "
                             f"({float(r.get('confidence', 0)):.0%}) {r.get('text', '')[:50]}")
        except Exception as e:
            lines.append(f"（读取失败: {e}）")
    else:
        lines.append("（今日无心情记录）")
    lines.append("")

    # 3) 待办提醒
    lines.append("## ⏰ 待办提醒")
    rem_file = wiki_root / "reminders" / "reminders.json"
    now = _dt.now()
    pending = []
    if rem_file.exists():
        try:
            for r in json.loads(rem_file.read_text(encoding="utf-8")):
                if r.get("status") != "pending":
                    continue
                ra = r.get("remind_at", "")
                due = _dt.strptime(ra, "%Y-%m-%d %H:%M:%S") if ra else None
                if due and due < now:
                    pending.append(f"- [已过期] #{r['id']} {ra} {r.get('message', '')}")
                else:
                    pending.append(f"- #{r['id']} {ra} {r.get('message', '')}")
        except Exception as e:
            lines.append(f"（读取失败: {e}）")
    lines.extend(pending[:15] or ["（无待办）"])
    lines.append("")

    # 4) 最近 RSS 摘要（daily/rss/ 下最新 3 篇标题）
    lines.append("## 📡 最近 RSS")
    rss_dir = wiki_root / "daily" / "rss"
    recent = []
    if rss_dir.is_dir():
        files = sorted(rss_dir.glob("*.md"), reverse=True)[:3]
        for f in files:
            try:
                head = f.read_text(encoding="utf-8", errors="ignore")
                title = _re.search(r"^#\s+(.+)$", head, _re.M)
                recent.append(f"- {f.name}: {title.group(1).strip() if title else f.stem}")
            except Exception:
                pass
    lines.extend(recent or ["（无 RSS 内容）"])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 传输层: 优先使用 mcp 库，否则最小 JSON-RPC over stdio
# ---------------------------------------------------------------------------

def serve_with_mcp_sdk():
    """使用官方 mcp 库提供完整 MCP 服务。"""
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    import mcp.types as types

    app = Server("mywiki-shared")

    @app.list_tools()
    async def list_tools():
        return [Tool(**t) for t in TOOLS]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict):
        result = _dispatch(name, arguments or {})
        return [TextContent(type="text", text=result)]

    async def _run():
        async with stdio_server() as (r, w):
            await app.run(r, w, app.create_initialization_options())

    asyncio.run(_run())


def serve_minimal_jsonrpc():
    """
    最小 JSON-RPC 2.0 over stdio 实现（无需第三方依赖）。
    兼容任何会发 JSON-RPC 的 MCP 客户端（忽略 notifications）。
    """
    import io

    # 确保用二进制 stdin 读取行
    stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    out = sys.stdout

    def send(obj):
        out.write(json.dumps(obj, ensure_ascii=False) + "\n")
        out.flush()

    # 强制无缓冲输出，确保宿主及时收到响应
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    while True:
        raw = stdin.readline()
        if not raw:
            break  # EOF：管道关闭或宿主退出
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except Exception:
            continue

        method = msg.get("method")
        mid = msg.get("id")

        if method == "initialize":
            send({
                "jsonrpc": "2.0", "id": mid,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "mywiki-shared", "version": "1.0.0"},
                },
            })
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            result_text = _dispatch(name, arguments)
            send({
                "jsonrpc": "2.0", "id": mid,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                    "isError": result_text.startswith("[ERROR]"),
                },
            })
        elif method in ("ping", "resources/list", "prompts/list"):
            if mid is not None:
                send({"jsonrpc": "2.0", "id": mid, "result": {}})
        # 忽略其他 notification

    # stdin 已到 EOF（如管道输入结束），正常退出
    sys.exit(0)


def main():
    try:
        serve_with_mcp_sdk()
    except ImportError:
        print("[INFO] 未安装 mcp 库，使用最小 JSON-RPC stdio 模式", file=sys.stderr)
        serve_minimal_jsonrpc()


if __name__ == "__main__":
    main()
