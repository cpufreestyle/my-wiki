#!/usr/bin/env python3
"""
Obsidian Sync — 将 MyWiki 内容同步到多个 Obsidian Vault

Usage:
    python sync.py                          # 同步到所有 Vault
    python sync.py --vault documents        # 仅同步到 Documents
    python sync.py --vault wiki             # 仅同步到 Wiki
    python sync.py --generate-index         # 仅生成首页
"""

import argparse
import shutil
import sys
from pathlib import Path
from datetime import datetime

WIKI_ROOT = Path(__file__).parent.parent.parent

VAULTS = {
    "documents": Path.home() / "Documents" / "Obsidian Vault",
    "wiki": WIKI_ROOT / "wiki",
}

# 同步目录配置: (wiki源目录, vault目标目录)
SYNC_DIRS = [
    ("daily", "daily"),
    ("projects", "projects"),
    ("concepts", "concepts"),
    ("people", "people"),
    ("brain", "brain"),
]


def sync_dir_to_vault(src: Path, dst: Path):
    """同步目录内容到 vault"""
    if not src.exists():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in src.glob("*.md"):
        target = dst / f.name
        # 跳过 .obsidian 目录
        if f.name.startswith("."):
            continue
        shutil.copy2(f, target)
        count += 1
    return count


def sync_analysis_reports(vault: Path):
    """同步分析报告到 vault"""
    report_dirs = [
        (WIKI_ROOT.parent, "AI产品经理共学营", ["aipmday*-analysis*.md", "aipmday2*-analysis*.md"]),
        (WIKI_ROOT.parent, "OpenClaw", ["video-analysis-skill*.md", "memo-sync-setup*.md"]),
    ]
    count = 0
    for src_dir, target_subdir, patterns in report_dirs:
        target = vault / target_subdir
        target.mkdir(parents=True, exist_ok=True)
        for pat in patterns:
            for f in src_dir.glob(pat):
                shutil.copy2(f, target / f.name)
                count += 1
    return count


def generate_index(vault: Path):
    """生成 vault 首页"""
    lines = [
        "---\n",
        f"created: {datetime.now().strftime('%Y-%m-%d')}\n",
        "tags: [首页, 索引]\n",
        "---\n\n",
        "# 🏠 My Wiki 首页\n\n",
    ]

    # 扫描各目录
    for dirname, label in [
        ("AI产品经理共学营", "📂 AI 产品经理共学营"),
        ("OpenClaw", "🤖 OpenClaw"),
        ("daily", "📝 日记"),
        ("projects", "🚀 项目"),
        ("concepts", "💡 概念"),
        ("people", "👥 人物"),
    ]:
        d = vault / dirname
        if not d.exists():
            continue
        files = sorted(d.glob("*.md"))
        if not files:
            continue
        lines.append(f"## {label}\n\n")
        for f in files:
            name = f.stem
            lines.append(f"- [[{dirname}/{name}|{name}]]\n")
        lines.append("\n")

    lines.append("---\n\n")
    lines.append(f"*最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

    (vault / "首页.md").write_text("".join(lines), encoding="utf-8")


def sync_to_vault(vault_name: str):
    """同步到指定 vault"""
    vault = VAULTS.get(vault_name)
    if not vault:
        print(f"❌ Unknown vault: {vault_name}", file=sys.stderr)
        return
    if not vault.exists():
        vault.mkdir(parents=True, exist_ok=True)

    total = 0
    for src_name, dst_name in SYNC_DIRS:
        src = WIKI_ROOT / src_name
        dst = vault / dst_name
        count = sync_dir_to_vault(src, dst)
        total += count

    # 同步分析报告
    total += sync_analysis_reports(vault)

    # 生成首页
    generate_index(vault)

    print(f"✅ Synced {total} files to {vault_name} vault: {vault}")


def main():
    parser = argparse.ArgumentParser(description="Obsidian Vault Sync")
    parser.add_argument("--vault", choices=["documents", "wiki", "all"], default="all")
    parser.add_argument("--generate-index", action="store_true")
    args = parser.parse_args()

    if args.generate_index:
        for name in VAULTS:
            generate_index(VAULTS[name])
            print(f"✅ Index generated for {name}")
        return

    if args.vault == "all":
        for name in VAULTS:
            sync_to_vault(name)
    else:
        sync_to_vault(args.vault)


if __name__ == "__main__":
    main()
