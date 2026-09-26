#!/usr/bin/env python3
"""
wiki_links.py — Wiki 双链（[[wikilink]]）解析 / 反向链接 / 链接健康检查

Obsidian 风格双向链接是知识库的核心能力：本模块以纯标准库实现链接图，
零第三方依赖，供 CLI / 桌面端 / Web 端复用。只读扫描，不写入任何笔记。

支持语法（[[目标]], [[目标#锚点]], [[目标|别名]]）：
  - 根相对：[[projects/Alpha]]、[[projects/Alpha.md]]
  - 裸文件名：[[Alpha]]（按文件名 stem 全局匹配）
  - 源文件相对：[[../concepts/X]]（相对来源笔记所在目录）

用法:
    from wiki_links import scan_links, build_backlinks, find_orphans

    graph = scan_links(wiki_root)
    back = build_backlinks(graph)
    orphans = find_orphans(graph)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path, PurePosixPath

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

__all__ = [
    "SKIP_DIRS",
    "iter_notes",
    "extract_links",
    "build_stem_index",
    "resolve_target",
    "resolve_note_arg",
    "scan_links",
    "build_backlinks",
    "find_orphans",
    "find_unresolved",
]

# 扫描时跳过的目录（工具产物 / 二进制资产 / 备份）
SKIP_DIRS = {
    ".git", ".obsidian", "__pycache__", ".trash", "attachments",
    "node_modules", ".venv", "venv", "dist", "build", "backups", "logs",
    "inbox",  # 收件箱为临时捕获区，不参与链接图
}


def _is_scannable_dir(name):
    """是否进入该目录扫描：显式黑名单 + 所有点开头目录（.obsidian/.codebuddy 等）。"""
    return name not in SKIP_DIRS and not name.startswith(".")


# [[目标]] / [[目标#锚点]] / [[目标|别名]]；别名与锚点不计入目标
_LINK_RE = re.compile(r"\[\[([^\[\]|#\n]+)(?:#[^\[\]|\n]*)?(?:\|[^\[\]\n]*)?\]\]")


def iter_notes(wiki_root):
    """产出 wiki 根下全部 Markdown 笔记（相对 wiki_root 的 posix 路径，排序稳定）。"""
    root = Path(wiki_root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if _is_scannable_dir(d))
        for name in sorted(filenames):
            if name.lower().endswith(".md"):
                rel = PurePosixPath(Path(dirpath).relative_to(root).as_posix(), name)
                yield str(rel)


def extract_links(text):
    """抽取文本中的全部 [[链接目标]]（去重、保序，不含别名/锚点）。"""
    targets = []
    for m in _LINK_RE.finditer(text or ""):
        target = m.group(1).strip()
        if target and target not in targets:
            targets.append(target)
    return targets


def _find_file(root, rel):
    """按大小写不敏感方式确认文件存在，返回磁盘上的真实相对路径。

    macOS默认文件系统大小写不敏感：直接拼路径判断会把 beta.md 当成
    Beta.md 的合法命中，导致链接图出现与磁盘不一致的路径名。这里回读
    目录项取真实文件名，保证链接图路径与磁盘严格一致。
    """
    if not rel:
        return None
    pure = PurePosixPath(str(rel).replace("\\", "/"))
    parent = root.joinpath(*pure.parent.parts) if pure.parent.parts else root
    if not parent.is_dir():
        return None
    try:
        entries = os.listdir(parent)
    except OSError:
        return None
    parent_rel = str(pure.parent) if pure.parent.parts else ""
    if pure.name in entries and (parent / pure.name).is_file():
        return f"{parent_rel}/{pure.name}" if parent_rel else pure.name
    lower = pure.name.lower()
    for entry in entries:
        if entry.lower() == lower and (parent / entry).is_file():
            return f"{parent_rel}/{entry}" if parent_rel else entry
    return None


def _normalize_rel(path_str):
    """把可能含 ./ ../ 的相对路径规范化为干净的 posix 相对路径。"""
    parts = []
    for seg in str(path_str).replace("\\", "/").split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(seg)
    return "/".join(parts)


def build_stem_index(notes, wiki_root=None):
    """文件名 stem -> [相对路径...] 索引（小写，支持裸文件名链接解析）。"""
    index = {}
    for rel in notes:
        stem = PurePosixPath(rel).stem.lower()
        index.setdefault(stem, []).append(rel)
    return index


def resolve_target(target, source_rel, wiki_root, stem_index=None):
    """把链接目标解析为实际笔记相对路径；无法解析返回 None。

    解析顺序（Obsidian 习惯）：根相对 .md -> 源文件同目录相对 -> 全局 stem 匹配。
    """
    if not target or not target.strip():
        return None
    root = Path(wiki_root)
    raw = target.strip().replace("\\", "/")
    base = raw[:-3] if raw.lower().endswith(".md") else raw
    if not base:
        return None

    candidates = []
    if raw.startswith("/"):
        candidates.append(_normalize_rel(base + ".md"))
    else:
        candidates.append(_normalize_rel(base + ".md"))
        src_dir = PurePosixPath(source_rel).parent
        candidates.append(_normalize_rel(str(src_dir / (base + ".md"))))
    # 同名文件（无扩展名引用，如指向附件或目录）
    candidates.append(_normalize_rel(base))

    for cand in candidates:
        found = _find_file(root, cand)
        if found:
            return found

    # 裸文件名 stem 全局匹配（同名多个时取目录序第一个，保证确定性）
    if "/" not in base:
        index = stem_index if stem_index is not None else build_stem_index(iter_notes(root), root)
        hits = index.get(base.lower(), [])
        if hits:
            return sorted(hits)[0]
    return None


def resolve_note_arg(arg, wiki_root):
    """解析 CLI 传入的笔记参数（路径 / stem / 不带 .md）为相对路径；找不到返回 None。"""
    if not arg:
        return None
    root = Path(wiki_root)
    raw = arg.strip().replace("\\", "/")
    base = raw[:-3] if raw.lower().endswith(".md") else raw

    for cand in (base + ".md", base):
        found = _find_file(root, _normalize_rel(cand))
        if found:
            return found

    index = build_stem_index(iter_notes(root), root)
    hits = index.get(base.lower(), [])
    if hits:
        return sorted(hits)[0]
    return None


def scan_links(wiki_root):
    """扫描全库构建链接图。

    返回 {
        "links":     {来源相对路径: [可解析目标相对路径...]},
        "raw":       {来源相对路径: [原始目标串...]},
        "dangling":  {无法解析的原始目标: [来源相对路径...]},
        "notes":     [全部笔记相对路径...],
        "stem_index": {stem: [路径...]},
    }
    """
    root = Path(wiki_root)
    notes = list(iter_notes(root))
    stem_index = build_stem_index(notes, root)
    links, raw_map, dangling = {}, {}, {}
    for rel in notes:
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        targets = extract_links(text)
        raw_map[rel] = targets
        resolved = []
        for target in targets:
            hit = resolve_target(target, rel, root, stem_index)
            if hit is None:
                dangling.setdefault(target, [])
                if rel not in dangling[target]:
                    dangling[target].append(rel)
            elif hit not in resolved:
                resolved.append(hit)
        links[rel] = resolved
    return {
        "links": links,
        "raw": raw_map,
        "dangling": dangling,
        "notes": notes,
        "stem_index": stem_index,
    }


def build_backlinks(graph, ignore_self=True):
    """反向链接表 {目标相对路径: [来源相对路径...]}（来源去重排序）。"""
    backlinks = {}
    for source, targets in graph["links"].items():
        for target in targets:
            if ignore_self and target == source:
                continue
            backlinks.setdefault(target, [])
            if source not in backlinks[target]:
                backlinks[target].append(source)
    return {k: sorted(v) for k, v in backlinks.items()}


def find_orphans(graph, backlinks=None, exclude=()):
    """孤儿笔记：没有任何入链的笔记（忽略自链），按路径排序。"""
    if backlinks is None:
        backlinks = build_backlinks(graph)
    excluded = {_normalize_rel(e) for e in exclude}
    return [rel for rel in graph["notes"]
            if rel not in backlinks and rel not in excluded]


def find_unresolved(graph):
    """无法解析的链接（疑似笔误 / 尚未创建的笔记）：
    [(原始目标, [来源...])...] 按目标排序。"""
    return sorted(graph["dangling"].items(), key=lambda kv: kv[0])
