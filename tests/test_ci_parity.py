#!/usr/bin/env python3
"""tests/test_ci_parity.py — 在「CI 的裸环境」里跑一遍全套

CI（.github/workflows/ci.yml）的单元测试步骤只装了 ci.yml 里 pip install 的那几个包，
本地 .venv 里却装着整份 requirements.txt（opencv / mediapipe / PySide6 / requests…）。
这个差别让「本地绿、CI 红」成为这个项目最难查的一类失败：用例或它 import 的一方模块
碰了某个第三方库，本地跑得过去，CI 上 ModuleNotFoundError。本会话里就中过两次
（PIL 与 cv2），都是靠手工模拟裸环境才发现的——这里把手工做法固化成用例。

做法：起一个子进程，用 sys.meta_path finder 把所有「装了但 CI 没装」的第三方顶层名
拦成 ImportError，再 runpy 跑 tests/run_all.py。这正是 CI 那一刻的环境。

- 递归防护：子进程带 MYWIKI_CI_PARITY=1，用例看到该变量就跳过（否则无限自调用）。
- 代价：一次额外的一套用例（约 2-3 秒）。
- 只用标准库，importlib.metadata 也在标准库内。
"""
import importlib.util
import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

from test_ci_dependency_contract import ci_installed_imports

ROOT = Path(__file__).resolve().parent.parent

# 子进程里跑的引导脚本：屏蔽第三方名 -> 跑统一入口 -> 用真实退出码退出
BOOTSTRAP = textwrap.dedent('''
    import ast, importlib.metadata as md, os, runpy, sys
    STD = set(sys.builtin_module_names) | set(sys.stdlib_module_names)
    ALLOW = set(ast.literal_eval(os.environ["MYWIKI_CI_ALLOWED"]))
    names = set()
    for dist in md.distributions():
        for top in (dist.read_text("top_level.txt") or "").split():
            names.add(top)
        for f in (dist.files or []):
            p = str(f)
            if "/" in p or p.endswith(".py"):
                names.add(p.split("/")[0].split(".")[0].replace("-", "_"))
    names = {n for n in names if n not in STD and not n.startswith("_")} - ALLOW

    class BareRunnerFinder:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in names:
                raise ImportError("No module named " + name + " (bare CI runner)")

    for module in list(sys.modules):
        if module.split(".")[0] in names:
            del sys.modules[module]
    sys.meta_path.insert(0, BareRunnerFinder())
    sys.argv = ["run_all.py"]
    code = 0
    try:
        runpy.run_path(os.path.join(os.getcwd(), "tests", "run_all.py"), run_name="__main__")
    except SystemExit as e:
        # run_all.py 用 SystemExit("中文原因") 表示「用例都没跑起来」，那串文字就是诊断本身
        if isinstance(e.code, str):
            sys.stderr.write("BARE-SUITE: " + e.code + "\\n")
            code = 1
        else:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    sys.stderr.write("MARKER_RC %s BLOCKED %s\\n" % (code, len(names)))
    raise SystemExit(code)
''')


def run_bare(allowed, code=BOOTSTRAP, env_overrides=None):
    """在屏蔽掉 allowed 之外所有第三方库的环境里跑一段代码，返回 CompletedProcess。"""
    env = dict(os.environ,
               MYWIKI_CI_ALLOWED=repr(sorted(set(allowed))),
               PYTHONPATH=str(ROOT / "tests"))
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run([sys.executable, "-c", code], cwd=str(ROOT),
                          env=env, capture_output=True, text=True)


# 引导脚本里「只装拦截器」的前半段，用于拦截器自检（不跑整套用例，秒级）
FINDER_ONLY = BOOTSTRAP.split("sys.argv")[0]


class BareRunnerFinderTest(unittest.TestCase):
    """拦截器本身要真的会拦——否则下面「裸环境全套通过」等于什么都没测。"""

    def test_blocks_installed_but_unallowed_module(self):
        candidate = None
        for name in ("requests", "PIL", "numpy"):
            try:
                if importlib.util.find_spec(name):
                    candidate = name
                    break
            except (ImportError, ValueError):
                continue
        if candidate is None:
            self.skipTest("本机没有可用来自检的第三方库")
        result = run_bare([], FINDER_ONLY +
                          "try:\n    import {}\n    print('IMPORTED')\n"
                          "except ImportError as e:\n    print('BLOCKED', e)\n".format(candidate))
        self.assertIn("BLOCKED", result.stdout,
                      "{} 明明装了却没被拦住，裸环境模拟是假的：{}".format(
                          candidate, result.stderr))

    def test_allowed_module_is_not_blocked(self):
        result = run_bare(["PIL"], FINDER_ONLY + "import PIL\nprint('ALLOWED')\n")
        self.assertIn("ALLOWED", result.stdout, result.stderr)


class CiParityTest(unittest.TestCase):
    def test_suite_passes_with_only_what_ci_installs(self):
        if os.environ.get("MYWIKI_CI_PARITY") == "1":
            self.skipTest("已在裸环境子进程里，别无限递归")
        result = run_bare(ci_installed_imports(),
                          env_overrides={"MYWIKI_CI_PARITY": "1"})
        combined = result.stdout + result.stderr
        self.assertTrue([l for l in combined.splitlines() if l.startswith("MARKER_RC")],
                        "裸环境子进程没跑到用例就被干掉了：\n" + combined[-4000:])
        failures = [line for line in combined.splitlines()
                    if line.startswith(("FAIL:", "ERROR:", "FAILED", "只读内容目录",
                                        "BARE-SUITE"))]
        self.assertEqual(
            result.returncode, 0,
            "CI 的裸环境（只装 {}）下全套跑不过，推上去必红。本地能过是因为 .venv 里"
            "装了 CI 没有的库：\n{}\n{}".format(
                sorted(ci_installed_imports()), "\n".join(failures[:20]),
                combined[-4000:]))


if __name__ == "__main__":
    unittest.main()
