#!/usr/bin/env python3
"""tests/test_github_repos.py — GitHub 仓库清单的单一数据源

`scripts/auto_fetch.py` 此前把要抓 commit 的 4 个仓库写死在脚本里（`GITHUB_REPOS`），
与 RSS 源是同一个病：配置里看不出有哪些仓库，加一个仓库要改代码，改完没人知道
其他地方是否还有第二份清单。这里把清单钉在 `config/github_repos.json`，
并守住「脚本不得自带列表」。

只读源码不 import auto_fetch.py：它模块级 `import requests`，CI 的裸测试步骤里没有。
"""
import ast
import json
import re
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import github_repos  # noqa: E402

REPO_ROOT = SCRIPTS_DIR.parent
CONFIG_PATH = github_repos.CONFIG_PATH
AUTO_FETCH = SCRIPTS_DIR / "auto_fetch.py"
REPO_NAME = re.compile(r"^[\w.-]+/[\w.-]+$")


def repo_lists(path):
    """返回文件里「元素全是 owner/repo 字符串」的列表/元组/集合字面量。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            continue
        values = [e.value for e in node.elts
                  if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if values and len(values) == len(node.elts) and all(
                REPO_NAME.match(v) for v in values):
            found.append((node.lineno, values))
    return found


class LoadReposTest(unittest.TestCase):
    def test_returns_enabled_repo_names_in_order(self):
        cfg = CONFIG_PATH.read_text(encoding="utf-8")
        repos = github_repos.load_repos()
        self.assertTrue(repos, "配置里至少要有一个启用的仓库")
        for name in repos:
            self.assertRegex(name, REPO_NAME)
            self.assertIn(name, cfg)

    def test_disabled_entries_are_filtered_out(self):
        """与 RSS 源同语义：`enabled: false` 可临时下线一个仓库而不删配置。"""
        tmp = CONFIG_PATH.parent / "_test_github_repos_tmp.json"
        tmp.write_text(json.dumps({"repos": [
            {"name": "owner/keep", "enabled": True},
            {"name": "owner/drop", "enabled": False},
            {"name": "owner/default"},  # 缺省即启用
        ]}), encoding="utf-8")
        try:
            self.assertEqual(github_repos.load_repos(tmp), ["owner/keep", "owner/default"])
        finally:
            tmp.unlink()

    def test_malformed_entry_fails_loudly(self):
        """配置写错（例如漏了 owner/）要指名报错，而不是悄悄少抓一个仓库。"""
        tmp = CONFIG_PATH.parent / "_test_github_repos_bad.json"
        tmp.write_text(json.dumps({"repos": [{"name": "no-slash"}]}), encoding="utf-8")
        try:
            with self.assertRaises(ValueError) as ctx:
                github_repos.load_repos(tmp)
            self.assertIn("no-slash", str(ctx.exception))
        finally:
            tmp.unlink()


class SingleSourceTest(unittest.TestCase):
    def test_auto_fetch_uses_the_loader_not_a_list(self):
        """脚本里不许再出现仓库名字面量：清单只来自 load_repos()。"""
        tree = ast.parse(AUTO_FETCH.read_text(encoding="utf-8"))
        literals = [n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and REPO_NAME.match(n.value)]
        self.assertEqual(literals, [], "auto_fetch.py 又硬编码了仓库：{}".format(literals))

        assigned = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "GITHUB_REPOS":
                        assigned[target.id] = ast.unparse(node.value)
        self.assertEqual(assigned.get("GITHUB_REPOS"), "load_repos()",
                         "GITHUB_REPOS 应直接取 load_repos() 的结果")

    def test_only_the_config_lists_repos(self):
        """RSS 的经验：同一份清单会在多个脚本里各抄一份。这里守住只有配置有名字。

        只认「整份列表全是 owner/repo」的字面量：单独一个字符串（UA、
        Content-Type、路径片段）不是仓库清单，报出来只会让人去关掉这条守卫。
        """
        offenders = []
        for path in sorted(SCRIPTS_DIR.glob("*.py")):
            if path.name.startswith("test_"):
                continue
            for lineno, values in repo_lists(path):
                offenders.append("{}:{} {}".format(path.name, lineno, values))
        self.assertEqual(offenders, [],
                         "这些地方自带仓库清单，应改为调用 load_repos()：\n"
                         + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
