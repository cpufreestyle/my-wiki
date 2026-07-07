#!/usr/bin/env python3
"""
Wiki 维护工具 - 帮助 LLM 更新 wiki 页面
集成模块: video-analysis, memo-sync, obsidian-sync

Usage:
  python wiki_tool.py update                    # 更新 INDEX.md
  python wiki_tool.py daily                     # 创建今日笔记
  python wiki_tool.py search <query>            # 搜索 wiki
  python wiki_tool.py video <path> [--interval 30] [--title T]  # 视频分析
  python wiki_tool.py memo-push <file> [--title T]  # 推送到 Memo
  python wiki_tool.py memo-list                 # 列出 Memo 文档
  python wiki_tool.py memo-search <keyword>     # 搜索 Memo
  python wiki_tool.py memo-pull                 # 从 Memo 拉取
  python wiki_tool.py sync-obsidian [--vault V] # 同步到 Obsidian
"""
import os
import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

WIKI_ROOT = Path(__file__).parent
MODULES = WIKI_ROOT / "modules"


def update_index():
    """更新 INDEX.md"""
    index_path = WIKI_ROOT / "INDEX.md"

    people = list(WIKI_ROOT.glob("people/*.md"))
    projects = list(WIKI_ROOT.glob("projects/*.md"))
    concepts = list(WIKI_ROOT.glob("concepts/*.md"))
    daily = sorted(WIKI_ROOT.glob("daily/*.md"), reverse=True)[:7]

    # 扫描模块
    modules_dir = WIKI_ROOT / "modules"
    module_list = []
    if modules_dir.exists():
        for m in sorted(modules_dir.iterdir()):
            if m.is_dir() and (m / "README.md").exists():
                module_list.append(m.name)

    lines = [
        "# Wiki Index\n",
        "",
        "## 人物 (People)\n",
    ]
    for p in people:
        display = p.stem.replace("_", " ")
        lines.append(f"- [[people/{p.name}|{display}]]\n")

    lines.append("\n## 项目 (Projects)\n")
    for p in projects:
        display = p.stem.replace("_", " ")
        lines.append(f"- [[projects/{p.name}|{display}]]\n")

    lines.append("\n## 概念 (Concepts)\n")
    for p in concepts:
        display = p.stem.replace("_", " ")
        lines.append(f"- [[concepts/{p.name}|{display}]]\n")

    lines.append("\n## 每日笔记 (Daily)\n")
    for p in daily:
        lines.append(f"- [[daily/{p.name}|{p.stem}]]\n")

    if module_list:
        lines.append("\n## 功能模块 (Modules)\n")
        for m in module_list:
            lines.append(f"- [[modules/{m}/README|{m}]]\n")

    lines.append("\n## 统计\n")
    lines.append(f"- 创建时间：2026-05-22\n")
    lines.append(f"- 最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    index_path.write_text("".join(lines), encoding="utf-8")
    print(f"[OK] 更新 INDEX.md ({len(people)} people, {len(projects)} projects, {len(concepts)} concepts, {len(module_list)} modules)")


def create_daily_note():
    """创建今日笔记"""
    today = datetime.now().strftime("%Y-%m-%d")
    path = WIKI_ROOT / f"daily/{today}.md"

    if path.exists():
        print(f"[WARN] 今日笔记已存在: {path}")
        return

    content = f"""# {today} 每日笔记

## 今日概要


## 工作记录


## 学习与思考


## 明日计划


## 相关链接


## 最后更新

{today} {datetime.now().strftime('%H:%M')}
"""
    path.write_text(content, encoding="utf-8")
    print(f"[OK] 创建今日笔记: {path}")


def search_wiki(query: str):
    """搜索 wiki"""
    results = []
    for md_file in WIKI_ROOT.rglob("*.md"):
        if "README" in md_file.name or ".obsidian" in str(md_file):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except:
            continue
        if query.lower() in text.lower():
            results.append(md_file)

    if results:
        print(f"[SEARCH] 找到 {len(results)} 个匹配:\n")
        for r in results:
            rel = r.relative_to(WIKI_ROOT)
            print(f"  - [[{rel}|{r.stem.replace('_', ' ')}]]")
    else:
        print(f"[NOT FOUND] 未找到匹配: {query}")


# === 模块集成 ===

def video_analysis(args):
    """视频分析模块"""
    script = MODULES / "video-analysis" / "analyze.py"
    cmd = [sys.executable, str(script)] + args
    subprocess.run(cmd)


def memo_sync(command, args):
    """Memo 同步模块"""
    script = MODULES / "memo-sync" / "sync.py"
    cmd = [sys.executable, str(script), command] + args
    subprocess.run(cmd)


def obsidian_sync(args):
    """Obsidian 同步模块"""
    script = MODULES / "obsidian-sync" / "sync.py"
    cmd = [sys.executable, str(script)] + args
    subprocess.run(cmd)


def main():
    args = sys.argv[1:]

    if not args or args[0] == "help":
        print("""
Wiki 维护工具 (v2.0 - 集成模块)

基础命令:
  update                    更新 INDEX.md
  daily                     创建今日笔记
  search <query>            搜索 wiki

模块命令:
  video <path> [opts]       视频分析 (--interval N --title T)
  memo-push <file> [opts]   推送到 Memo (--title T)
  memo-push-dir <dir> [opts] 批量推送到 Memo (--pattern "*.md")
  memo-list [--limit N]     列出 Memo 文档
  memo-search <keyword>     搜索 Memo
  memo-pull [--limit N]     从 Memo 拉取
  sync-obsidian [opts]      同步到 Obsidian (--vault documents|wiki|all)
""")
    elif args[0] == "update":
        update_index()
    elif args[0] == "daily":
        create_daily_note()
    elif args[0] == "search":
        if len(args) < 2:
            print("[ERROR] 请提供搜索关键词")
        else:
            search_wiki(" ".join(args[1:]))
    elif args[0] == "video":
        video_analysis(args[1:])
    elif args[0].startswith("memo-"):
        command = args[0].replace("memo-", "")
        memo_sync(command, args[1:])
    elif args[0] == "sync-obsidian":
        obsidian_sync(args[1:])
    else:
        print(f"[ERROR] 未知命令: {args[0]}")


if __name__ == "__main__":
    main()
