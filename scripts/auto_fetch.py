#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-fetch - 自动拉取外部数据到 MyWiki
GitHub Commits -> projects/*-updates.md
RSS -> daily/rss/YYYY-MM-DD-*.md
"""

from __future__ import annotations
import os, sys, re, json, requests
from datetime import datetime
from pathlib import Path

WIKI_DIR = Path(__file__).parent.parent
GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")

GITHUB_REPOS = [
    "cpufreestyle/psvr2-panel",
    "cpufreestyle/sanguosha-mobile",
    "cpufreestyle/stock-crewai",
    "cpufreestyle/my-wiki",
]

RSS_FEEDS = [
    {"name": "Hacker News",    "url": "https://hnrss.org/frontpage",                  "tag": "tech"},
    {"name": "GitHub Blog",    "url": "https://github.blog/feed/",                    "tag": "github"},
    {"name": "Real Python",    "url": "https://realpython.com/atom.xml",              "tag": "python"},
    {"name": "MIT Tech Review","url": "https://www.technologyreview.com/feed/",        "tag": "tech"},
]

def compress(text):
    if not text: return text
    lines = text.split('\n')
    seen, unique = set(), []
    for line in lines:
        key = line[:50].lower().replace(' ', '') if len(line) >= 50 else line.lower().replace(' ', '')
        if key not in seen or len(line) < 80:
            seen.add(key); unique.append(line)
    result = '\n'.join(unique)
    if len(result) > 2000:
        result = result[:2000] + "\n\n[Content truncated]"
    return result

def fetch_github():
    print("[GitHub] Fetching repos...")
    headers = {"Authorization": "token " + GITHUB_TOKEN, "Accept": "application/vnd.github.v3+json"}
    for repo in GITHUB_REPOS:
        try:
            resp = requests.get(
                "https://api.github.com/repos/" + repo + "/commits?per_page=5",
                headers=headers, timeout=10
            )
            resp.raise_for_status()
            commits = resp.json()
            if not commits: continue
            name = repo.split("/")[-1]
            out_dir = WIKI_DIR / "projects"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / (name + "-updates.md")

            parts = ["# " + repo + " Changelog\n\n",
                     "**Updated**: " + datetime.now().strftime("%Y-%m-%d %H:%M") + "\n",
                     "**Repo**: https://github.com/" + repo + "\n\n---\n\n"]
            for c in commits:
                sha = c["sha"][:7]
                msg = c["commit"]["message"].split("\n")[0]
                author = c["commit"]["author"]["name"]
                date = c["commit"]["author"]["date"][:10]
                url = c["html_url"]
                parts.append("## " + date + " . " + sha + "\n")
                parts.append("- **" + author + "**: " + msg + "\n")
                parts.append("- " + url + "\n\n")

            content = compress(''.join(parts))
            out_file.write_text(content, encoding='utf-8')
            print("  [OK] " + repo + " -> " + out_file.name)
        except Exception as e:
            print("  [ERR] " + repo + ": " + str(e))

def fetch_rss():
    print("[RSS] Fetching feeds...")
    out_dir = WIKI_DIR / "daily" / "rss"
    out_dir.mkdir(parents=True, exist_ok=True)

    import feedparser
    for feed in RSS_FEEDS:
        try:
            parsed = feedparser.parse(
                feed["url"],
                request_headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            if not parsed.entries: continue

            today = datetime.now().strftime("%Y-%m-%d")
            safe = "".join(c if c.isalnum() else "-" for c in feed["name"])[:20]
            out_file = out_dir / (today + "-" + feed["tag"] + "-" + safe + ".md")

            parts = ["# " + feed["name"] + " - " + today + "\n\n",
                     "**Tag**: #" + feed["tag"] + "  **Source**: " + feed["url"] + "\n\n---\n\n"]
            for i, e in enumerate(parsed.entries[:10], 1):
                title = e.get("title", "No Title")
                link  = e.get("link", "")
                pub   = e.get("published", "")[:10]
                smry  = re.sub("<[^<]+?>", "", e.get("summary", ""))[:150].strip()
                parts.append(str(i) + ". **" + title + "**\n\n")
                parts.append("- " + link + "\n")
                if pub: parts.append("- " + pub + "\n")
                if smry: parts.append("- " + smry + "...\n")
                parts.append("\n")

            content = compress(''.join(parts))
            out_file.write_text(content, encoding='utf-8')
            print("  [OK] " + feed["name"] + " -> " + out_file.name)
        except Exception as e:
            print("  [ERR] " + feed["name"] + ": " + str(e))

def update_index():
    print("[Index] Updating knowledge map...")
    def count(*parts): p = WIKI_DIR.joinpath(*parts); return len(list(p.rglob("*.md"))) if p.exists() else 0

    total = sum(count(k) for k in ["daily", "projects", "concepts", "people"])

    content = "# MyWiki Knowledge Map\n\n"
    content += "> Auto-generated . " + datetime.now().strftime("%Y-%m-%d %H:%M") + "\n\n---\n\n"
    content += "## Statistics\n\n"
    content += "| Category | Count |\n|----------|-------|\n"
    content += "| daily | " + str(count("daily")) + " |\n"
    content += "| projects | " + str(count("projects")) + " |\n"
    content += "| concepts | " + str(count("concepts")) + " |\n"
    content += "| people | " + str(count("people")) + " |\n"
    content += "| **Total** | **" + str(total) + "** |\n\n"
    content += "---\n\n"
    content += "_Auto-generated by MyWiki auto_fetch script_\n"

    (WIKI_DIR / "index.md").write_text(content, encoding='utf-8')
    print("  [OK] index.md updated")

def main():
    print("=" * 50)
    print(" MyWiki Auto-fetch . " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 50)
    fetch_github()
    print()
    fetch_rss()
    print()
    update_index()
    print("=" * 50)
    print("Done.")

if __name__ == "__main__":
    main()
