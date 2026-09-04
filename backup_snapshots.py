#!/usr/bin/env python3
"""backup_snapshots.py — MyWiki 自动备份快照

将用户数据（wiki/、mood/、reminders/、daily/）打包 zip 到 backups/，
保留最近 N 份，防止误删/误改。桌面端启动时触发 + 每 24h 一次。

配置（可选）：config/backup.json
    {"keep": 7, "dir": "backups", "sources": ["wiki", "mood", "reminders", "daily"]}
缺省 keep=7，sources 如上。backups/ 已在 .gitignore（运行时产物不入库）。
"""
import json
import os
import zipfile
from datetime import datetime

from wiki_paths import _SCRIPT_DIR, WIKI_DIR

DEFAULT_KEEP = 7
DEFAULT_SOURCES = ["wiki", "mood", "reminders", "daily"]


def _load_config():
    """读取 config/backup.json（缺省 keep=7 / 默认源目录）。"""
    cfg = {}
    path = os.path.join(str(_SCRIPT_DIR), "config", "backup.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    keep = int(cfg.get("keep", DEFAULT_KEEP))
    sources = cfg.get("sources") or DEFAULT_SOURCES
    out_dir = cfg.get("dir") or os.path.join(str(_SCRIPT_DIR), "backups")
    return keep, sources, out_dir


def prune_old_snapshots(out_dir, keep):
    """只保留最近 keep 份快照，返回删除数量。"""
    try:
        snaps = sorted(
            f for f in os.listdir(out_dir)
            if f.startswith("mywiki-snapshot-") and f.endswith(".zip")
        )
    except FileNotFoundError:
        return 0
    removed = 0
    for old in snaps[:-keep] if keep > 0 else snaps:
        try:
            os.remove(os.path.join(out_dir, old))
            removed += 1
        except OSError:
            pass
    return removed


def create_snapshot(keep=None, sources=None, out_dir=None):
    """创建一次快照，返回 (zip 路径, 大小字节)；无数据时返回 (None, 0)。

    wiki/ 等目录在 WIKI_DIR（可能是 Obsidian vault），mood/reminders 在仓库根。
    """
    if keep is None or sources is None or out_dir is None:
        keep, sources, out_dir = _load_config()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs(out_dir, exist_ok=True)

    # 收集存在的源目录（绝对路径，允许 WIKI_DIR 下的 vault 与仓库根混用）
    roots = []
    for name in sources:
        for base in (WIKI_DIR, str(_SCRIPT_DIR)):
            cand = os.path.join(base, name)
            if os.path.isdir(cand):
                roots.append((name, cand))
                break

    if not roots:
        return None, 0

    zip_path = os.path.join(out_dir, f"mywiki-snapshot-{stamp}.zip")
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, root in roots:
            for dirpath, _dirnames, filenames in os.walk(root):
                # 跳过缓存/隐藏目录，避免把 .rag_index 之类打包进去
                _dirnames[:] = [d for d in _dirnames
                                if not d.startswith(".") and d != "__pycache__"]
                for fn in filenames:
                    if fn.startswith("."):
                        continue
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, os.path.dirname(root))
                    zf.write(full, rel)
                    count += 1
    if count == 0:
        try:
            os.remove(zip_path)
        except OSError:
            pass
        return None, 0

    removed = prune_old_snapshots(out_dir, keep)
    size = os.path.getsize(zip_path)
    print(f"[backup] 快照完成: {zip_path} ({count} 个文件, "
          f"{size // 1024}KB, 清理旧快照 {removed} 份)")
    return zip_path, size


if __name__ == "__main__":
    create_snapshot()
