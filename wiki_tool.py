#!/usr/bin/env python3
"""
Wiki 维护工具 - 帮助 LLM 更新 wiki 页面
"""
import os
import json
import sys
from datetime import datetime
from pathlib import Path

# 修复 Windows 控制台 UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

WIKI_ROOT = Path(__file__).parent


def update_index():
    """更新 INDEX.md - 扫描所有页面并生成索引"""
    index_path = WIKI_ROOT / "INDEX.md"
    
    people = list(WIKI_ROOT.glob("people/*.md"))
    projects = list(WIKI_ROOT.glob("projects/*.md"))
    concepts = list(WIKI_ROOT.glob("concepts/*.md"))
    daily = sorted(WIKI_ROOT.glob("daily/*.md"), reverse=True)[:7]  # 最近7天
    
    lines = [
        "# Wiki Index\n",
        "",
        "## 人物 (People)\n",
    ]
    
    for p in people:
        name = p.stem
        display = name.replace("_", " ")
        lines.append(f"- [[people/{p.name}|{display}]]\n")
    
    lines.append("\n## 项目 (Projects)\n")
    for p in projects:
        name = p.stem
        display = name.replace("_", " ")
        lines.append(f"- [[projects/{p.name}|{display}]]\n")
    
    lines.append("\n## 概念 (Concepts)\n")
    for p in concepts:
        name = p.stem
        display = name.replace("_", " ")
        lines.append(f"- [[concepts/{p.name}|{display}]]\n")
    
    lines.append("\n## 每日笔记 (Daily)\n")
    for p in daily:
        name = p.stem
        lines.append(f"- [[daily/{p.name}|{name}]]\n")
    
    lines.append("\n## 统计\n")
    lines.append(f"- 创建时间：2026-05-22\n")
    lines.append(f"- 最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    
    index_path.write_text("".join(lines), encoding="utf-8")
    print(f"[OK] 更新 INDEX.md ({len(people)} people, {len(projects)} projects, {len(concepts)} concepts)")


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
    """搜索 wiki（简单文本匹配）"""
    results = []
    for md_file in WIKI_ROOT.rglob("*.md"):
        if "README" in md_file.name:
            continue
        text = md_file.read_text(encoding="utf-8")
        if query.lower() in text.lower():
            results.append(md_file)
    
    if results:
        print(f"[SEARCH] 找到 {len(results)} 个匹配:\n")
        for r in results:
            rel = r.relative_to(WIKI_ROOT)
            print(f"  - [[{rel}|{r.stem.replace('_', ' ')}]]")
    else:
        print(f"[NOT FOUND] 未找到匹配: {query}")


def main():
    args = sys.argv[1:]
    
    if not args or args[0] == "help":
        print("""
Wiki 维护工具

用法:
  python wiki_tool.py update          # 更新 INDEX.md
  python wiki_tool.py daily           # 创建今日笔记
  python wiki_tool.py search <query> # 搜索 wiki
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
    else:
        print(f"[ERROR] 未知命令: {args[0]}")


if __name__ == "__main__":
    main()
