#!/usr/bin/env python3
"""
Wiki 维护工具 - 帮助 LLM 更新 wiki 页面
"""
import os
import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# 修复 Windows 控制台 UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

REPO_ROOT = Path(__file__).resolve().parent  # my-wiki 仓库根


def _resolve_wiki_root():
    """wiki 数据根目录。

    优先级: 环境变量 MYWIKI_ROOT > config/obsidian.json 的 vault_path (Obsidian vault) > 仓库根。
    """
    env = os.environ.get("MYWIKI_ROOT")
    if env and Path(os.path.expanduser(env)).is_dir():
        return Path(os.path.expanduser(env))
    cfg = REPO_ROOT / "config" / "obsidian.json"
    if cfg.exists():
        try:
            vp = json.loads(cfg.read_text(encoding="utf-8")).get("vault_path", "")
            if vp and Path(os.path.expanduser(vp)).is_dir():
                return Path(os.path.expanduser(vp))
        except Exception:
            pass
    return REPO_ROOT


WIKI_ROOT = _resolve_wiki_root()


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
    """语义搜索 wiki（BM25 / 可选 Ollama embedding，失败时回退文本匹配）"""
    try:
        from rag import RAGEngine
        eng = RAGEngine()
        hits = eng.search(query, limit=10)
        if not hits:
            print(f"[NOT FOUND] 未找到语义相关: {query}")
            return
        print(f"[SEMANTIC SEARCH] 找到 {len(hits)} 个相关片段:\n")
        for h in hits:
            print(f"  - [[{h['rel']}|{h['title']}]]  (score={h['score']})")
            print(f"    {h['snippet']}")
    except Exception as e:
        # 回退到原始子串匹配
        print(f"[WARN] 语义检索不可用，使用文本匹配: {e}")
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


def _read_clipboard():
    """跨平台读取剪贴板（macOS pbpaste / Windows PowerShell / Linux xclip）。

    任何失败（无头环境、缺少工具）都返回空串，由调用方提示手动输入。
    """
    try:
        if sys.platform == "darwin":
            cmd = ["pbpaste"]
        elif sys.platform.startswith("win"):
            cmd = ["powershell", "-NoProfile", "-Command", "Get-Clipboard"]
        else:
            cmd = ["xclip", "-selection", "clipboard", "-o"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return (result.stdout or "").strip()
    except Exception:
        return ""


def quick_capture(text=None, source="cli"):
    """快速捕捉：把灵感 / 待办一键收集到 inbox/quick-capture.md。

    - text 为空时回退读取剪贴板，再不行则报错退出；
    - 相同文本已存在时跳过（防手抖重复捕捉）；
    - 只写 inbox/（临时收件箱），不动 daily/ 等用户笔记目录，
      处理完后把条目移到对应笔记即可。
    """
    if not text:
        text = _read_clipboard()
    if not text:
        print("[ERROR] 没有可捕捉的文本（参数或剪贴板均为空）")
        return False

    entry_text = " ".join(str(text).split())  # 压平换行/多余空白
    inbox_dir = WIKI_ROOT / "inbox"
    inbox_file = inbox_dir / "quick-capture.md"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    if inbox_file.exists():
        existing = inbox_file.read_text(encoding="utf-8", errors="replace")
        if entry_text in existing:
            print(f"[SKIP] 相同内容已存在: {entry_text}")
            return False
        append_text = f"- [ ] {stamp} {entry_text}\n"
        with open(inbox_file, "a", encoding="utf-8") as f:
            f.write(append_text)
    else:
        inbox_dir.mkdir(parents=True, exist_ok=True)
        header = (
            "# 快速捕捉收件箱\n\n"
            "> 由 wiki_tool.py capture 写入。处理后把条目移到对应笔记，或直接删除本行。\n\n"
        )
        inbox_file.write_text(header + f"- [ ] {stamp} {entry_text}\n", encoding="utf-8")

    print(f"[OK] 已收集（{source}）: {entry_text}")
    print(f"     位置: {inbox_file}")
    return True


def show_links(note_ref, note_name):
    """出链 / 反向链接展示（供 links / backlinks 子命令）。"""
    try:
        from wiki_links import build_backlinks, scan_links
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] 双链模块不可用: {e}")
        return

    rel = wiki_links_resolve(note_name)
    if rel is None:
        print(f"[NOT FOUND] 找不到笔记: {note_name}")
        return

    graph = scan_links(WIKI_ROOT)
    if note_ref == "links":
        targets = graph["links"].get(rel, [])
        print(f"[LINKS] {rel} 共 {len(targets)} 条出链:")
        for t in targets:
            print(f"  - [[{t}|{Path(t).stem.replace('_', ' ')}]]")
        return

    backlinks = build_backlinks(graph)
    sources = backlinks.get(rel, [])
    print(f"[BACKLINKS] {rel} 被 {len(sources)} 个笔记引用:")
    for s in sources:
        print(f"  - [[{s}|{Path(s).stem.replace('_', ' ')}]]")


def wiki_links_resolve(note_name):
    """解析笔记参数为相对路径（复用 wiki_links.resolve_note_arg）。"""
    try:
        from wiki_links import resolve_note_arg
        return resolve_note_arg(note_name, WIKI_ROOT)
    except Exception:  # noqa: BLE001
        return None


def show_top_linked(top=10):
    """不给参数时的 links：显示出链最多的笔记，便于发现枢纽页。"""
    try:
        from wiki_links import scan_links
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] 双链模块不可用: {e}")
        return

    graph = scan_links(WIKI_ROOT)
    ranked = sorted(graph["links"].items(), key=lambda kv: (-len(kv[1]), kv[0]))[:top]
    print(f"[TOP LINKS] 出链最多的 {len(ranked)} 篇笔记:")
    for rel, targets in ranked:
        if targets:
            print(f"  - {rel}  ({len(targets)} 条)")
    unresolved = sum(len(v) for v in graph["dangling"].values())
    print(f"[STATS] 共 {len(graph['notes'])} 篇笔记，{unresolved} 个失效链接目标")


def show_orphans():
    """孤儿笔记 + 失效链接清单。"""
    try:
        from wiki_links import build_backlinks, find_orphans, find_unresolved, scan_links
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] 双链模块不可用: {e}")
        return

    graph = scan_links(WIKI_ROOT)
    backlinks = build_backlinks(graph)
    # INDEX.md 是导航页，正常没有入链，不算孤儿
    orphans = find_orphans(graph, backlinks, exclude=("INDEX.md", "README.md"))
    print(f"[ORPHANS] 无入链笔记 {len(orphans)} 篇:")
    for rel in orphans:
        print(f"  - [[{rel}|{Path(rel).stem.replace('_', ' ')}]]")

    unresolved = find_unresolved(graph)
    print(f"[DANGLING] 失效链接 {len(unresolved)} 个:")
    for target, sources in unresolved:
        print(f"  - [[{target}]]  <- {', '.join(sources)}")


def main():
    args = sys.argv[1:]
    
    if not args or args[0] == "help":
        print("""
Wiki 维护工具

用法:
  python wiki_tool.py update          # 更新 INDEX.md
  python wiki_tool.py daily           # 创建今日笔记
  python wiki_tool.py search <query> # 语义搜索 wiki
  python wiki_tool.py capture <文本> # 快速捕捉到 inbox/（省去开笔记的步骤，可接剪贴板）
  python wiki_tool.py links <笔记>   # 列出该笔记的出链；不给参数则显示出链最多的笔记
  python wiki_tool.py backlinks <笔记> # 反向链接：哪些笔记链接到它
  python wiki_tool.py orphans        # 孤儿笔记（无入链）+ 失效链接清单
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
    elif args[0] == "capture":
        quick_capture(" ".join(args[1:]) or None)
    elif args[0] in ("links", "backlinks"):
        if len(args) < 2:
            if args[0] == "links":
                show_top_linked()
            else:
                print("[ERROR] 请提供笔记名，如 projects/Alpha 或 Alpha")
        else:
            show_links(args[0], " ".join(args[1:]))
    elif args[0] == "orphans":
        show_orphans()
    else:
        print(f"[ERROR] 未知命令: {args[0]}")


if __name__ == "__main__":
    main()
