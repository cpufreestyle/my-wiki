#!/usr/bin/env python3
"""test_module_manifest_completeness.py — 安装/打包手工清单的漂移守卫

`pyproject.toml` 的 `py-modules` 和 `MyWiki.spec` 的 `datas` 都是手工清单，历史上反复
漏登记：模块在仓库根目录跑得好好的，`pip install` 或打成 .app 之后 import 不到
（wiki_tabs_* / wiki_links / llm_qa / vision_face_mood 都漏过）。这类故障要到用户打开
装好的应用才暴露，本地测试完全无感。

本文件不另建一份清单（那正是会漏的东西），而是从 pyproject 声明的入口点顺着 import 图
算出「应当有哪些一方模块」，再核对两份手工清单：

1. 入口闭包里的模块必须都在 py-modules；
2. py-modules 里不能留着盘上已不存在的模块名；
3. web_server.py 的本地 import 闭包必须都进 spec 的 datas（它按数据文件打包，
   PyInstaller 不会跟踪其中的 import）；
4. requires-python 下限不能低于代码实际用到的语法（PEP 604 注解需 3.10）。
"""
import ast
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
PEP604_ANNOTATION = re.compile(
    r"->\s*[\w\.\[\]]+\s*\|[\w\.\s|None]*|:\s*[\w\.\[\]]+\s*\|\s*(?:None|[\w\.\[\]])")


class _Dummy:
    """占位对象：吃掉 PyInstaller 的构造调用与后续属性访问。"""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):  # noqa: D105
        return _Dummy()


def read(path):
    return path.read_text(encoding="utf-8")


def declared_py_modules():
    """pyproject 的 [tool.setuptools] py-modules 列表。"""
    block = re.search(r"py-modules\s*=\s*\[(.*?)\]", read(PYPROJECT), re.S)
    return set(re.findall(r'"([^"]+)"', block.group(1))) if block else set()


def declared_requires_python():
    """pyproject 的 requires-python，返回 (major, minor)。"""
    m = re.search(r'requires-python\s*=\s*">=\s*(\d+)\.(\d+)"', read(PYPROJECT))
    return (int(m.group(1)), int(m.group(2))) if m else None


def entry_point_modules():
    """[project.scripts] / [project.gui-scripts] 里 "module:func" 的模块名。"""
    return set(re.findall(r'=\s*"([\w.]+):[\w.]+"', read(PYPROJECT)))


def root_modules():
    """仓库根目录下可被 import 的单文件模块名（py-modules 只管这一层）。"""
    return {p.stem for p in ROOT.glob("*.py")}


def local_imports(module):
    """该根模块 import 到的其他根模块（静态 import + 字面量 import_module）。"""
    path = ROOT / (module + ".py")
    if not path.exists():
        return set()
    src = read(path)
    out = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            out |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module.split(".")[0])
    out |= {m.split(".")[0]
            for m in re.findall(r'import_module\(\s*"([\w.]+)"', src)}
    return {name for name in out if name in root_modules()}


def import_closure(starts):
    """从入口出发、沿一方 import 图可达的根模块集合。"""
    seen, stack = set(), list(starts)
    while stack:
        for name in local_imports(stack.pop()):
            if name not in seen:
                seen.add(name)
                stack.append(name)
    return seen | {s for s in starts if s in root_modules()}


def spec_datas_names():
    """符号执行 MyWiki.spec，取 Analysis(datas=...) 里的文件名集合。

    spec 用相对路径与 glob，所以执行时把 CWD 临时切到仓库根；Analysis 等构造全部
    换成占位对象，不会真的开始打包分析。
    """
    captured = {}

    def factory(name):
        def call(*args, **kwargs):
            captured[name] = kwargs
            return _Dummy()
        return call

    namespace = {"__file__": str(ROOT / "MyWiki.spec"), "__name__": "spec_under_test",
                 "Analysis": factory("Analysis"), "PYZ": factory("PYZ"),
                 "EXE": factory("EXE"), "COLLECT": factory("COLLECT"),
                 "BUNDLE": factory("BUNDLE")}
    prior = Path.cwd()
    try:
        os.chdir(ROOT)
        exec(compile(read(ROOT / "MyWiki.spec"), "MyWiki.spec", "exec"), namespace)
    finally:
        os.chdir(prior)
    return {Path(str(src)).name for src, _ in (captured["Analysis"].get("datas") or [])}


class ModuleManifestTest(unittest.TestCase):
    """py-modules 必须覆盖入口闭包，且不留死名。"""

    @classmethod
    def setUpClass(cls):
        cls.entries = entry_point_modules()
        cls.closure = import_closure(cls.entries)
        cls.declared = declared_py_modules()

    def test_entry_points_are_discovered(self):
        """守卫自身不能空跑：入口一个都没解析到时，下面两条会永远绿。"""
        self.assertTrue({"wiki_app", "web_server", "wiki_tool"} <= self.entries,
                        "pyproject 脚本入口结构与解析假设不符: {}".format(
                            sorted(self.entries)))
        self.assertGreaterEqual(len(self.closure), 20,
                                "入口 import 闭包只算出 {} 个模块".format(
                                    len(self.closure)))

    def test_py_modules_covers_entry_import_closure(self):
        """漏一个就等于「装完就 ModuleNotFoundError」，而盘上跑得一切正常。"""
        self.assertEqual(sorted(self.closure - self.declared), [],
                         "以下一方模块被入口 import，却不在 pyproject 的 py-modules 里："
                         + str(sorted(self.closure - self.declared)))

    def test_py_modules_has_no_stale_entries(self):
        """模块改名或删掉后，清单里的旧名字应一并清理。"""
        self.assertEqual(sorted(self.declared - root_modules()), [],
                         "py-modules 登记了盘上不存在的模块："
                         + str(sorted(self.declared - root_modules())))


class WebServerPackagingTest(unittest.TestCase):
    """web_server.py 按数据文件打包，它的本地 import 必须逐条进 datas。"""

    @classmethod
    def setUpClass(cls):
        cls.packaged = spec_datas_names()
        cls.closure = import_closure(["web_server"])

    def test_datas_covers_web_server_import_closure(self):
        missing = sorted(m for m in self.closure
                         if m != "web_server" and m + ".py" not in self.packaged)
        self.assertEqual(missing, [],
                         "MyWiki.spec 的 datas 缺这些 web_server 依赖（打包版接口会不可用）："
                         + str(missing))


class RequiresPythonTest(unittest.TestCase):
    """requires-python 不能低于代码实际用到的语法版本。"""

    def test_floor_matches_pep604_usage(self):
        """PEP 604 注解（str | None）在 3.9 上 import 即 TypeError。"""
        users = []
        for path in sorted(ROOT.glob("*.py")):
            src = read(path)
            if "from __future__ import annotations" in src:
                continue
            if PEP604_ANNOTATION.search(src):
                users.append(path.name)
        floor = declared_requires_python()
        self.assertIsNotNone(floor, "pyproject 未声明 requires-python")
        if users:
            self.assertGreaterEqual(floor, (3, 10),
                                    "{} 用了 PEP 604 注解，requires-python 不能低于 3.10"
                                    .format(users[:4]))


if __name__ == "__main__":
    unittest.main()
