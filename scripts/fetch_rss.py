#!/usr/bin/env python3
"""
fetch_rss.py - RSS 订阅专用抓取器
直接运行：python fetch_rss.py
"""

import re
import feedparser
import requests
from datetime import datetime
from pathlib import Path

WIKI_DIR = Path(__file__).parent.parent
RSS_FEEDS = [
    {"name": "Hacker News",    "url": "https://hnrss.org/frontpage",                   "tag": "tech"},
    {"name": "GitHub Blog",    "url": "https://github.blog/feed/",                    "tag": "github"},
    {"name": "Real Python",    "url": "https://realpython.com/atom.xml",               "tag": "python"},
    {"name": "MIT Tech Review","url": "https://www.technologyreview.com/feed/",        "tag": "tech"},
]

def main():
    out_dir = WIKI_DIR / "daily" / "rss"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    for feed in RSS_FEEDS:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            parsed = feedparser.parse(feed['url'], request_headers=headers)
            if not parsed.entries:
                continue

            safe = "".join(c if c.isalnum() else "-" for c in feed['name'])[:20]
            out_file = out_dir / f"{today}-{feed['tag']}-{safe}.md"

            lines = [f"# {feed['name']} · {today}\n\n",
                     f"**标签**: #{feed['tag']}\n\n---\n\n"]
            for i, e in enumerate(parsed.entries[:10], 1):
                lines.append(f"## {i}. {e.get('title','No Title')}\n\n")
                lines.append(f"- 🔗 {e.get('link','')}\n")
                pub = e.get('published','')[:10]
                if pub: lines.append(f"- 📅 {pub}\n")
                smry = re.sub('<[^<]+?>', '', e.get('summary',''))[:200].strip()
                if smry: lines.append(f"- {smry}...\n")
                lines.append("\n")

            out_file.write_text(''.join(lines), encoding='utf-8')
            print(f"✅ {feed['name']} → {out_file.name}")

        except Exception as e:
            print(f"❌ {feed['name']}: {e}")

if __name__ == "__main__":
    main()
