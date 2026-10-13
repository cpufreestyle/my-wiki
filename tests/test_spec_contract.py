#!/usr/bin/env python3
"""tests/test_spec_contract.py — SPEC.md 与 web_server.py 的契约核对

AGENTS.md 让 Agent 改「入口 / HTTP 路由 / 静态白名单 / 打包资源 / 版本号」前先看
SPEC.md，并称其为「可核对的硬契约」。但此前没有任何测试读过 SPEC.md：文档与代码各写
一份路由表，漂移了没人知道——而按文档行事的人会写出 404 的调用、或以为某个目录可下载。

这里核对四件事（文档 ↔ 代码，双向）：
  1. SPEC 3.2 GET 路由 == web_server.do_GET 实际派发的路径
  2. SPEC 3.3 POST 路由 == web_server.do_POST 实际派发的路径
  3. SPEC 3.4 静态白名单（放行目录 / 扩展名）== 代码里的 STATIC_ALLOWED_*
  4. SPEC 6.2 版本单一数据源：MyWiki.spec 不得再出现硬编码版本号

只读源码文本，不 import web_server（它 import rag → 依赖 requests，CI 裸 runner 上没有）。
"""
import ast
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def read_tracked(rel_path):
    """SPEC.md 目前仍是未纳入版本控制的未跟踪文件——全新检出的 CI 里它可能不在。

    缺了它这条核对就没有对象，报错要说清「把 SPEC.md 一起提交」，而不是一句 FileNotFoundError。
    """
    path = REPO / rel_path
    if not path.is_file():
        raise AssertionError(
            "{} 不在仓库工作区里：本文件核对它与代码的一致性，"
            "全新检出的 CI 需要它被提交进版本控制".format(rel_path))
    return path.read_text(encoding="utf-8")


SPEC = read_tracked("SPEC.md")
SERVER_SRC = read_tracked("web_server.py")


def spec_table_routes(heading):
    """解析 SPEC.md 某小节表格里第一列的路径，返回集合。"""
    start = SPEC.index(heading)
    end = SPEC.find("###", start + len(heading))
    section = SPEC[start:end if end != -1 else len(SPEC)]
    routes = set()
    for line in section.splitlines():
        row = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(row) < 2 or not row[0].startswith("/") or set(row[0]) <= set("-: "):
            continue
        for cell in re.split(r"[、,]", row[0]):
            cell = cell.strip().strip("`")
            if cell.startswith("/"):
                routes.add(cell)
    return routes


def _path_comparison(node):
    """该节点是不是「拿请求路径来比对」——只在这种情况下字面量才算一条路由。"""
    if not isinstance(node, (ast.Compare, ast.Call)):
        return False
    if isinstance(node, ast.Call):
        func = node.func
        if not (isinstance(func, ast.Attribute)
                and func.attr in ("startswith", "endswith")):
            return False
        owner = func.value
        return (isinstance(owner, ast.Attribute) and owner.attr == "path") or (
            isinstance(owner, ast.Name) and owner.id in ("path", "clean_path"))
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == "path":
            return True
        if isinstance(sub, ast.Name) and sub.id in ("path", "clean_path"):
            return True
    return False


def served_routes(method):
    """从 web_server.py 的 do_GET / do_POST 函数体里取出被派发的路径常量。"""
    tree = ast.parse(SERVER_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "do_" + method:
            found = set()
            for sub in ast.walk(node):
                if not _path_comparison(sub):
                    continue
                for literal in ast.walk(sub):
                    if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                        if not literal.value.startswith("/"):
                            continue
                        value = literal.value.split("?")[0].rstrip("/") or "/"
                        found.add(value)
            return found
    raise AssertionError("web_server.py 里找不到 do_{}，路由核对表需要更新".format(method))


def code_literal(name):
    """取 web_server.py 模块级 `NAME = <字面量>` 的值。"""
    for node in ast.parse(SERVER_SRC).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError("web_server.py 里找不到常量 {}".format(name))


class RouteContractTest(unittest.TestCase):
    def test_get_routes_match_the_spec_table(self):
        self.assertEqual(spec_table_routes("### 3.2 GET 路由"), served_routes("GET"))

    def test_post_routes_match_the_spec_table(self):
        self.assertEqual(spec_table_routes("### 3.3 POST 路由"), served_routes("POST"))

    def test_docstring_advertises_only_routes_that_exist(self):
        """模块 docstring 也是对外契约：写着有、实际 404，等于教人写出坏调用。"""
        doc = ast.get_docstring(ast.parse(SERVER_SRC)) or ""
        documented = {m.group(0).split("?")[0].rstrip("/") or "/"
                      for m in re.finditer(r"/(?:api/)?[\w/]+", doc)}
        missing = documented - served_routes("GET") - served_routes("POST")
        self.assertFalse(
            missing,
            "web_server.py 顶部 docstring 声明了不存在的路由：{}（客户端只会拿到 404）".format(
                sorted(missing)))


class StaticWhitelistContractTest(unittest.TestCase):
    def test_allowed_dirs_match_the_spec(self):
        spec_dirs = re.search(r"放行目录：STATIC_ALLOWED_DIRS = \(([^)]*)\)", SPEC)
        self.assertIsNotNone(spec_dirs, "SPEC 3.4 不再声明 STATIC_ALLOWED_DIRS？同步更新本测试")
        documented = set(re.findall(r'"([^"]+)"', spec_dirs.group(1)))
        self.assertEqual(documented, set(code_literal("STATIC_ALLOWED_DIRS")))

    def test_allowed_extensions_match_the_spec(self):
        spec_exts = re.search(r"放行扩展名：([^\n]+)", SPEC)
        self.assertIsNotNone(spec_exts, "SPEC 3.4 不再声明放行扩展名？同步更新本测试")
        documented = {e if e.startswith(".") else "." + e
                      for e in spec_exts.group(1).split()}
        self.assertEqual(documented, {e.lower() for e in code_literal("STATIC_ALLOWED_EXTS")})


class VersionSourceTest(unittest.TestCase):
    def test_spec_file_does_not_hardcode_a_version(self):
        """SPEC 6.2：版本号只有 pyproject.toml 一处，MyWiki.spec 必须读它。"""
        spec_src = (REPO / "MyWiki.spec").read_text(encoding="utf-8")
        hardcoded = re.findall(r'^\s*VERSION\s*=\s*["\'][\d.]+["\']', spec_src, re.M)
        self.assertEqual(
            hardcoded, [],
            "MyWiki.spec 又硬编码了版本号 {}：应引用 pyproject 的 _pyproject_version()".format(
                hardcoded))
        self.assertIn("pyproject", spec_src)


if __name__ == "__main__":
    unittest.main()
