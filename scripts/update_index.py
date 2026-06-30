#!/usr/bin/env python3
"""
update_index.py - 知识地图自动更新器
直接运行：python update_index.py
"""

from datetime import datetime
from pathlib import Path

WIKI_DIR = Path(__file__).parent.parent

def count_files(*parts):
    p = WIKI_DIR.joinpath(*parts)
    return len(list(p.rglob("*.md"))) if p.exists() else 0

def recent_files(glob_pat, limit=5):
    files = sorted(WIKI_DIR.rglob(glob_pat), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[:limit]

def main():
    stats = {
        "daily":    count_files("daily"),
        "active":   count_files("projects"),
        "tech":     count_files("concepts"),
        "people":   count_files("people"),
    }
    total = sum(stats.values())

    recent_daily = recent_files("daily/*.md", 5)
    recent_proj  = recent_files("projects/*.md", 5)

    md_lines = [
        f"# 📍 MyWiki 知识地图\n\n",
        f"> 自动生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n",
        f"## 📊 统计\n\n",
        "| 分类 | 数量 |\n|------|------|\n",
    ]
    for k, v in stats.items():
        labels = {"daily":"日记","active":"项目","tech":"概念","people":"人脉"}
        md_lines.append(f"| {labels[k]} | {v} |\n")
    md_lines.append(f"| **合计** | **{total}** |\n\n")

    md_lines.append("## 📝 近期日记\n\n")
    if recent_daily:
        for f in recent_daily:
            md_lines.append(f"- [{f.stem}](daily/{f.stem}.md)\n")
    else:
        md_lines.append("- （空）\n")

    md_lines.append("\n## 🚀 项目\n\n")
    if recent_proj:
        for f in recent_proj:
            md_lines.append(f"- [{f.stem}](projects/{f.stem}.md)\n")
    else:
        md_lines.append("- （空）\n")

    md_lines.append("""\n---\n\n_由 update_index.py 自动维护_\n""")

    (WIKI_DIR / "index.md").write_text(''.join(md_lines), encoding='utf-8')
    print(f"✅ index.md 已更新（总计 {total} 个笔记文件）")

if __name__ == "__main__":
    main()
