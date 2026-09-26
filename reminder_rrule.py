#!/usr/bin/env python3
"""
reminder_rrule.py — 重复提醒规则引擎（RRULE 子集，零依赖）

融合开源实现 python-dateutil `rrule` / iCalendar RFC 5545 的重复事件语义，
按 MyWiki 提醒场景重实现为纯标准库模块（零第三方依赖，可直接打进 .app 包）：

  - FREQ:     DAILY / WEEKLY / MONTHLY / YEARLY
  - INTERVAL: 步长（每隔几个周期）
  - COUNT:    发生次数上限（自首次发生起计）
  - UNTIL:    截止时间（含边界；DATE 形式按当天 23:59:59 处理）
  - BYDAY:    每周几（仅 WEEKLY），如 BYDAY=MO,WE,FR
  - BYMONTHDAY: 每月几号（仅 MONTHLY），如 BYMONTHDAY=1,15

语义对齐 python-dateutil：
  - dtstart 本身命中规则时算第一次发生，不发生早于 dtstart 的时间点；
  - 目标日期在当期不存在时跳过该期（如每月 31 号会跳过 2 月）；
  - COUNT 与 UNTIL 不得同时指定（RFC 5545 规定）。

用法:
    from reminder_rrule import parse_rrule, iter_occurrences, describe_rule

    rule = parse_rrule("FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,FR;COUNT=5")
    for dt in iter_occurrences(rule, datetime(2026, 9, 28, 9, 0)):
        print(dt)
    print(describe_rule(rule))  # 周一、周五，每隔 2 周，共 5 次

解析失败抛出 RRuleError（ValueError 子类），调用方应在保存提醒前拒绝非法规则。
"""
from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta

__all__ = [
    "RRuleError",
    "FREQS",
    "WEEKDAY_CODES",
    "parse_rrule",
    "iter_occurrences",
    "next_occurrence",
    "describe_rule",
]

FREQS = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")

# Python weekday(): Monday=0 ... Sunday=6，与 RFC 5545 BYDAY 顺序一致
WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
_WEEKDAY_NAMES = {
    "MO": "周一", "TU": "周二", "WE": "周三", "TH": "周四",
    "FR": "周五", "SA": "周六", "SU": "周日",
}
_DEFAULT_HORIZON_DAYS = 366 * 5  # 无 COUNT/UNTIL 时的兜底展开上限（5 年，保证终止）

_UNTIL_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2}))?Z?$")


class RRuleError(ValueError):
    """RRULE 解析或校验错误。"""


def _positive_int(value: str, key: str) -> int:
    """解析正整数参数，失败抛 RRuleError。"""
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        raise RRuleError(f"{key} 必须为正整数，收到 {value!r}")
    if n < 1:
        raise RRuleError(f"{key} 必须为正整数，收到 {value!r}")
    return n


def _parse_until(value: str) -> datetime:
    """解析 UNTIL：YYYYMMDD 或 YYYYMMDDTHHMMSS（可带 Z）。

    DATE 形式按当天 23:59:59 处理，保证截止日当天仍算有效（RFC 5545
    规定 UNTIL 为包含边界）。
    """
    m = _UNTIL_RE.match(value.strip())
    if not m:
        raise RRuleError(
            f"UNTIL 时间格式无效: {value!r}（应为 YYYYMMDD 或 YYYYMMDDTHHMMSS）")
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        if m.group(4) is None:
            return datetime(y, mo, d, 23, 59, 59)
        return datetime(y, mo, d, int(m.group(4)), int(m.group(5)), int(m.group(6)))
    except ValueError as e:
        raise RRuleError(f"UNTIL 不是合法日期时间: {value!r}（{e}）")


def _parse_byday(value: str) -> list:
    """解析 BYDAY=MO,WE,...（仅星期码，不支持 RFC 序号形式如 2MO）。"""
    days = []
    for token in value.split(","):
        code = token.strip().upper()
        if code not in WEEKDAY_CODES:
            raise RRuleError(
                f"BYDAY 仅支持 {'/'.join(WEEKDAY_CODES)}，收到 {token!r}")
        if code not in days:
            days.append(code)
    if not days:
        raise RRuleError("BYDAY 不能为空")
    return sorted(days, key=WEEKDAY_CODES.index)


def _parse_bymonthday(value: str) -> list:
    """解析 BYMONTHDAY=1,15,...（1-31）。"""
    days = []
    for token in value.split(","):
        try:
            n = int(token.strip())
        except ValueError:
            raise RRuleError(f"BYMONTHDAY 必须为 1-31 的整数，收到 {token!r}")
        if not 1 <= n <= 31:
            raise RRuleError(f"BYMONTHDAY 必须为 1-31 的整数，收到 {token!r}")
        if n not in days:
            days.append(n)
    if not days:
        raise RRuleError("BYMONTHDAY 不能为空")
    return sorted(days)


def parse_rrule(text: str) -> dict:
    """解析 RRULE 字符串为规范化 dict；任何非法之处都抛 RRuleError。

    返回结构: {"freq", "interval", "count", "until", "byday", "bymonthday"}，
    未指定的键取默认值（interval=1，其余为 None）。
    """
    if not isinstance(text, str) or not text.strip():
        raise RRuleError("RRULE 不能为空，格式如 FREQ=DAILY;INTERVAL=2")
    rule = {
        "freq": None,
        "interval": 1,
        "count": None,
        "until": None,
        "byday": None,
        "bymonthday": None,
    }
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        key, sep, value = chunk.partition("=")
        if not sep:
            raise RRuleError(f"无效 RRULE 片段 {chunk!r}，应为 KEY=VALUE")
        key = key.strip().upper()
        value = value.strip()
        if key == "FREQ":
            freq = value.upper()
            if freq not in FREQS:
                raise RRuleError(f"FREQ 仅支持 {'/'.join(FREQS)}，收到 {value!r}")
            rule["freq"] = freq
        elif key == "INTERVAL":
            rule["interval"] = _positive_int(value, "INTERVAL")
        elif key == "COUNT":
            rule["count"] = _positive_int(value, "COUNT")
        elif key == "UNTIL":
            rule["until"] = _parse_until(value)
        elif key == "BYDAY":
            rule["byday"] = _parse_byday(value)
        elif key == "BYMONTHDAY":
            rule["bymonthday"] = _parse_bymonthday(value)
        else:
            raise RRuleError(f"不支持的 RRULE 键: {key!r}")
    if rule["freq"] is None:
        raise RRuleError("RRULE 缺少必填键 FREQ")
    if rule["byday"] and rule["freq"] != "WEEKLY":
        raise RRuleError("本实现中 BYDAY 仅支持 FREQ=WEEKLY")
    if rule["bymonthday"] and rule["freq"] != "MONTHLY":
        raise RRuleError("本实现中 BYMONTHDAY 仅支持 FREQ=MONTHLY")
    if rule["count"] is not None and rule["until"] is not None:
        raise RRuleError("COUNT 与 UNTIL 不能同时指定（RFC 5545 规定）")
    return rule


def _as_rule(rule) -> dict:
    """接受已解析 dict 或 RRULE 字符串，统一返回 dict。"""
    if isinstance(rule, str):
        return parse_rrule(rule)
    if isinstance(rule, dict) and rule.get("freq"):
        return rule
    raise RRuleError("rule 必须是 parse_rrule 的解析结果或合法 RRULE 字符串")


def _candidates(rule: dict, dtstart: datetime, horizon_days=None):
    """生成 >= dtstart 的发生时间序列（升序）。

    兜底 horizon 保证无 COUNT/UNTIL 的规则也能终止，默认 5 年。
    """
    horizon = horizon_days if horizon_days is not None else _DEFAULT_HORIZON_DAYS
    deadline = dtstart + timedelta(days=horizon)
    freq = rule["freq"]
    interval = rule.get("interval") or 1

    if freq == "DAILY":
        dt = dtstart
        while dt <= deadline:
            yield dt
            dt += timedelta(days=interval)

    elif freq == "WEEKLY":
        byday = rule.get("byday")
        if not byday:
            # 无 BYDAY：每周同一天
            dt = dtstart
            while dt <= deadline:
                yield dt
                dt += timedelta(weeks=interval)
        else:
            # 有 BYDAY：从 dtstart 所在周（周一为首日）起，按 INTERVAL 周步进
            week_monday = dtstart - timedelta(days=dtstart.weekday())
            while week_monday <= deadline:
                for code in byday:
                    day = week_monday + timedelta(days=WEEKDAY_CODES.index(code))
                    dt = datetime.combine(day.date(), dtstart.time())
                    if dt >= dtstart:
                        yield dt
                week_monday += timedelta(weeks=interval)

    else:  # MONTHLY / YEARLY
        step_months = interval if freq == "MONTHLY" else interval * 12
        if freq == "YEARLY":
            plan = [(dtstart.month, dtstart.day)]
        else:
            # 无 BYMONTHDAY 时沿用 dtstart 的日号
            plan = [(None, day) for day in (rule.get("bymonthday") or [dtstart.day])]
        idx = 0
        while True:
            month_index = dtstart.year * 12 + (dtstart.month - 1) + idx * step_months
            year, mon = divmod(month_index, 12)
            mon += 1
            if datetime(year, mon, 1) > deadline:
                return
            for fixed_mon, day in plan:
                use_mon = fixed_mon if fixed_mon is not None else mon
                if day > calendar.monthrange(year, use_mon)[1]:
                    continue  # 该期不存在目标日期，跳过（dateutil 语义）
                dt = datetime(year, use_mon, day,
                              dtstart.hour, dtstart.minute, dtstart.second)
                if dt >= dtstart:
                    yield dt
            idx += 1


def iter_occurrences(rule, dtstart: datetime, count=None, horizon_days=None):
    """按规则展开发生时间序列。

    - count 为 None 时沿用规则的 COUNT；UNTIL 与 COUNT 均约束展开长度。
    """
    rule = _as_rule(rule)
    if not isinstance(dtstart, datetime):
        raise RRuleError("dtstart 必须为 datetime 对象")
    limit = rule["count"] if count is None else count
    until = rule["until"]
    produced = 0
    for dt in _candidates(rule, dtstart, horizon_days=horizon_days):
        if until is not None and dt > until:
            return
        yield dt
        produced += 1
        if limit is not None and produced >= limit:
            return


def next_occurrence(rule, dtstart: datetime, after=None, horizon_days=None):
    """返回严格晚于 after（默认 dtstart）的下一次发生；耗尽返回 None。

    不应用规则 COUNT（次数上限由调用方按已触发次数管理），
    但仍应用 UNTIL 与兜底 horizon。
    """
    rule = _as_rule(rule)
    if not isinstance(dtstart, datetime):
        raise RRuleError("dtstart 必须为 datetime 对象")
    ref = after if after is not None else dtstart
    if not isinstance(ref, datetime):
        raise RRuleError("after 必须为 datetime 对象")
    for dt in _candidates(rule, dtstart, horizon_days=horizon_days):
        if dt > ref:
            if rule["until"] is not None and dt > rule["until"]:
                return None
            return dt
    return None


def describe_rule(rule, dtstart=None) -> str:
    """生成中文可读描述，如「周五、周一，每隔 2 周，共 5 次」。"""
    rule = _as_rule(rule)
    freq = rule["freq"]
    interval = rule.get("interval") or 1

    if freq == "DAILY":
        base = "每天" if interval == 1 else f"每隔 {interval} 天"
    elif freq == "WEEKLY":
        byday = rule.get("byday")
        if byday:
            names = "、".join(_WEEKDAY_NAMES[c] for c in byday)
            base = names if interval == 1 else f"{names}，每隔 {interval} 周"
        elif dtstart is not None:
            base = f"每{_WEEKDAY_NAMES[WEEKDAY_CODES[dtstart.weekday()]]}"
            if interval > 1:
                base += f"，每隔 {interval} 周"
        else:
            base = "每周"
    elif freq == "MONTHLY":
        day = rule["bymonthday"][0] if rule.get("bymonthday") else (
            dtstart.day if dtstart is not None else None)
        if day is None:
            base = "每月"
        elif interval == 1:
            base = f"每月 {day} 号"
        else:
            base = f"每隔 {interval} 个月的 {day} 号"
    else:  # YEARLY
        if dtstart is not None and interval == 1:
            base = f"每年 {dtstart.month} 月 {dtstart.day} 日"
        elif dtstart is not None:
            base = f"每隔 {interval} 年的 {dtstart.month} 月 {dtstart.day} 日"
        else:
            base = "每年"

    extras = []
    if rule["count"] is not None:
        extras.append(f"共 {rule['count']} 次")
    if rule["until"] is not None:
        extras.append(f"至 {rule['until']:%Y-%m-%d %H:%M}")
    if extras:
        return base + "，" + "，".join(extras)
    return base
