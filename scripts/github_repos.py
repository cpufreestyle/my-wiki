#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
github_repos.py — GitHub 仓库清单加载器

`config/github_repos.json` 是「要抓 commit 的仓库」的唯一数据源。
`auto_fetch.py` 通过 load_repos() 取清单，不再自带仓库列表：
新增/下线一个仓库只需改配置，不必改脚本。
"""
import json
import re
from pathlib import Path

WIKI_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = WIKI_DIR / "config" / "github_repos.json"
REPO_NAME = re.compile(r"^[\w.-]+/[\w.-]+$")


def load_repos(config_path=CONFIG_PATH):
    """读取仓库配置，返回启用中的 owner/repo 列表（保持配置顺序）。

    "enabled": false 的条目被排除，省略 enabled 视为启用。仓库名不是
    owner/repo 形式时抛 ValueError 并指名该值——写错的名字只会让抓取
    静默少一个仓库，比直接报错更难发现。
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError("GitHub 仓库配置不存在: {}".format(path))
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    names = []
    for entry in data.get("repos", []):
        name = entry.get("name")
        if not isinstance(name, str) or not REPO_NAME.match(name):
            raise ValueError(
                "{}: 仓库名应形如 owner/repo，实际是 {!r}".format(path, name))
        if entry.get("enabled", True):
            names.append(name)
    return names


if __name__ == "__main__":
    for _repo in load_repos():
        print(_repo)
