#!/usr/bin/env python3
"""tests/test_vault_walker_consistency.py — vault 遍历规则的一致性核对

vault 里「跳过哪些目录」「有哪些知识分类」这条规则目前写在 4 个文件里，各写一遍：

| 文件 | 常量 | 用途 |
|------|------|------|
| `rag.py` | `SKIP_DIRS` / `CATEGORIES` | 语义索引 |
| `modules/shared-wiki/wiki_core.py` | `SKIP_DIRS` / `CATEGORIES` | 内核读写 / 清单 |
| `wiki_data.py` | `VAULT_SKIP_DIRS` | 搜索 / 标签浏览 |
| `wiki_links.py` | `SKIP_DIRS` | 链接图 |

四份抄本已经漂了（`wiki_links.py` 多跳 `.venv`/`inbox` 等）。把常量收敛成单一来源代价高——
`wiki_core.py` 刻意在没有仓库根时也能独立运行——所以这里守住**一致性**本身：
公共部分四家必须都有，任何*新增*的不对称要么四家一起改，要么显式登记进
`DOCUMENTED_EXTRA_SKIP`，让「只改一个索引」变成 CI 报红而不是用户眼里的一个诡异 bug
（比如「搜索能搜到、知识图谱里没有」）。

只用 AST 读字面量、不 import 被测模块：`rag.py` 会 import requests，
CI 的裸测试步骤里没有它（见 tests/test_ci_dependency_contract.py）。
常量将来若收敛到一处，本文件会因取不到字面量而报红——那是提醒同步改这里，不是放过。
"""
import ast
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 四家都必须跳过的目录：Obsidian 配置、版本库、缓存、二进制附件与回收站
COMMON_SKIP_DIRS = {".obsidian", ".git", "__pycache__", "node_modules",
                    "attachments", ".trash"}

# 有意保留的差异（不是漏改）。inbox/ 是临时捕获区，不进链接图；构建产物只对链接图成立。
DOCUMENTED_EXTRA_SKIP = {
    "wiki_links.py": {".venv", "venv", "dist", "build", "backups", "logs", "inbox"},
}

WALKERS = {
    "rag.py": {"SKIP_DIRS", "CATEGORIES"},
    "modules/shared-wiki/wiki_core.py": {"SKIP_DIRS", "CATEGORIES"},
    "wiki_data.py": {"VAULT_SKIP_DIRS"},
    "wiki_links.py": {"SKIP_DIRS"},
}


def literals(rel_path, names):
    """取出某文件里 `NAME = <字面量>` 的值，返回 {name: 值}；取不到即返回 None 项。"""
    tree = ast.parse((REPO / rel_path).read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in names:
                found[target.id] = ast.literal_eval(node.value)
    return found


class WalkerConsistencyTest(unittest.TestCase):
    def test_constants_are_still_literals_where_we_expect_them(self):
        """表里每一份常量都得取得到，否则下面的核对会在空集上假通过。"""
        for rel_path, names in WALKERS.items():
            found = literals(rel_path, names)
            missing = names - set(found)
            self.assertFalse(
                missing,
                "{} 里取不到 {} —— 常量搬走了就同步更新本文件的表".format(
                    rel_path, sorted(missing)))
            for name, value in found.items():
                self.assertTrue(value, "{}.{} 是空的，核对无意义".format(rel_path, name))

    def test_every_walker_skips_the_common_dirs(self):
        for rel_path, names in WALKERS.items():
            for key, value in literals(rel_path, names).items():
                if not key.endswith("SKIP_DIRS"):
                    continue
                missing = COMMON_SKIP_DIRS - set(value)
                self.assertFalse(
                    missing,
                    "{} 的 {} 漏跳了 {}：这份笔记会被索引进搜索结果".format(
                        rel_path, key, sorted(missing)))

    def test_no_undocumented_divergence_between_walkers(self):
        """某一跳目录只出现在一家、其他三家没有——要么四家一起改，要么登记进白名单。"""
        skip_sets = {}
        for rel_path, names in WALKERS.items():
            for key, value in literals(rel_path, names).items():
                if key.endswith("SKIP_DIRS"):
                    skip_sets[rel_path] = set(value)
        for rel_path, own in skip_sets.items():
            others = set().union(*(s for p, s in skip_sets.items() if p != rel_path))
            extra = own - others - DOCUMENTED_EXTRA_SKIP.get(rel_path, set())
            self.assertFalse(
                extra,
                "{} 的 {} 只被一家跳过：其余索引会把这些目录里的笔记算进来".format(
                    rel_path, sorted(extra)))

    def test_indexers_agree_on_categories(self):
        """RAG 与内核的分类目录不一致时，同一篇笔记在一个入口搜得到、另一个入口不存在。"""
        rag = literals("rag.py", {"CATEGORIES"})["CATEGORIES"]
        core = literals("modules/shared-wiki/wiki_core.py",
                        {"CATEGORIES"})["CATEGORIES"]
        self.assertEqual(list(rag), list(core),
                         "rag.py 与 wiki_core.py 的 CATEGORIES 顺序或内容不一致")


if __name__ == "__main__":
    unittest.main()
