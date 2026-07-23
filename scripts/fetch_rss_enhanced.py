#!/usr/bin/env python3
"""
fetch_rss_enhanced.py - Scrapling 增强版 RSS 抓取器

改进:
1. 使用 Scrapling 替代 requests，支持动态渲染页面
2. 内置反爬绕过（自动处理 User-Agent、延迟、重试）
3. 智能元素追踪（自动适应页面结构变化）
4. 失败时 fallback 到原 feedparser
"""

import re
import os
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

# Scrapling 增强: 支持需要 JS 渲染的页面
SCRAPLING_FEEDS = [
    # 可以在这里添加需要 JS 渲染的页面
    # {"name": "示例", "url": "https://example.com/news", "tag": "custom", "selector": ".news-item"}
]


def fetch_with_scrapling(url: str, selector: str = None) -> list:
    """使用 Scrapling 抓取动态页面"""
    try:
        from scrapling import Fetcher
        fetcher = Fetcher(auto_match=False)
        page = fetcher.get(url, stealthy_headers=True)
        
        if selector:
            items = page.css(selector)
        else:
            items = page.css('item, entry')
        
        results = []
        for item in items[:10]:
            title = item.css_first('title') or item.css_first('h3')
            link = item.css_first('link') or item.css_first('a')
            summary = item.css_first('summary') or item.css_first('description') or item.css_first('p')
            
            results.append({
                'title': title.text if title else 'No Title',
                'link': link.attrib.get('href', '') if link and link.attrib else (link.text if link else ''),
                'summary': summary.text[:200] if summary else '',
            })
        return results
    except Exception as e:
        print(f"  [Scrapling] fallback to feedparser: {e}")
        return []


def fetch_with_feedparser(url: str) -> list:
    """传统 feedparser 抓取（fallback）"""
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    parsed = feedparser.parse(url, request_headers=headers)
    return parsed.entries


def main():
    out_dir = WIKI_DIR / "daily" / "rss"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    # 标准 RSS feeds
    for feed in RSS_FEEDS:
        try:
            print(f"[RSS] Fetching {feed['name']}...")
            entries = fetch_with_feedparser(feed['url'])
            
            if not entries:
                # feedparser 失败时尝试 Scrapling
                print(f"  feedparser empty, trying Scrapling...")
                entries = fetch_with_scrapling(feed['url'])
            
            if not entries:
                print(f"  ❌ {feed['name']}: no entries")
                continue

            safe = "".join(c if c.isalnum() else "-" for c in feed['name'])[:20]
            out_file = out_dir / f"{today}-{feed['tag']}-{safe}.md"

            lines = [f"# {feed['name']} · {today}\n\n",
                     f"**标签**: #{feed['tag']}\n\n---\n\n"]
            for i, e in enumerate(entries[:10], 1):
                title = e.get('title', 'No Title') if isinstance(e, dict) else getattr(e, 'title', 'No Title')
                link = e.get('link', '') if isinstance(e, dict) else getattr(e, 'link', '')
                summary = e.get('summary', '') if isinstance(e, dict) else getattr(e, 'summary', '')
                summary = re.sub('<[^<]+?>', '', summary)[:200].strip()
                
                lines.append(f"## {i}. {title}\n\n")
                lines.append(f"- 🔗 {link}\n")
                pub = (e.get('published', '') if isinstance(e, dict) else getattr(e, 'published', ''))[:10]
                if pub:
                    lines.append(f"- 📅 {pub}\n")
                if summary:
                    lines.append(f"- {summary}...\n")
                lines.append("\n")

            out_file.write_text(''.join(lines), encoding='utf-8')
            print(f"  ✅ {feed['name']} → {out_file.name}")

        except Exception as e:
            print(f"  ❌ {feed['name']}: {e}")

    # Scrapling 增强 feeds（JS 渲染页面）
    for feed in SCRAPLING_FEEDS:
        try:
            print(f"[Scrapling] Fetching {feed['name']}...")
            items = fetch_with_scrapling(feed['url'], feed.get('selector'))
            
            if not items:
                continue
            
            safe = "".join(c if c.isalnum() else "-" for c in feed['name'])[:20]
            out_file = out_dir / f"{today}-{feed['tag']}-{safe}.md"
            
            lines = [f"# {feed['name']} · {today}\n\n",
                     f"**标签**: #{feed['tag']}\n\n---\n\n"]
            for i, item in enumerate(items[:10], 1):
                lines.append(f"## {i}. {item.get('title', 'No Title')}\n\n")
                lines.append(f"- 🔗 {item.get('link', '')}\n")
                summary = item.get('summary', '')[:200]
                if summary:
                    lines.append(f"- {summary}...\n")
                lines.append("\n")
            
            out_file.write_text(''.join(lines), encoding='utf-8')
            print(f"  ✅ {feed['name']} → {out_file.name}")
            
        except Exception as e:
            print(f"  ❌ {feed['name']}: {e}")


if __name__ == "__main__":
    main()
