"""wiki_srs.py — 间隔重复复习模块（复刻 RemNote Pro / Readwise）。

从笔记中抽取问答卡与填空卡，按 SM-2 lite 算法安排复习：
Q:/A: 相邻两行构成问答卡，==高亮== 构成填空卡；
复习状态存 <root>/srs.json，损坏时按空状态处理。

主要 API：
    extract_cards(md_text, source)            -> list[dict]
    due_cards(cards, state, today, limit)     -> list[dict]
    review(card, state, grade, today)         -> dict（更新后的卡片状态）
    load_state(root) / save_state(root, state)

CLI（经 wiki_tool.py 转发）：
    review [--root DIR] [--limit N] / cards [--root DIR]

依赖：仅标准库。
"""

import hashlib
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

STATE_NAME = "srs.json"

_QA_RE = re.compile(r"^Q:\s*(.+?)\s*\n^A:\s*(.+?)\s*$", re.M)
_CLOZE_RE = re.compile(r"==([^=\n]+)==")
_GRADES = ("again", "hard", "good", "easy")
_BASE_INTERVAL = {"again": 0, "hard": 1, "good": 3, "easy": 7}


# ------------------------------------------------------------ 抽卡

def _card_id(key):
    """卡片稳定 ID：key 的 sha1 前 12 位。"""
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def extract_cards(md_text, source):
    """从 Markdown 文本抽取卡片，返回 list[dict]。

    两种形态：Q:/A: 相邻行 -> 问答卡；==高亮== -> 填空卡
    （问题取所在行、把高亮替换为省略号）。按 key 去重。
    """
    cards = []
    seen = set()

    def add(key, card):
        if key in seen:
            return
        seen.add(key)
        cards.append(card)

    for m in _QA_RE.finditer(md_text):
        q = m.group(1).strip()
        a = m.group(2).strip()
        if q and a:
            add(("qa", q), {
                "id": _card_id("qa:" + q),
                "kind": "qa",
                "question": q,
                "answer": a,
                "source": source,
            })
    for m in _CLOZE_RE.finditer(md_text):
        cloze = m.group(1).strip()
        if not cloze:
            continue
        start = m.start()
        line_start = md_text.rfind("\n", 0, start) + 1
        line_end = md_text.find("\n", m.end())
        if line_end < 0:
            line_end = len(md_text)
        line = md_text[line_start:line_end]
        question = line.replace("==" + cloze + "==", "〔…〕").strip()
        add(("cloze", cloze), {
            "id": _card_id("cloze:" + cloze),
            "kind": "cloze",
            "question": question,
            "answer": cloze,
            "source": source,
        })
    return cards


def _iter_md(root, sources=("brain", "daily")):
    """遍历 root 下各来源目录的 Markdown 文件。"""
    base = Path(root)
    skip = {".git", ".obsidian", ".venv", "__pycache__", "node_modules"}
    for src in sources:
        top = base / src
        if not top.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for name in sorted(filenames):
                if name.lower().endswith((".md", ".markdown")):
                    yield Path(dirpath) / name


def collect_cards(root):
    """收集全库卡片，按文件顺序合并。"""
    cards = []
    base = Path(root)
    for path in _iter_md(base):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(base).as_posix()
        cards.extend(extract_cards(text, rel))
    return cards


# ------------------------------------------------------------ 状态与调度

def _to_date(value):
    """把 None / date / 'YYYY-MM-DD' 统一成 date。"""
    if value is None:
        return date.today()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def load_state(root):
    """读取复习状态；文件缺失或损坏时返回空 dict。"""
    path = Path(root) / STATE_NAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(root, state):
    """写回复习状态（UTF-8，缩进 2 便于人工查看）。"""
    path = Path(root) / STATE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def due_cards(cards, state, today=None, limit=20):
    """筛出今天到期的卡片：新卡或 due <= today；按 id 排序后截断。"""
    day_s = _to_date(today).isoformat()
    due = [c for c in cards
           if c["id"] not in state
           or str(state[c["id"]].get("due", day_s)) <= day_s]
    due.sort(key=lambda c: c["id"])
    return due[:limit]


def review(card, state, grade, today=None):
    """按 SM-2 lite 更新卡片状态并写回 state，返回该卡片状态。

    评分 again/hard/good/easy：
      again -> 遗忘：lapses+1、reps 归零、ease-0.2、当天再练；
      hard  -> ease-0.15；easy -> ease+0.1（上下界 1.3~3.0）；
      首次正确按基础间隔，之后 interval = round(上次 * ease)。
    """
    if grade not in _GRADES:
        raise ValueError("评分必须是 %s 之一" % "/".join(_GRADES))
    day = _to_date(today)
    prev = state.get(card["id"]) or {}
    st = dict(prev)
    ease = float(st.get("ease", 2.5))
    if grade == "again":
        st["lapses"] = int(st.get("lapses", 0)) + 1
        st["reps"] = 0
        st["ease"] = max(1.3, ease - 0.2)
        st["interval"] = 0
    else:
        reps = int(st.get("reps", 0)) + 1
        st["reps"] = reps
        if reps == 1:
            st["interval"] = _BASE_INTERVAL[grade]
        else:
            st["interval"] = max(1, round(int(st.get("interval", 0)) * ease))
        if grade == "hard":
            st["ease"] = max(1.3, ease - 0.15)
        elif grade == "easy":
            st["ease"] = min(3.0, ease + 0.1)
        else:
            st["ease"] = ease
    st["grade"] = grade
    st["last"] = day.isoformat()
    st["due"] = (day + timedelta(days=int(st["interval"]))).isoformat()
    state[card["id"]] = st
    return st


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


def _list_cards(root):
    """cards 子命令：逐卡打印类型 / ID / 问题 / 到期与次数。"""
    state = load_state(root)
    cards = collect_cards(root)
    for c in cards:
        st = state.get(c["id"], {})
        print("[%s] %s | %s | due=%s reps=%s" % (
            c["kind"], c["id"], c["question"][:40],
            st.get("due", "new"), st.get("reps", 0)))
    print("共 %d 张卡片。" % len(cards))
    return 0


def _run_review(root, limit):
    """review 子命令：终端交互复习，结束后统一保存状态。"""
    state = load_state(root)
    cards = due_cards(collect_cards(root), state, limit=limit)
    if not cards:
        print("今天没有到期的卡片。")
        return 0
    print("共 %d 张到期卡片。评分: again/hard/good/easy，输入 q 退出。" % len(cards))
    for idx, card in enumerate(cards, 1):
        print("\n[%d/%d][%s] %s" % (idx, len(cards), card["kind"],
                                    card["question"]))
        try:
            input("回想后按回车看答案...")
            print("答案: %s" % card["answer"])
            grade = input("评分 [again/hard/good/easy，默认 good]: ")
        except EOFError:
            break
        grade = grade.strip().lower()
        if grade in ("q", "quit"):
            break
        if grade not in _GRADES:
            grade = "good"
        st = review(card, state, grade)
        print("  -> 间隔 %d 天，下次 %s" % (st["interval"], st["due"]))
    save_state(root, state)
    print("已保存 %d 条复习记录 -> %s" % (len(state),
                                         Path(root) / STATE_NAME))
    return 0


def main(argv):
    """CLI 入口：review [--root DIR] [--limit N] / cards [--root DIR]。"""
    import argparse
    parser = argparse.ArgumentParser(
        prog="wiki_tool", description="间隔重复复习")
    sub = parser.add_subparsers(dest="cmd")
    p_review = sub.add_parser("review", help="开始复习")
    p_review.add_argument("--root", default=None, help="知识库根目录")
    p_review.add_argument("--limit", type=int, default=20, help="每次上限")
    p_cards = sub.add_parser("cards", help="列出所有卡片")
    p_cards.add_argument("--root", default=None, help="知识库根目录")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser() if args.root else _default_root()
    if args.cmd == "cards":
        return _list_cards(root)
    if args.cmd == "review":
        return _run_review(root, args.limit)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
