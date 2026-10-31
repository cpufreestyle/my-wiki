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


def spec_analysis_kwargs():
    """符号执行 MyWiki.spec，取 Analysis(...) 的关键字参数。

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
    return captured["Analysis"]


def spec_datas_names():
    """Analysis(datas=...) 里的文件名集合。"""
    return {Path(str(src)).name for src, _ in (spec_analysis_kwargs().get("datas") or [])}


def first_party_module_files():
    """仓库里可被 import 的一方模块：根目录单文件 + modules/<模块>/*.py。"""
    files = {p.stem: p for p in ROOT.glob("*.py")}
    files.update({p.stem: p for p in ROOT.glob("modules/*/*.py")})
    return files


def source_files():
    """全仓 Python 源码（排除虚拟环境与用户内容目录）。"""
    skip = {".venv", "node_modules", ".git", "vendor", "__pycache__", ".qoder",
            "daily", "brain", "wiki"}
    return [p for p in ROOT.rglob("*.py")
            if not skip.intersection(p.relative_to(ROOT).parts)]


def imported_names():
    """全仓 import 语句（含字面量动态 import）里出现过的顶层名。"""
    out = set()
    for path in source_files():
        src = read(path)
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                out |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                out.add(node.module.split(".")[0])
        out |= {m.split(".")[0]
                for m in re.findall(r'(?:import_module|__import__)\(\s*["\']([\w.]+)', src)}
    return out


def path_injected_imports():
    """先改写 sys.path 再 import 的一方模块 -> 发起 import 的文件名。

    PyInstaller 在构建机上看不到这些目录（只有运行时才插进 sys.path），
    所以静态分析必然漏掉，只能靠 hiddenimports 或 datas 补上。
    """
    importable_at_build = set(first_party_module_files()) - root_modules()
    found = {}
    for path in sorted(ROOT.glob("*.py")):
        src = read(path)
        if "sys.path.insert" not in src and "sys.path.append" not in src:
            continue
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            for name in names:
                if name in importable_at_build:
                    found.setdefault(name, path.name)
    return found


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


class HiddenImportsTest(unittest.TestCase):
    """hiddenimports 是 PyInstaller 唯一看不见的动态依赖：既不能漏，也不能留死名。"""

    @classmethod
    def setUpClass(cls):
        kwargs = spec_analysis_kwargs()
        cls.hidden = set(kwargs.get("hiddenimports") or [])
        cls.datas = {Path(str(src)).name for src, _ in (kwargs.get("datas") or [])}
        cls.injected = path_injected_imports()
        cls.imported = imported_names()

    def test_manifests_are_discovered(self):
        """守卫自身不能空跑：解析不到清单时，下面几条会永远绿。"""
        self.assertGreaterEqual(len(self.hidden), 10, "spec 的 hiddenimports 解析为空")
        self.assertGreaterEqual(len(self.datas), 10, "spec 的 datas 解析为空")

    def test_path_injected_imports_are_discovered(self):
        """wiki_tabs_share 会先插 sys.path 再 import，这里确认静态扫描还能看见它们。"""
        self.assertGreaterEqual(len(self.injected), 3,
                                "只发现 {} 个路径注入后 import 的模块".format(
                                    sorted(self.injected)))

    def test_injected_imports_are_hidden_or_packaged(self):
        """只在运行时插进 sys.path 的模块，构建期静态分析必然漏掉。

        打包版靠 hiddenimports 编进 PYZ，或者靠 datas 落到包内目录再动态加载；
        两者都没有时，标签页在装好的应用里会 ModuleNotFoundError。
        """
        missing = sorted(
            "{}（由 {} import）".format(name, importer)
            for name, importer in self.injected.items()
            if name not in self.hidden and name + ".py" not in self.datas)
        self.assertEqual(missing, [],
                         "以下模块只被路径注入后 import，既不在 hiddenimports 也不在 "
                         "datas，打包版会 import 失败：" + str(missing))

    def test_hiddenimports_have_no_stale_names(self):
        """模块改名/删除后，hiddenimports 里的旧名只会让 PyInstaller 打一行警告。"""
        stale = sorted(n for n in self.hidden if n.split(".")[0] not in self.imported)
        self.assertEqual(stale, [],
                         "hiddenimports 里的名字已无人 import（模块改名或删除后的残骸）："
                         + str(stale))


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
