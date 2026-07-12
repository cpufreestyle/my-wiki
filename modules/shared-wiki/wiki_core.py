#!/usr/bin/env python3
"""
wiki_core.py — MyWiki 共享知识内核 (Shared Wiki Core)

这是 MyWiki 与 Obsidian、电脑里所有 Agent 共享 Wiki 的**统一访问层**。
所有读写、搜索、知识查询操作都通过这里完成，避免每个 Agent 重复造轮子。

设计原则:
  - 单一事实源 (Single Source of Truth): wiki 文件夹就是全部知识，Obsidian 直接读它
  - Agent 无关: 不假定任何特定 Agent，任何进程都能 import 它
  - 文件即 API: 每篇笔记是一个 .md 文件，frontmatter 是元数据

定位 wiki root 的优先级:
  1. 环境变量 MYWIKI_ROOT
  2. 本仓库根目录（scripts 等在 my-wiki/ 下时）
  3. ~/.qclaw/workspace/wiki
"""
import os
import re
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

try:
    import yaml
except ImportError:
    yaml = None


def find_wiki_root() -> Path:
    """智能定位 wiki 根目录。"""
    env = os.environ.get("MYWIKI_ROOT")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p

    # 当前文件: modules/shared-wiki/wiki_core.py -> 仓库根 = parent.parent.parent
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent.parent,                    # 仓库根
        here.parent.parent.parent.parent / "wiki",    # 部署形态
        Path.home() / ".qclaw" / "workspace" / "wiki",
    ]
    for c in candidates:
        if (c / "INDEX.md").exists() or (c / "daily").exists() or (c / "README.md").exists():
            return c
    # 兜底返回仓库根
    return here.parent.parent.parent


WIKI_ROOT = find_wiki_root()

# 知识分类目录
CATEGORIES = ["daily", "projects", "concepts", "people", "brain"]

# 跳过这些目录（Obsidian 配置、缓存等）
SKIP_DIRS = {".obsidian", ".git", "__pycache__", "node_modules", "attachments", ".trash"}


# ---------------------------------------------------------------------------
# Frontmatter 处理
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str):
    """解析 YAML frontmatter，返回 (meta:dict, body:str)。"""
    meta = {}
    body = text
    if text.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
        if m:
            fm = m.group(1)
            body = m.group(2)
            if yaml:
                try:
                    meta = yaml.safe_load(fm) or {}
                except Exception:
                    meta = {}
            else:
                # 极简 fallback 解析: 支持列表 [a, b] 与带引号字符串
                for line in fm.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        v = v.strip()
                        if v.startswith("[") and v.endswith("]"):
                            items = [i.strip().strip("'\"") for i in v[1:-1].split(",") if i.strip()]
                            meta[k.strip()] = items
                        elif v == "":
                            meta[k.strip()] = None
                        else:
                            meta[k.strip()] = v.strip("'\"")
    return meta, body


def build_frontmatter(meta: dict) -> str:
    """根据 dict 生成 YAML frontmatter 文本。"""
    if not meta:
        return ""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(str(x) for x in v)}]")
        elif v is None:
            lines.append(f"{k}:")
        else:
            s = str(v)
            # 避免 YAML 把纯日期/数字字符串误解析为非字符串类型
            if re.match(r"^\d{4}-\d{2}-\d{2}([ T].*)?$", s) or re.match(r"^-?\d+(\.\d+)?$", s):
                s = f"'{s}'"
            lines.append(f"{k}: {s}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


# ---------------------------------------------------------------------------
# 读取 / 写入
# ---------------------------------------------------------------------------

def list_notes(category: str = None, include_body: bool = False):
    """
    列出 wiki 中的笔记。
    category: 指定分类 (daily/projects/...) 或 None 表示全部
    返回 [ {path, rel, title, tags, type, date, mtime, body?} ]
    """
    results = []
    roots = [WIKI_ROOT / c for c in (CATEGORIES if not category else [category])]
    if category and category not in CATEGORIES:
        roots = [WIKI_ROOT / category]  # 允许任意子目录

    for root in roots:
        if not root.exists():
            continue
        for f in root.rglob("*.md"):
            if any(part in SKIP_DIRS for part in f.parts):
                continue
            if f.name in ("INDEX.md", "README.md"):
                continue
            meta, body = parse_frontmatter(f.read_text(encoding="utf-8", errors="ignore"))
            rel = f.relative_to(WIKI_ROOT).as_posix()
            item = {
                "path": str(f),
                "rel": rel,
                "title": meta.get("title") or f.stem,
                "tags": meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
                "type": meta.get("type", category or "note"),
                "date": meta.get("date"),
                "mtime": f.stat().st_mtime,
            }
            if include_body:
                item["body"] = body
            results.append(item)
    results.sort(key=lambda x: x["mtime"], reverse=True)
    return results


def read_note(rel_path: str) -> dict:
    """按相对路径读取一篇笔记，返回 {meta, body, rel}。"""
    f = (WIKI_ROOT / rel_path).resolve()
    if not f.exists():
        raise FileNotFoundError(f"Note not found: {rel_path}")
    text = f.read_text(encoding="utf-8", errors="ignore")
    meta, body = parse_frontmatter(text)
    return {"rel": f.relative_to(WIKI_ROOT).as_posix(), "meta": meta, "body": body}


def write_note(rel_path: str, body: str, meta: dict = None, append: bool = False) -> str:
    """
    写入/创建一篇笔记。自动补充 frontmatter。
    rel_path: 相对路径，例如 daily/2026-07-12.md
    返回最终写入的绝对路径字符串。
    """
    f = (WIKI_ROOT / rel_path).resolve()
    f.parent.mkdir(parents=True, exist_ok=True)

    if meta is None:
        meta = {}

    # 自动补 default frontmatter
    if "title" not in meta:
        meta["title"] = f.stem
    if "date" not in meta and re.match(r"\d{4}-\d{2}-\d{2}", f.stem):
        meta["date"] = f.stem
    if "type" not in meta:
        first = rel_path.split("/")[0]
        meta["type"] = first if first in CATEGORIES else "note"
    if "tags" not in meta:
        meta["tags"] = [meta["type"]] if meta["type"] != "note" else []

    if append and f.exists():
        existing = f.read_text(encoding="utf-8", errors="ignore")
        _, old_body = parse_frontmatter(existing)
        new_body = old_body.rstrip() + "\n\n" + body.strip() + "\n"
    else:
        new_body = body.strip() + "\n"

    content = build_frontmatter(meta) + new_body
    f.write_text(content, encoding="utf-8")
    return str(f)


def create_daily_note(date: str = None) -> str:
    """创建（如不存在）今日/指定日期的日记，返回相对路径。"""
    date = date or datetime.now().strftime("%Y-%m-%d")
    rel = f"daily/{date}.md"
    target = WIKI_ROOT / rel
    if target.exists():
        return rel
    body = (
        f"# {date} 每日笔记\n\n"
        "## 今日概要\n\n\n## 工作记录\n\n\n"
        "## 学习与思考\n\n\n## 明日计划\n\n\n"
        f"## 最后更新\n\n{date} {datetime.now().strftime('%H:%M')}\n"
    )
    write_note(rel, body)
    return rel


# ---------------------------------------------------------------------------
# 搜索 / 查询
# ---------------------------------------------------------------------------

def search(query: str, limit: int = 20):
    """
    全文搜索 wiki。返回匹配笔记列表（含命中片段）。
    """
    q = query.lower()
    hits = []
    notes = list_notes(include_body=True)
    for n in notes:
        text = n.get("body", "")
        if q in text.lower():
            # 提取命中上下文
            idx = text.lower().find(q)
            start = max(0, idx - 60)
            end = min(len(text), idx + len(query) + 60)
            snippet = text[start:end].replace("\n", " ").strip()
            hits.append({
                "rel": n["rel"],
                "title": n["title"],
                "tags": n["tags"],
                "snippet": ("..." + snippet + "...") if start > 0 else snippet,
            })
        if len(hits) >= limit:
            break
    return hits


def search_by_tag(tag: str):
    """按标签搜索笔记。"""
    out = []
    for n in list_notes():
        if tag in n["tags"]:
            out.append({"rel": n["rel"], "title": n["title"], "tags": n["tags"]})
    return out


def query_links(topic: str, limit: int = 10):
    """根据主题返回最相关的若干笔记（简单相关性：标题/标签/正文命中计数）。"""
    topic_l = topic.lower()
    scored = []
    for n in list_notes(include_body=True):
        score = 0
        title = str(n["title"]).lower()
        if topic_l in title:
            score += 5
        score += sum(3 for t in n["tags"] if topic_l in t.lower())
        score += n.get("body", "").lower().count(topic_l)
        if score > 0:
            scored.append((score, n))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"rel": n["rel"], "title": n["title"], "tags": n["tags"], "score": s}
        for s, n in scored[:limit]
    ]


# ---------------------------------------------------------------------------
# 索引
# ---------------------------------------------------------------------------

def update_index() -> str:
    """重建 INDEX.md 统一索引入口。"""
    index_path = WIKI_ROOT / "INDEX.md"
    lines = ["# Wiki Index\n", ""]

    for cat in CATEGORIES:
        root = WIKI_ROOT / cat
        if not root.exists():
            continue
        notes = sorted(root.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not notes:
            continue
        label = {
            "daily": "每日笔记 (Daily)",
            "projects": "项目 (Projects)",
            "concepts": "概念 (Concepts)",
            "people": "人物 (People)",
            "brain": "脑图 (Brain)",
        }.get(cat, cat)
        lines.append(f"## {label}\n")
        for p in notes:
            display = p.stem.replace("_", " ")
            lines.append(f"- [[{cat}/{p.name}|{display}]]\n")
        lines.append("")

    lines.append("## 统计\n")
    lines.append(f"- 最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(f"- 笔记总数：{len(list_notes())}\n")

    index_path.write_text("".join(lines), encoding="utf-8")
    return str(index_path)


# ---------------------------------------------------------------------------
# 导出 (供 Obsidian / 其他 Agent 消费)
# ---------------------------------------------------------------------------

def export_manifest() -> dict:
    """导出 wiki 清单 JSON，供 Agent 快速了解整体结构。"""
    notes = list_notes()
    return {
        "wiki_root": str(WIKI_ROOT),
        "updated": datetime.now().isoformat(timespec="seconds"),
        "note_count": len(notes),
        "categories": {c: len(list((WIKI_ROOT / c).glob("*.md"))) for c in CATEGORIES if (WIKI_ROOT / c).exists()},
        "notes": [{"rel": n["rel"], "title": n["title"], "tags": n["tags"], "type": n["type"]} for n in notes[:100]],
    }


if __name__ == "__main__":
    print(f"Wiki root: {WIKI_ROOT}")
    print(f"Notes: {len(list_notes())}")
    print(json.dumps(export_manifest(), ensure_ascii=False, indent=2)[:800])
