#!/usr/bin/env python3
"""tests/test_dependency_manifests.py — 依赖清单双向核对

`requirements.txt` 是「核心 + 全部运行时可选依赖」的完整安装清单，
`pyproject.toml` 是 `pip install .` / pipx 路径的声明。两份清单此前已经漂移：
mediapipe / opencv-python / SpeechRecognition 只写在 requirements.txt，
走 pip 安装路径会缺这三项，面部与语音功能要到运行时才失败。

本测试把两份清单当作同一契约的两端：名称、版本约束、平台 marker 必须一致，
且 requirements.txt 不得漏掉任何运行时可选依赖组。

纯标准库实现；`tomllib` 在 Python 3.10 不存在，那里跳过并在跳过信息里说明，
CI（3.12）与发布机都会执行。
"""
import re
import unittest
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10 没有 tomllib
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
PYPROJECT = ROOT / "pyproject.toml"

# 开发工具（pytest / playwright）不进入运行时安装清单，不参与双向核对
DEV_GROUP = "dev"

_REQ_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?P<extras>\[[^\]]*\])?(?P<rest>.*)$"
)


def normalize_name(name):
    """PEP 503 名称归一：大小写与 `-_.` 视为等价"""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirement(text):
    """把一条依赖声明拆成 (归一化名称, extras, 版本约束+marker)"""
    match = _REQ_RE.match(text.strip())
    if not match:
        raise AssertionError(f"无法解析依赖声明: {text!r}")
    extras = (match.group("extras") or "").replace(" ", "")
    rest = re.sub(r"\s+", " ", match.group("rest")).strip()
    return normalize_name(match.group("name")), extras, rest


def read_requirements(path=REQUIREMENTS):
    """返回 [(行号, 原始行, 解析结果)]，忽略注释、行内注释与 pip 选项"""
    entries = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r", "-e", "--")):
            continue
        entries.append((lineno, line, parse_requirement(line)))
    return entries


def read_pyproject(path=PYPROJECT):
    """返回 [(所属组, 声明原文, 解析结果)]，含 dependencies 与非 dev 可选依赖组"""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data["project"]
    groups = {"dependencies": project.get("dependencies", [])}
    for group, values in project.get("optional-dependencies", {}).items():
        if group != DEV_GROUP:
            groups[group] = values

    entries = []
    for group, values in groups.items():
        for spec in values:
            entries.append((group, spec, parse_requirement(spec)))
    return entries


def index_by_name(entries):
    """按归一化名称分组，便于做同名条目的双向比较"""
    mapping = {}
    for entry in entries:
        mapping.setdefault(entry[-1][0], []).append(entry)
    return mapping


@unittest.skipIf(tomllib is None, "tomllib 需要 Python 3.11+；CI 使用 3.12 会执行")
class TestDependencyManifestParity(unittest.TestCase):
    """requirements.txt 与 pyproject.toml 必须描述同一组运行时依赖"""

    @classmethod
    def setUpClass(cls):
        cls.requirements = read_requirements()
        cls.pyproject = read_pyproject()
        cls.requirements_by_name = index_by_name(cls.requirements)
        cls.pyproject_by_name = index_by_name(cls.pyproject)

    def test_every_requirement_is_declared_in_pyproject(self):
        """requirements.txt 里的每条运行时依赖都必须能在 pyproject 中找到

        否则 `pip install .` / pipx 安装出来的程序缺依赖，表现为运行时
        ModuleNotFoundError（而按 requirements.txt 安装的机器一切正常）。
        """
        for lineno, line, (name, _extras, _rest) in self.requirements:
            with self.subTest(requirement=line):
                self.assertIn(
                    name,
                    self.pyproject_by_name,
                    f"requirements.txt:{lineno} `{line}` 未在 pyproject.toml "
                    "的 dependencies 或可选依赖组中声明，pip 安装路径会漏装",
                )

    def test_every_pyproject_runtime_dependency_is_in_requirements(self):
        """pyproject 的运行时依赖也必须出现在 requirements.txt

        requirements.txt 是完整安装清单；只写进 pyproject 会让按文档安装的
        用户缺功能。
        """
        for group, spec, (name, _extras, _rest) in self.pyproject:
            with self.subTest(group=group, requirement=spec):
                self.assertIn(
                    name,
                    self.requirements_by_name,
                    f"pyproject.toml [{group}] `{spec}` 未出现在 requirements.txt，"
                    "requirements.txt 不再是完整安装清单",
                )

    def test_specifiers_and_markers_match(self):
        """同名依赖的版本约束与平台 marker 必须逐字一致"""
        for name, entries in self.requirements_by_name.items():
            pyproject_entries = self.pyproject_by_name.get(name, [])
            requirement_variants = {entry[-1] for entry in entries}
            pyproject_variants = {entry[-1] for entry in pyproject_entries}
            with self.subTest(requirement=name):
                self.assertEqual(
                    requirement_variants,
                    pyproject_variants,
                    f"{name} 在两份清单里的版本约束/marker 不一致："
                    f"requirements={requirement_variants} "
                    f"pyproject={pyproject_variants}",
                )

    def test_requirements_has_no_duplicate_names(self):
        """同名依赖出现两次时，后一条会静默覆盖前一条的语义"""
        duplicates = {
            name: entries
            for name, entries in self.requirements_by_name.items()
            if len(entries) > 1
        }
        self.assertFalse(
            duplicates,
            "requirements.txt 存在重复依赖："
            + ", ".join(
                f"{name} (行 {[e[0] for e in entries]})"
                for name, entries in duplicates.items()
            ),
        )


if __name__ == "__main__":
    unittest.main()
