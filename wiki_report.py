#!/usr/bin/env python3
"""wiki_report.py — MyWiki 周报 / 月报生成（无 GUI 依赖，便于单元测试）

汇总指定周期内的日记、心情、待办，输出 Markdown 报告。
collect_report() 只负责采集数据（便于断言），render_report() 负责渲染。
"""
import json
import os
from collections import Counter
from datetime import datetime, timedelta

from wiki_paths import DAILY_DIR, MOOD_DIR
import wiki_data


def _parse_date(s):
    """把 'YYYY-MM-DD' 解析为 date。"""
    return datetime.strptime(str(s), "%Y-%m-%d").date()


def _iter_dates(start, end):
    """生成 [start, end] 闭区间内的每一天（date）。"""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _read_daily(ds):
    """读取某天日记正文；空模板（仅标题）视为无内容，返回 None。"""
    path = os.path.join(DAILY_DIR, f"{ds}.md")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
    except Exception:
        return None
    if not text or text == f"# {ds} Diary":
        return None
    # 去掉首行 H1 标题（# <date> Diary），只保留正文
    lines = text.split("\n")
    if lines and lines[0].lstrip().startswith("#"):
        lines = lines[1:]
    body = "\n".join(lines).strip()
    return body or None


def _read_moods(ds):
    """读取某天心情记录列表；文件缺失或损坏返回 []。"""
    path = os.path.join(MOOD_DIR, f"{ds}.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _date_of(stamp):
    """取 'YYYY-MM-DD HH:MM:SS' 的日期部分，异常返回 ''。"""
    return str(stamp or "")[:10]


def collect_report(start, end):
    """采集 [start, end] 周期数据，返回 dict（采集与渲染分离，便于测试）。

    start / end 可以是 date，也可以是 'YYYY-MM-DD' 字符串。
    """
    if isinstance(start, str):
        start = _parse_date(start)
    if isinstance(end, str):
        end = _parse_date(end)
    if start > end:
        start, end = end, start

    dates = [d.strftime("%Y-%m-%d") for d in _iter_dates(start, end)]
    date_set = set(dates)

    diaries = {}
    for ds in dates:
        body = _read_daily(ds)
        if body:
            diaries[ds] = body

    mood_counter = Counter()
    mood_days = 0
    for ds in dates:
        recs = _read_moods(ds)
        if recs:
            mood_days += 1
        for r in recs:
            mood = r.get("mood")
            if mood:
                mood_counter[str(mood)] += 1

    todos = wiki_data.load_todos()
    todos_created = [t for t in todos if _date_of(t.get("created_at")) in date_set]
    todos_done = [t for t in todos if t.get("done") and _date_of(t.get("done_at")) in date_set]
    todos_pending = [t for t in wiki_data.sort_todos(todos) if not t.get("done")]

    return {
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "days": len(dates),
        "diaries": diaries,
        "mood_counter": dict(mood_counter),
        "mood_days": mood_days,
        "todos_created": todos_created,
        "todos_done": todos_done,
        "todos_pending": todos_pending,
    }


def render_report(data):
    """把 collect_report() 的结果渲染成 Markdown 字符串。"""
    lines = [f"# MyWiki 报告 {data['start']} ~ {data['end']}", ""]
    lines.append("## 📊 概览")
    lines.append("")
    lines.append(f"- 统计天数：{data['days']} 天")
    lines.append(f"- 有日记：{len(data['diaries'])} 天")
    lines.append(f"- 有心情记录：{data['mood_days']} 天")
    lines.append(f"- 待办新增 {len(data['todos_created'])} / 完成 {len(data['todos_done'])} / 未完成 {len(data['todos_pending'])}")
    lines.append("")

    lines.append("## 💡 心情分布")
    lines.append("")
    if data["mood_counter"]:
        for mood, cnt in sorted(data["mood_counter"].items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"- {mood}：{cnt} 次")
    else:
        lines.append("（本周期无心情记录）")
    lines.append("")

    lines.append("## ✅ 待办")
    lines.append("")
    if data["todos_done"]:
        lines.append("**已完成：**")
        lines.append("")
        for t in data["todos_done"]:
            lines.append(f"- ✅ {t.get('text', '')}")
        lines.append("")
    if data["todos_pending"]:
        lines.append("**待办中：**")
        lines.append("")
        for t in data["todos_pending"]:
            due = f"（截止 {t['due']}）" if t.get("due") else ""
            lines.append(f"- [ ] {t.get('text', '')}{due}")
        lines.append("")
    if not data["todos_done"] and not data["todos_pending"]:
        lines.append("（无待办）")
        lines.append("")

    lines.append("## 📝 日记摘录")
    lines.append("")
    if data["diaries"]:
        for ds, body in sorted(data["diaries"].items()):
            preview = " ".join(body.split())[:200]
            lines.append(f"- **{ds}**：{preview}")
    else:
        lines.append("（本周期无日记）")
    lines.append("")
    return "\n".join(lines)


def weekly_report(ref=None):
    """最近 7 天（含今天）的报告 Markdown。"""
    end = ref or datetime.now().date()
    if isinstance(end, str):
        end = _parse_date(end)
    return render_report(collect_report(end - timedelta(days=6), end))


def monthly_report(ref=None):
    """本月（1 号至今）的报告 Markdown。"""
    end = ref or datetime.now().date()
    if isinstance(end, str):
        end = _parse_date(end)
    return render_report(collect_report(end.replace(day=1), end))


def save_report(text, name):
    """把报告写到 vault 根目录，返回路径。"""
    path = os.path.join(os.path.dirname(DAILY_DIR), name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
