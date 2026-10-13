#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rss_feeds.py — RSS 订阅源加载器

`config/rss_feeds.json` 是订阅源的唯一数据源（见
`.qoder/rules/rss-feed-management.md`）。`fetch_rss.py` /
`fetch_rss_enhanced.py` / `auto_fetch.py` 统一调用 load_feeds() 取源，
不再各自维护一份源清单。
"""
import json
from pathlib import Path

WIKI_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = WIKI_DIR / "config" / "rss_feeds.json"


def load_feeds(config_path=CONFIG_PATH):
    """读取订阅源配置，返回启用中的源列表。

    返回 [{"name", "url", "tag"}, ...]；"enabled": false 的条目被排除，
    省略 enabled 视为启用。配置缺失时抛出指名文件路径的 FileNotFoundError。
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"RSS 订阅源配置不存在: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return [
        {"name": feed["name"], "url": feed["url"], "tag": feed["tag"]}
        for feed in data.get("feeds", [])
        if feed.get("enabled", True)
    ]


if __name__ == "__main__":
    for _feed in load_feeds():
        print(f"{_feed['tag']:8} {_feed['name']:18} {_feed['url']}")
