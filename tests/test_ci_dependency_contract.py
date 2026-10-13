#!/usr/bin/env python3
"""tests/test_ci_dependency_contract.py — CI 测试步骤的依赖契约

CI 的单元测试步骤在任何 requirements.txt 安装之前跑 `python tests/run_all.py`，
所以全套用例只能是纯标准库 + 仓库内一方模块；唯一被 CI 额外安装的第三方库写在
ci.yml 的 pip install 步骤里。这个契约把两边对齐：

- 用例里 import 了 CI 没装的第三方库 -> 本地就能测出「CI 必红」，不用等推送后失败；
- 想加新的第三方测试依赖 -> 必须同时改 ci.yml，否则此处报出库名和文件名。

本文件自身只用标准库（不能用 pyyaml 解析 ci.yml，因为 CI 并不安装它）。
"""
import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI_FILE = ROOT / ".github" / "workflows" / "ci.yml"

# pip 包名 -> 顶层 import 名不一致的少数几个（其余按下划线小写直译）
IMPORT_ALIASES = {"pillow": "PIL"}


def test_files():
    """与被测代码同目录的模块测试，和 tests/ 下的测试文件（同 run_all.py 的两个发现根）。"""
    return sorted((ROOT / "tests").glob("test_*.py")) + sorted(
        (ROOT / "modules").glob("*/test_*.py"))


def first_party_names():
    """仓库内可被 import 的一方模块名（排除 .venv / node_modules 等外部目录）。"""
    skip = {".venv", "node_modules", ".git", "vendor", "__pycache__", ".qoder"}
    names = set()
    for path in ROOT.rglob("*.py"):
        if skip.intersection(path.relative_to(ROOT).parts):
            continue
        names.add(path.stem)
    return names


def third_party_imports(path, first_party):
    """返回该测试文件里非标准库、非一方模块的顶层 import 名。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    std = set(sys.stdlib_module_names)
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            raw = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            raw = [node.module] if node.module else []
        else:
            continue
        for name in raw:
            top = name.split(".")[0]
            if top in std or top in first_party or top.startswith("_"):
                continue
            out.add(top)
    return out


def ci_installed_imports():
    """解析 ci.yml，返回在单元测试步骤 *之前* 被 pip install 的包对应的 import 名。"""
    lines = CI_FILE.read_text(encoding="utf-8").splitlines()
    installed, tested = set(), False
    for line in lines:
        if "tests/run_all.py" in line:
            tested = True
        match = re.search(r"pip install\s+(.+)$", line)
        if not match or tested:
            continue
        for token in match.group(1).split():
            if token.startswith("-"):
                continue
            pkg = re.split(r"[<>=!;\[]", token)[0].strip("\"'").lower()
            if not pkg:
                continue
            installed.add(IMPORT_ALIASES.get(pkg, pkg.replace("-", "_")))
    return installed


class CiDependencyContractTest(unittest.TestCase):
    """用例的第三方 import 必须被 CI 测试步骤安装。"""

    @classmethod
    def setUpClass(cls):
        cls.files = test_files()
        cls.first_party = first_party_names()
        cls.installed = ci_installed_imports()

    def test_ci_installs_pillow_before_the_suite(self):
        """契约的前提：CI 在 run_all 之前装了 pillow（抠图尺寸用例要用）。"""
        self.assertIn("PIL", self.installed,
                      "ci.yml 的单元测试步骤前应 pip install Pillow")

    def test_discovered_test_files_are_not_empty(self):
        """守卫自身不能空跑：发现不到用例文件时，后两条断言会永远绿。"""
        self.assertGreaterEqual(len(self.files), 20,
                                "只发现 {} 个测试文件，发现根改了要同步这里".format(
                                    len(self.files)))

    def test_no_uninstalled_third_party_import(self):
        """逐个测试文件核对：用了 CI 没装的库就指名报出来。"""
        problems = []
        for path in self.files:
            missing = third_party_imports(path, self.first_party) - self.installed
            if missing:
                problems.append("{}: {}".format(path.name, sorted(missing)))
        self.assertEqual(
            problems, [],
            "以下用例 import 了 CI 未安装的第三方库，CI 会红；"
            "请在 ci.yml 单元测试步骤前 pip install，或改回纯标准库：\n"
            + "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
