#!/usr/bin/env python3
"""tests/_immutable_guard.py — 只读内容目录的快照与比对助手

AGENTS.md 把 brain/、daily/、wiki/ 定为「用户内容，Agent 只读」。这条规则此前只是文字：
任何一个用例 import 到会写笔记的函数，就能往真实 vault 里落文件，而三秒跑完的单测没人会去翻。
tests/run_all.py 用这里的 snapshot()/changes() 在跑全套前后各做一次快照并比对，
把「写进了只读目录」变成非零退出码 + 指名路径的失败。

纯标准库，且只 stat 不读内容（wiki/ 里单个文件就有 4MB）。
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 与 AGENTS.md 的「不可变目录（只读）」一节一一对应
IMMUTABLE_DIRS = ("brain", "daily", "wiki")

# Obsidian 的窗口状态和 macOS 访达的缩略图缓存：用户动一下鼠标就会变，
# 不代表内容被写坏，守它们只会制造假警报。
SKIP_DIRS = {".obsidian"}
SKIP_FILES = {".DS_Store"}


def snapshot(dirs=IMMUTABLE_DIRS, root=None):
    """返回 {相对 root 的路径: (mtime_ns, size)}，用于与后续快照比对。

    目录不存在时跳过（CI 的全新检出可能没有 daily/），不当成违规。
    """
    base = Path(root) if root is not None else REPO_ROOT
    state = {}
    for name in dirs:
        top = base / name
        if not top.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for filename in filenames:
                if filename in SKIP_FILES:
                    continue
                path = Path(dirpath) / filename
                try:
                    info = path.stat()
                except OSError:
                    # 快照瞬间正被其他进程增删，交给 changes() 的「新增/删除」判定
                    continue
                state[os.path.relpath(path, base)] = (info.st_mtime_ns, info.st_size)
    return state


def changes(before, after):
    """比对两次快照，返回逐条指名路径的可读报告；无变化时为空列表。"""
    report = ["新增: {}".format(p) for p in sorted(set(after) - set(before))]
    report += ["删除: {}".format(p) for p in sorted(set(before) - set(after))]
    report += [
        "修改: {}（{} -> {} 字节）".format(p, before[p][1], after[p][1])
        for p in sorted(set(before) & set(after))
        if before[p] != after[p]
    ]
    return report
