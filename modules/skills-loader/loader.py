#!/usr/bin/env python3
"""
skills-loader — MyWiki 统一技能目录加载器 (Unified Skills Loader)

把一个集中的技能目录（默认 "~/AI Shared/skills"）作为**统一技能根**，
扫描其中每个技能子目录的 SKILL.md（YAML frontmatter: name / description），
提供列出、查询、调用（运行技能脚本）的能力。

设计原则:
  - 单一技能根 (Single Skills Root): 所有技能集中在一个目录，便于统一管理调用
  - 约定优于配置: 每个技能是一个子目录，内含 SKILL.md 描述 + scripts/ 脚本
  - 可覆盖: 环境变量 MYWIKI_SKILLS_ROOT 优先

技能目录约定:
    <SKILLS_ROOT>/
        <skill-name>/
            SKILL.md          # frontmatter: name, description(含触发词)
            scripts/*.py      # 可执行脚本 (可选)

定位 SKILLS_ROOT 的优先级:
  1. 环境变量 SKILLS_ROOT            (中性，供任意 agent 使用)
  2. 环境变量 MYWIKI_SKILLS_ROOT     (MyWiki 专用，兼容)
  3. ~/AI Shared/skills              (本机默认统一技能中心)
  4. ~/.qclaw/skills  (兼容旧路径)
"""
import os
import re
import sys
import subprocess
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


# ---------------------------------------------------------------------------
# 定位统一技能根目录
# ---------------------------------------------------------------------------

def find_skills_root() -> Path:
    """智能定位统一技能根目录。

    全系统的技能唯一来源：所有 agent（MyWiki 及其他）都从这里发现、调用技能。
    """
    for env_var in ("SKILLS_ROOT", "MYWIKI_SKILLS_ROOT"):
        env = os.environ.get(env_var)
        if env:
            p = Path(env).expanduser()
            if p.exists():
                return p

    candidates = [
        Path.home() / "AI Shared" / "skills",
        Path.home() / ".qclaw" / "skills",
    ]
    for c in candidates:
        if c.exists():
            return c
    # 兜底: 第一候选（即便暂不存在，调用方可据此提示创建）
    return candidates[0]


SKILLS_ROOT = find_skills_root()

# 扫描时跳过这些目录/文件
SKIP_NAMES = {".git", "__pycache__", "node_modules", ".DS_Store"}


# ---------------------------------------------------------------------------
# frontmatter 解析（与 wiki_core 保持一致的极简实现）
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict:
    """解析 SKILL.md 顶部的 YAML frontmatter，返回 meta dict。"""
    meta = {}
    if text.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
        if m:
            fm = m.group(1)
            if yaml:
                try:
                    meta = yaml.safe_load(fm) or {}
                except Exception:
                    meta = {}
            else:
                for line in fm.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip("'\"")
    return meta


# ---------------------------------------------------------------------------
# 技能发现与查询
# ---------------------------------------------------------------------------

def discover_skills(root: Path = None) -> list:
    """扫描技能根目录，返回技能列表。

    每个技能是一个 dict:
        {
            "name": str,          # 技能名 (frontmatter.name 或目录名)
            "dir": Path,          # 技能目录
            "skill_md": Path,     # SKILL.md 路径 (可能不存在)
            "description": str,   # frontmatter.description
            "scripts": [Path],    # scripts/ 下的 .py / .mjs / .sh
        }
    """
    root = Path(root) if root else SKILLS_ROOT
    skills = []
    if not root.exists():
        return skills

    for entry in sorted(root.iterdir()):
        if entry.name in SKIP_NAMES:
            continue
        if not entry.is_dir():
            continue

        skill_md = entry / "SKILL.md"
        meta = {}
        if skill_md.exists():
            try:
                meta = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            except Exception:
                meta = {}

        scripts_dir = entry / "scripts"
        scripts = []
        if scripts_dir.exists():
            for pat in ("*.py", "*.mjs", "*.js", "*.sh"):
                scripts.extend(sorted(scripts_dir.glob(pat)))

        skills.append({
            "name": meta.get("name") or entry.name,
            "dir": entry,
            "skill_md": skill_md if skill_md.exists() else None,
            "description": meta.get("description", ""),
            "scripts": scripts,
        })
    return skills


def get_skill(name: str, root: Path = None) -> dict:
    """按名称（或目录名）获取单个技能，找不到返回 None。"""
    for s in discover_skills(root):
        if s["name"] == name or s["dir"].name == name:
            return s
    return None


def read_skill_md(name: str, root: Path = None) -> str:
    """读取某技能的 SKILL.md 全文（供 Agent 载入上下文调用）。"""
    s = get_skill(name, root)
    if not s or not s["skill_md"]:
        return ""
    return s["skill_md"].read_text(encoding="utf-8")


def run_skill_script(name: str, script: str = None, args: list = None,
                     root: Path = None) -> int:
    """运行某技能的脚本。

    Args:
        name: 技能名
        script: 脚本文件名 (如 analyze_video.py)；为 None 时取 scripts/ 下第一个 .py
        args: 传给脚本的参数列表
    Returns:
        子进程退出码
    """
    s = get_skill(name, root)
    if not s:
        raise FileNotFoundError(f"技能未找到: {name}")

    target = None
    if script:
        cand = s["dir"] / "scripts" / script
        target = cand if cand.exists() else None
    else:
        pys = [p for p in s["scripts"] if p.suffix == ".py"]
        target = pys[0] if pys else None

    if not target:
        raise FileNotFoundError(f"技能 {name} 没有可运行脚本: {script or '(默认 .py)'}")

    cmd = [sys.executable, str(target)] + (args or [])
    return subprocess.call(cmd)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    import argparse
    parser = argparse.ArgumentParser(description="MyWiki 统一技能目录加载器")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("root", help="显示当前技能根目录")
    sub.add_parser("list", help="列出所有技能")

    p_show = sub.add_parser("show", help="显示某技能的 SKILL.md")
    p_show.add_argument("name")

    p_run = sub.add_parser("run", help="运行某技能脚本")
    p_run.add_argument("name")
    p_run.add_argument("--script", default=None)
    p_run.add_argument("script_args", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    if args.cmd == "root" or args.cmd is None:
        print(SKILLS_ROOT)
        if args.cmd is None:
            print("\n用法: python loader.py [root|list|show <name>|run <name> ...]")
        return

    if args.cmd == "list":
        skills = discover_skills()
        if not skills:
            print(f"（技能根 {SKILLS_ROOT} 下没有找到技能）")
            return
        print(f"技能根: {SKILLS_ROOT}\n")
        for s in skills:
            desc = (s["description"] or "").strip().replace("\n", " ")
            if len(desc) > 80:
                desc = desc[:80] + "…"
            n_scripts = len(s["scripts"])
            print(f"• {s['name']}  [脚本 {n_scripts}]")
            if desc:
                print(f"    {desc}")
        return

    if args.cmd == "show":
        text = read_skill_md(args.name)
        print(text or f"（未找到技能 {args.name} 或其无 SKILL.md）")
        return

    if args.cmd == "run":
        code = run_skill_script(args.name, args.script, args.script_args)
        sys.exit(code)


if __name__ == "__main__":
    _cli()
