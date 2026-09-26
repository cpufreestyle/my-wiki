#!/usr/bin/env python3
"""
Quick Reminder - 快速提醒设置（持久化版本）
使用 Windows 任务计划实现持久化提醒

重复提醒：通过 reminder_rrule.py（RRULE 子集，零依赖）支持
DAILY/WEEKLY/MONTHLY/YEARLY 周期规则；一次性提醒为默认行为。
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

from reminder_rrule import (
    RRuleError,
    WEEKDAY_CODES,
    describe_rule,
    next_occurrence,
    parse_rrule,
)

# 数据目录跟随统一解析（环境变量 MYWIKI_ROOT > vault > 仓库根），
# 避免 macOS/Linux 上把 Windows 硬编码路径当成相对目录而创建垃圾文件夹。
try:
    from wiki_paths import WIKI_DIR
except Exception:  # noqa: BLE001
    WIKI_DIR = os.path.dirname(os.path.abspath(__file__))
REMINDER_DIR = os.path.join(WIKI_DIR, "reminders")
REMINDER_FILE = os.path.join(REMINDER_DIR, "reminders.json")
SCRIPT_DIR = WIKI_DIR

def load_reminders():
    """加载所有提醒"""
    if os.path.exists(REMINDER_FILE):
        with open(REMINDER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_reminders(reminders):
    """保存提醒列表"""
    if not os.path.exists(REMINDER_DIR):
        os.makedirs(REMINDER_DIR)
    with open(REMINDER_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def add_reminder(remind_at, message, rrule=None):
    """
    添加提醒（使用 Windows 任务计划实现持久化）
    remind_at: datetime 对象（提醒时间；重复提醒时为首次发生时间）
    message: 提醒内容
    rrule: 可选，重复规则字符串（RRULE 子集，见 reminder_rrule.py），
           如 "FREQ=WEEKLY;BYDAY=MO,FR;COUNT=10"；None 为一次性提醒。
           非法规则会抛 RRuleError，不会写入 reminders.json。
    """
    reminders = load_reminders()

    # 重复规则先解析后落库：非法规则直接拒绝，不产生半成品数据
    rule_text = str(rrule).strip() if rrule else None
    if rule_text:
        parse_rrule(rule_text)  # 校验，非法则抛 RRuleError

    rid = max([r["id"] for r in reminders], default=0) + 1  # 避免ID冲突
    task_name = f"WikiReminder_{rid}"
    reminder = {
        "id": rid,
        "remind_at": remind_at.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending",  # pending, sent, cancelled, done
        "task_name": None,  # Windows 任务名称
        "rrule": rule_text,  # 重复规则（None 为一次性提醒）
        "fired_count": 0,    # 已触发次数（重复提醒的 COUNT 上限判断依据）
    }
    
    reminders.append(reminder)
    save_reminders(reminders)
    
    # 创建 Windows 任务计划
    task_name = f"WikiReminder_{reminder['id']}"
    create_windows_task(reminder, task_name)
    reminder["task_name"] = task_name
    save_reminders(reminders)
    
    return reminder

def create_windows_task(reminder, task_name):
    """
    创建 Windows 任务计划
    一次性提醒：/sc once 精确到分；
    重复提醒：按频率映射 /sc daily / weekly / monthly（YEARLY 暂不支持，
    退化为对首次发生排一次性任务，后续由 advance_reminder 推进）。
    提醒触发时，执行 send_reminder.py 发送微信消息
    """
    remind_time = datetime.strptime(reminder["remind_at"], "%Y-%m-%d %H:%M:%S")

    # 构造执行命令
    script_path = os.path.join(SCRIPT_DIR, "send_reminder.py")
    python_exe = sys.executable  # 使用当前 Python 解释器的绝对路径

    # Windows schtasks 命令
    # 一次性：/sc once /st HH:MM /sd YYYY/MM/DD
    # 重复：  /sc daily|weekly|monthly /mo <interval> [/d <dates>] /st HH:MM /sd YYYY/MM/DD
    date_str = remind_time.strftime("%Y/%m/%d")
    time_str = remind_time.strftime("%H:%M")

    schedule = _schtasks_schedule_args(reminder.get("rrule"), remind_time)
    if schedule is None:
        schedule = ["/sc", "once"]

    cmd = [
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", f'"{python_exe}" "{script_path}" {reminder["id"]}',
    ] + schedule + [
        "/st", time_str,
        "/sd", date_str,
        "/f"  # 强制覆盖
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"[提醒] 已创建 Windows 任务：{task_name}")
            print(f"[提醒] 触发时间：{reminder['remind_at']}")
            return True
        else:
            print(f"[提醒] 创建任务失败：{result.stderr}")
            return False
    except Exception as e:
        print(f"[提醒] 创建任务异常：{e}")
        return False

def _schtasks_schedule_args(rule_text, remind_time):
    """重复规则 → schtasks /sc 参数映射；不支持或解析失败返回 None。

    DAILY   -> /sc daily /mo <interval>
    WEEKLY  -> /sc weekly /mo <interval> /d MO,TU,...（无 BYDAY 时用
               首次发生日期的星期）
    MONTHLY -> /sc monthly /mo <interval> /d <bymonthday 或首次发生日号>
    YEARLY  -> schtasks 无年周期，返回 None（退化为一次性任务）
    """
    if not rule_text:
        return None
    try:
        rule = parse_rrule(rule_text)
    except RRuleError:
        return None
    interval = str(rule.get("interval") or 1)
    if rule["freq"] == "DAILY":
        return ["/sc", "daily", "/mo", interval]
    if rule["freq"] == "WEEKLY":
        byday = rule.get("byday") or [WEEKDAY_CODES[remind_time.weekday()]]
        return ["/sc", "weekly", "/mo", interval, "/d", ",".join(byday)]
    if rule["freq"] == "MONTHLY":
        days = rule.get("bymonthday") or [remind_time.day]
        return ["/sc", "monthly", "/mo", interval,
                "/d", ",".join(str(d) for d in days)]
    return None  # YEARLY


def describe_reminder_rule(reminder):
    """重复规则的中文描述；一次性提醒返回 None（供 UI 展示）。"""
    rule_text = reminder.get("rrule")
    if not rule_text:
        return None
    try:
        dt = datetime.strptime(reminder["remind_at"], "%Y-%m-%d %H:%M:%S")
        return describe_rule(rule_text, dt)
    except (RRuleError, ValueError):
        return None


def advance_reminder(reminder_id, now=None):
    """提醒触发后推进：一次性→sent；重复→排下一次；规则耗尽→done。

    返回更新后的 reminder dict；ID 不存在返回 None。
    重复规则按 fired_count 判断 COUNT 上限、按 UNTIL 判断截止；
    YEARLY 等退化为一次性任务的规则会为下一次重新创建 Windows 任务。
    """
    now = now or datetime.now()
    reminders = load_reminders()
    for r in reminders:
        if r["id"] == reminder_id:
            rule_text = r.get("rrule")
            if not rule_text:
                r["status"] = "sent"
                if r.get("task_name"):
                    delete_windows_task(r["task_name"])
                save_reminders(reminders)
                return r
            rule = parse_rrule(rule_text)
            current = datetime.strptime(r["remind_at"], "%Y-%m-%d %H:%M:%S")
            fired = int(r.get("fired_count", 0)) + 1
            r["fired_count"] = fired
            # 时钟回拨时以当前排期为准，避免同一时间重复触发
            nxt = next_occurrence(rule, current, after=max(now, current))
            if nxt is None or (rule.get("count") is not None
                               and fired >= rule["count"]):
                r["status"] = "done"
                if r.get("task_name"):
                    delete_windows_task(r["task_name"])
            else:
                r["remind_at"] = nxt.strftime("%Y-%m-%d %H:%M:%S")
                # 退化为一次性任务的规则（如 YEARLY）：为下一次重新排任务
                if r.get("task_name") and _schtasks_schedule_args(rule_text, nxt) is None:
                    delete_windows_task(r["task_name"])
                    create_windows_task(r, r["task_name"])
            save_reminders(reminders)
            return r
    return None


def mark_reminder_sent(reminder_id):
    """标记提醒已发送，并删除 Windows 任务"""
    reminders = load_reminders()
    for r in reminders:
        if r["id"] == reminder_id:
            r["status"] = "sent"
            
            # 删除 Windows 任务
            if r.get("task_name"):
                delete_windows_task(r["task_name"])
            break
    save_reminders(reminders)

def cancel_reminder(reminder_id):
    """取消提醒（删除 Windows 任务）"""
    reminders = load_reminders()
    for r in reminders:
        if r["id"] == reminder_id and r["status"] == "pending":
            # 删除 Windows 任务
            if r.get("task_name"):
                delete_windows_task(r["task_name"])
            
            r["status"] = "cancelled"
            save_reminders(reminders)
            return True
    return False

def delete_windows_task(task_name):
    """删除 Windows 任务计划"""
    cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"[提醒] 已删除 Windows 任务：{task_name}")
        else:
            print(f"[提醒] 删除任务失败：{result.stderr}")
    except Exception as e:
        print(f"[提醒] 删除任务异常：{e}")

def get_pending_reminders():
    """获取待发送的提醒"""
    reminders = load_reminders()
    return [r for r in reminders if r["status"] == "pending"]

def preset_reminders():
    """预设提醒选项"""
    now = datetime.now()
    return {
        "1小时后": now + timedelta(hours=1),
        "2小时后": now + timedelta(hours=2),
        "3小时后": now + timedelta(hours=3),
        "明天9点": (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0),
        "明天18点": (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0),
        "下周一同9点": (now + timedelta(days=(7 - now.weekday()))).replace(hour=9, minute=0, second=0, microsecond=0)
    }

if __name__ == "__main__":
    print("=== 快速提醒测试（Windows 任务计划版本）===\n")
    
    # 测试：添加1分钟后的提醒
    test_time = datetime.now() + timedelta(minutes=1)
    reminder = add_reminder(test_time, "测试持久化提醒")
    print(f"已添加提醒：{reminder['message']}")
    print(f"提醒时间：{reminder['remind_at']}")
    print(f"提醒ID：{reminder['id']}")
    print(f"Windows 任务：{reminder['task_name']}")
    print("\n✅ 提醒已持久化，即使重启电脑也会触发！")
