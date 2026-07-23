#!/usr/bin/env python3
"""
Quick Reminder - 快速提醒设置（持久化版本）
使用 Windows 任务计划实现持久化提醒
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

REMINDER_DIR = r"D:\Users\michael\MyWiki\reminders"
REMINDER_FILE = f"{REMINDER_DIR}\\reminders.json"
SCRIPT_DIR = r"D:\Users\michael\MyWiki"

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

def add_reminder(remind_at, message):
    """
    添加提醒（使用 Windows 任务计划实现持久化）
    remind_at: datetime 对象（提醒时间）
    message: 提醒内容
    """
    reminders = load_reminders()
    
    rid = max([r["id"] for r in reminders], default=0) + 1  # 避免ID冲突
    task_name = f"WikiReminder_{rid}"
    reminder = {
        "id": rid,
        "remind_at": remind_at.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending",  # pending, sent, cancelled
        "task_name": None  # Windows 任务名称
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
    创建 Windows 任务计划（一次性）
    提醒触发时，执行 send_reminder.py 发送微信消息
    """
    remind_time = datetime.strptime(reminder["remind_at"], "%Y-%m-%d %H:%M:%S")
    
    # 构造执行命令
    script_path = os.path.join(SCRIPT_DIR, "send_reminder.py")
    python_exe = sys.executable  # 使用当前 Python 解释器的绝对路径
    
    # Windows schtasks 命令
    # 格式：schtasks /create /tn "任务名" /tr "命令" /sc once /st HH:MM /sd YYYY/MM/DD
    date_str = remind_time.strftime("%Y/%m/%d")
    time_str = remind_time.strftime("%H:%M")
    
    cmd = [
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", f'"{python_exe}" "{script_path}" {reminder["id"]}',
        "/sc", "once",
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
