"""wiki_digest.py — 每日摘要模块（复刻 Notion AI 每日摘要）。

汇总当天改动的笔记，生成 daily/digest/YYYY-MM-DD.md：
优先走本地 Ollama（llm_qa.generate）做归纳；
模型不可用或生成失败时，自动降级为零依赖的抽取式摘要。
写入 daily/ 与 scripts/auto_fetch.py 写 daily/rss/ 的先例一致
（运行时可写；测试一律传临时 root）。

主要 API：
    gather_day_notes(root, day)          -> list[dict(rel, text)]
    extractive_digest(notes)             -> Markdown 文本
    build_digest(root, day, use_ai=True) -> (Path | None, mode)

CLI（经 wiki_tool.py 转发）：
    digest [YYYY-MM-DD] [--no-ai] [--root DIR]

依赖：仅标准库（AI 路径懒加载 llm_qa）。
"""

import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

_SOURCES = ("brain", "daily", "wiki")
_SKIP_DIRS = {".git", ".obsidian", ".venv", "__pycache__", "node_modules",
              "dist-publish", "inbox", "backups"}
_MAX_NOTES = 20
_NOTE_CHARS = 2000


def _to_date(value):
    """把 None / date / 'YYYY-MM-DD' 统一成 date。"""
    if value is None:
        return date.today()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _iter_md(root):
    """遍历 root 下三个来源目录的 Markdown 文件。"""
    base = Path(root)
    for src in _SOURCES:
        top = base / src
        if not top.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for name in sorted(filenames):
                if name.lower().endswith((".md", ".markdown")):
                    yield Path(dirpath) / name


def gather_day_notes(root, day=None):
    """收集当天的笔记：文件名以日期开头，或 mtime 命中当天。

    返回 [{'rel': 相对路径, 'text': 全文}]，按 rel 排序。
    """
    day = _to_date(day)
    day_s = day.isoformat()
    base = Path(root)
    notes = []
    for path in _iter_md(base):
        try:
            stat = path.stat()
        except OSError:
            continue
        hit_name = path.name.startswith(day_s)
        hit_mtime = datetime.fromtimestamp(stat.st_mtime).date() == day
        if not (hit_name or hit_mtime):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        notes.append({"rel": path.relative_to(base).as_posix(),
                      "text": text})
    notes.sort(key=lambda n: n["rel"])
    return notes


def _split_frontmatter(text):
    """极简 frontmatter 解析，返回 (meta, body)。"""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end = idx
            break
    if end is None:
        return {}, text
    meta = {}
    for line in lines[1:end]:
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip("'\"")
    return meta, "\n".join(lines[end + 1:])


def _sentences(body):
    """正文切句：按中英文句末标点与换行，长度 12~120 的才算有效句。"""
    parts = re.split(r"[。！？!?\n]", body)
    out = []
    for p in parts:
        s = p.strip().strip("-*#>|").strip()
        if 12 <= len(s) <= 120:
            out.append(s)
    return out


def _title_of(note):
    """笔记标题：frontmatter title -> 首个一级标题 -> 文件名。"""
    meta, body = _split_frontmatter(note["text"])
    title = (meta.get("title") or "").strip()
    if not title:
        m = re.search(r"^#\s+(.+)$", body, re.M)
        if m:
            title = m.group(1).strip()
    return title or Path(note["rel"]).stem


def extractive_digest(notes):
    """零依赖抽取式摘要：清单 + 标签分布 + 每篇最长两句。"""
    lines = ["# 每日摘要", "",
             "共 %d 篇笔记有更新。" % len(notes), "",
             "## 今日笔记", ""]
    tag_count = {}
    for note in notes:
        meta, body = _split_frontmatter(note["text"])
        tags = meta.get("tags", "")
        for t in re.split(r"[,\[\]'\"]+", tags):
            t = t.strip()
            if t:
                tag_count[t] = tag_count.get(t, 0) + 1
        title = _title_of(note)
        lines.append("- [%s](%s)" % (title, note["rel"]))
        lines.append("")
    lines.append("## 标签分布")
    lines.append("")
    if tag_count:
        for tag, count in sorted(tag_count.items(), key=lambda kv: -kv[1]):
            lines.append("- %s × %d" % (tag, count))
    else:
        lines.append("（今日笔记没有标签）")
    lines.append("")
    lines.append("## 要点摘录")
    lines.append("")
    for note in notes:
        meta, body = _split_frontmatter(note["text"])
        lines.append("### %s" % _title_of(note))
        lines.append("")
        lines.append("来源：%s" % note["rel"])
        lines.append("")
        sents = _sentences(body)
        if sents:
            for s in sents[:2]:
                lines.append("- %s" % s)
        else:
            lines.append("- （无可摘录的正文）")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_prompt(notes, day):
    """构造 AI 摘要 prompt：每篇截断，总量设上限。"""
    parts = ["你是个人知识库助手。请把下面 %s 的 %d 篇笔记更新"
             "归纳成一份中文每日摘要：先一段总体概述，再按主题"
             "分组列出要点，最后给出 3 条可执行的下一步建议。"
             % (day.isoformat(), len(notes)), ""]
    for note in notes[:_MAX_NOTES]:
        parts.append("=== %s ===" % note["rel"])
        parts.append(note["text"][:_NOTE_CHARS])
        parts.append("")
    return "\n".join(parts)


def build_digest(root, day=None, use_ai=True):
    """生成每日摘要，返回 (Path | None, mode)。

    mode: 'ai'（模型生成）/ 'extractive'（抽取兜底）/ 'empty'（无笔记）。
    """
    day = _to_date(day)
    root = Path(root)
    notes = gather_day_notes(root, day)
    if not notes:
        return None, "empty"
    mode = "extractive"
    body = extractive_digest(notes)
    if use_ai:
        try:
            import llm_qa
            if llm_qa.ollama_available():
                generated = llm_qa.generate(_build_prompt(notes, day),
                                            timeout=180)
                if generated and generated.strip():
                    body = generated.strip() + "\n"
                    mode = "ai"
        except Exception:
            mode = "extractive"
    out_dir = root / "daily" / "digest"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ("%s.md" % day.isoformat())
    header = ("---\ndate: %s\nmode: %s\nnotes: %d\n---\n\n"
              % (day.isoformat(), mode, len(notes)))
    path.write_text(header + body, encoding="utf-8")
    return path, mode


# ------------------------------------------------------------ CLI

def _default_root():
    """推断知识库根目录：MYWIKI_ROOT > wiki_paths.WIKI_DIR > 本文件所在目录。"""
    env = os.environ.get("MYWIKI_ROOT")
    if env:
        return Path(env).expanduser()
    try:
        import wiki_paths
        return Path(wiki_paths.WIKI_DIR)
    except Exception:
        return Path(__file__).resolve().parent


def main(argv):
    """CLI 入口：digest [YYYY-MM-DD] [--no-ai] [--root DIR]。"""
    import argparse
    parser = argparse.ArgumentParser(
        prog="wiki_tool digest", description="生成每日摘要")
    parser.add_argument("day", nargs="?", default=None,
                        help="日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--no-ai", action="store_true",
                        help="跳过 AI，只用抽取式摘要")
    parser.add_argument("--root", default=None, help="知识库根目录")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser() if args.root else _default_root()
    day = None
    if args.day:
        try:
            day = date.fromisoformat(args.day)
        except ValueError:
            print("[ERROR] 日期格式应为 YYYY-MM-DD: %s" % args.day)
            return 2
    try:
        path, mode = build_digest(root, day, use_ai=not args.no_ai)
    except ValueError as exc:
        print("[ERROR] %s" % exc)
        return 2
    if path is None:
        print("[OK] 当天没有笔记更新，未生成摘要。")
        return 0
    print("[OK] 已生成摘要（%s）-> %s" % (mode, path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
