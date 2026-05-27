#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weekly_review.py - Weekly Knowledge Review
Identifies stale pages (30+ days old) and hot nodes (most referenced).
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

WIKI_DIR = Path(__file__).parent.parent

def extract_links(content):
    return re.findall(r'\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]', content)

def main():
    print("[Review] Generating weekly review...")
    all_links, all_refs = {}, defaultdict(list)

    for md in WIKI_DIR.rglob("*.md"):
        content = md.read_text(encoding='utf-8', errors='ignore')
        rel = str(md.relative_to(WIKI_DIR)).replace('\\', '/')
        links = extract_links(content)
        all_links[rel] = links
        for link in links:
            all_refs[link.strip()].append(rel)

    # Stale pages (30+ days)
    stale = []
    cutoff = datetime.now() - timedelta(days=30)
    for md in WIKI_DIR.rglob("*.md"):
        if "weekly_review" in md.name or "knowledge_report" in md.name: continue
        mtime = datetime.fromtimestamp(md.stat().st_mtime)
        if mtime < cutoff:
            rel = str(md.relative_to(WIKI_DIR)).replace('\\', '/')
            stale.append((rel, mtime.strftime('%Y-%m-%d')))
    stale.sort(key=lambda x: x[1])

    # Hot pages
    hot = sorted(all_refs.items(), key=lambda x: len(x[1]), reverse=True)[:10]

    # New this week
    week_ago = datetime.now() - timedelta(days=7)
    new_files = []
    for md in WIKI_DIR.rglob("*.md"):
        if datetime.fromtimestamp(md.stat().st_mtime) > week_ago:
            rel = str(md.relative_to(WIKI_DIR)).replace('\\', '/')
            if "weekly_review" not in rel:
                new_files.append((rel, datetime.fromtimestamp(md.stat().st_mtime)))

    today = datetime.now().strftime("%Y-%m-%d")
    out_file = WIKI_DIR / "weekly_review.md"
    lines = ["# Weekly Review\n\n",
             "> Generated: " + today + "\n\n---\n\n",
             "## Stale Pages (30+ days no update)\n\n"]
    if stale:
        for name, date in stale[:20]:
            lines.append("- [" + name + "](" + name + ")  _" + date + "_\n")
    else:
        lines.append("- All pages have recent updates!\n")

    lines.append("\n## Hot Nodes (most referenced)\n\n")
    for name, refs in hot:
        lines.append("- [" + name + "](" + name + ") <- " + str(len(refs)) + " refs\n")

    lines.append("\n## New/Updated This Week\n\n")
    if new_files:
        for name, mtime in sorted(new_files, key=lambda x: x[1], reverse=True):
            ts = mtime.strftime('%m-%d %H:%M')
            lines.append("- [" + name + "](" + name + ")  _" + ts + "_\n")
    else:
        lines.append("- No updates this week\n")

    out_file.write_text(''.join(lines), encoding='utf-8')
    print("  [OK] Stale:", len(stale), "  Hot:", len(hot), "  New:", len(new_files))
    print("  [OK] weekly_review.md saved")

if __name__ == "__main__":
    main()
