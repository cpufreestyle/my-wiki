#!/usr/bin/env python3
"""
tests/test_rss_feeds.py — RSS 订阅源单一数据源单元测试

守住 `.qoder/rules/rss-feed-management.md` 声明的契约：`config/rss_feeds.json`
是唯一数据源，抓取脚本不得自带源清单。此前三份脚本各自硬编码同一份 4 源列表，
配置里新增的源永远抓不到，且没有任何测试能发现这种漂移。

纯标准库实现（unittest + json + re），不导入 feedparser/requests——CI 的
Python 测试步骤在 `pip install` 之前运行，依赖第三方包会让本文件在 CI 报错。
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import rss_feeds  # noqa: E402

CONFIG_PATH = rss_feeds.CONFIG_PATH
FETCHERS = ["fetch_rss.py", "fetch_rss_enhanced.py", "auto_fetch.py"]


class TestLoadFeeds(unittest.TestCase):
    """load_feeds() 的行为"""

    def test_reads_the_configured_feeds(self):
        """配置里的每个启用源都应出现在返回值中"""
        configured = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["feeds"]
        enabled = [f for f in configured if f.get("enabled", True)]
        loaded = rss_feeds.load_feeds()
        self.assertEqual([f["url"] for f in loaded], [f["url"] for f in enabled])
        self.assertEqual([f["name"] for f in loaded], [f["name"] for f in enabled])

    def test_returns_name_url_tag_for_every_feed(self):
        """下游脚本按 name/url/tag 三个键取用，缺一个就会在抓取时抛 KeyError"""
        for feed in rss_feeds.load_feeds():
            self.assertEqual(
                sorted(k for k in ("name", "url", "tag") if k in feed),
                ["name", "tag", "url"],
                f"订阅源字段不完整: {feed}",
            )

    def test_skips_disabled_feeds(self):
        """enabled=false 的源应被排除，而不是删除条目"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feeds.json"
            path.write_text(json.dumps({"feeds": [
                {"name": "On", "url": "https://a/feed", "tag": "tech", "enabled": True},
                {"name": "Off", "url": "https://b/feed", "tag": "tech", "enabled": False},
            ]}), encoding="utf-8")
            names = [f["name"] for f in rss_feeds.load_feeds(path)]
            self.assertEqual(names, ["On"])

    def test_feed_without_enabled_key_defaults_to_enabled(self):
        """省略 enabled 字段视为启用（与 Rule 的示例配置一致）"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feeds.json"
            path.write_text(json.dumps({"feeds": [
                {"name": "Unspecified", "url": "https://a/feed", "tag": "tech"},
            ]}), encoding="utf-8")
            self.assertEqual(len(rss_feeds.load_feeds(path)), 1)

    def test_missing_config_raises_with_its_path(self):
        """配置缺失属于部署错误，报错信息必须指名缺哪个文件"""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.json"
            with self.assertRaises(FileNotFoundError) as ctx:
                rss_feeds.load_feeds(missing)
            self.assertIn("nope.json", str(ctx.exception))


class TestFetchersHaveOwnFeedListRemoved(unittest.TestCase):
    """三份抓取脚本必须从配置取源，不得再自带源清单"""

    def test_each_fetcher_loads_from_config(self):
        for name in FETCHERS:
            src = (SCRIPTS_DIR / name).read_text(encoding="utf-8")
            self.assertIn("load_feeds", src, f"{name} 未从 config/rss_feeds.json 读取订阅源")

    def test_no_fetcher_hardcodes_a_feed_url(self):
        """守卫的是漂移本身：脚本里再出现订阅源 URL 就是第二份数据源

        整行注释不计入——fetch_rss_enhanced.py 保留了一行被注释掉的
        SCRAPLING_FEEDS 用法示例，那是文档而非数据源。
        """
        for name in FETCHERS:
            src = (SCRIPTS_DIR / name).read_text(encoding="utf-8")
            code = "\n".join(
                line for line in src.splitlines() if not line.lstrip().startswith("#")
            )
            hardcoded = re.findall(r'"url"\s*:\s*"(https?://[^"]+)"', code)
            self.assertFalse(
                hardcoded,
                f"{name} 仍存在硬编码的订阅源 URL {hardcoded}，"
                "config/rss_feeds.json 不再是唯一数据源",
            )


class TestConfigHasSingleReader(unittest.TestCase):
    """只有 load_feeds 的实现可以指名 config/rss_feeds.json"""

    ALLOWED = {"scripts/rss_feeds.py", "tests/test_rss_feeds.py"}
    SKIP = {".venv", "node_modules", ".git", "vendor", "__pycache__", ".qoder",
            "daily", "brain", "wiki"}

    def test_no_other_file_names_the_config_directly(self):
        """绕开 load_feeds 自己 open+解析，等于开出第二份数据源

        enabled/tag 的过滤逻辑会在两处各写一遍，之后配置改了只生效一半，
        而这种不一致没有任何报错——正是这次要修的原始故障。
        """
        root = Path(__file__).resolve().parent.parent
        offenders = []
        for path in root.rglob("*.py"):
            rel = path.relative_to(root).as_posix()
            if rel in self.ALLOWED or self.SKIP.intersection(rel.split("/")):
                continue
            if CONFIG_PATH.name in path.read_text(encoding="utf-8"):
                offenders.append(rel)
        self.assertEqual(
            offenders, [],
            "以下文件绕开 scripts/rss_feeds.py 直接指名订阅源配置，"
            "改为调用 load_feeds(): " + str(offenders))


if __name__ == "__main__":
    unittest.main(verbosity=2)
