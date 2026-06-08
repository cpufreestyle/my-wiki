#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提醒管理器
支持 Windows 任务计划程序 + 系统通知
"""
import os
import json
import re
import uuid
from datetime import datetime, timedelta
from config import WIKI_DIR, REMIND_DIR, REMINDER_FILE, PENDING_FILE

# ===== 提醒存储 =====

def load_reminders():
    """加载所有提醒"""
    REMIND_DIR.mkdir(parents=True, exist_ok=True)
    if REMINDER_FILE.exists():
        with open(REMINDER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_reminders(reminders):
    """保存所有提醒"""
    REMIND_DIR.mkdir(parents=True, exist_ok=True)
    with open(REMINDER_FILE, 'w', encoding='utf-8') as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def add_reminder(title, message, remind_at, repeat=None):
    """添加新提醒"""
    reminders = load_reminders()
    
    new_reminder = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "message": message,
        "remind_at": remind_at,
        "repeat": repeat,  # None, "daily", "weekly", "monthly"
        "done": False,
        "created_at": datetime.now().isoformat()
    }
    
    reminders.append(new_reminder)
    save_reminders(reminders)
    
    # 注册到 Windows 任务计划
    _schedule_windows_task(new_reminder)
    
    return new_reminder

def remove_reminder(reminder_id):
    """删除提醒"""
    reminders = load_reminders()
    reminders = [r for r in reminders if r["id"] != reminder_id]
    save_reminders(reminders)
    
    # 从 Windows 任务计划移除
    _remove_windows_task(reminder_id)
    
    return True

def done_reminder(reminder_id):
    """标记提醒完成"""
    reminders = load_reminders()
    for r in reminders:
        if r["id"] == reminder_id:
            r["done"] = True
            break
    save_reminders(reminders)

# ===== Windows 任务计划 =====
PYTHON_BAT = WIKI_DIR / "reminder_quick.bat"

def _ensure_batch_file():
    """确保批处理文件存在（用于触发通知）"""
    bat_content = f'''@echo off
python "{WIKI_DIR}\\send_reminder.py" %%1
'''
    with open(PYTHON_BAT, 'w', encoding='utf-8') as f:
        f.write(bat_content)

def _schedule_windows_task(reminder):
    """注册到 Windows 任务计划"""
    _ensure_batch_file()
    
    task_name = f"MyWiki_Reminder_{reminder['id']}"
    remind_dt = datetime.fromisoformat(reminder["remind_at"])
    date_str  = remind_dt.strftime("%Y-%m-%d")
    time_str  = remind_dt.strftime("%H:%M")
    
    # 转换时区（UTC+8 → 本地）
    import subprocess
    cmd = [
        "schtasks", "/create", "/tn", task_name,
        "/tr", f'"{PYTHON_BAT}" "{reminder["id"]}"',
        "/sc", "once", "/st", time_str, "/sd", date_str,
        "/f"
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, timeout=10)
    except Exception as e:
        print(f"[WARN] schtasks failed: {e}")

def _remove_windows_task(reminder_id):
    """从 Windows 任务计划移除"""
    import subprocess
    task_name = f"MyWiki_Reminder_{reminder_id}"
    
    try:
        subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"],
                      capture_output=True, timeout=10)
    except Exception:
        pass

# ===== 待处理提醒 =====
def load_pending():
    """加载待通知列表"""
    if PENDING_FILE.exists():
        with open(PENDING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_pending(pending):
    """保存待通知列表"""
    REMIND_DIR.mkdir(parents=True, exist_ok=True)
    with open(PENDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

def add_pending(reminder_id):
    """添加待通知"""
    pending = load_pending()
    if reminder_id not in pending:
        pending.append(reminder_id)
        save_pending(pending)

def check_and_notify():
    """检查并发送到期通知"""
    pending = load_pending()
    if not pending:
        return
    
    reminders = load_reminders()
    now = datetime.now()
    triggered = []
    
    for rid in pending:
        for r in reminders:
            if r["id"] == rid and not r.get("done"):
                remind_at = datetime.fromisoformat(r["remind_at"])
                if remind_at <= now:
                    _show_notification(r)
                    triggered.append(rid)
    
    # 移除已通知
    for rid in triggered:
        pending.remove(rid)
    save_pending(pending)

def _show_notification(reminder):
    """发送 Windows 系统通知"""
    import subprocess
    
    title   = reminder.get("title", "提醒")
    message = reminder.get("message", "")
    
    # 尝试 PowerShell Toast
    script = f'''
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
        [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $textNodes = $template.GetElementsByTagName("text")
    $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) | Out-Null
    $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) | Out-Null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("MyWiki").Show($toast)
    '''
    
    try:
        subprocess.Popen([
            "powershell", "-Command", script
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        print(f"[NOTIFY] {title}: {message}")

# ===== GUI =====
def show_gui():
    """显示 Tkinter GUI"""
    import tkinter as tk
    from tkinter import ttk
    
    root = tk.Tk()
    root.title("My Wiki - 提醒管理")
    root.geometry("600x400")
    
    # 加载数据
    reminders = load_reminders()
    active = [r for r in reminders if not r.get("done")]
    
    # 列表框
    frame = ttk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    columns = ("时间", "标题", "状态")
    tree = ttk.Treeview(frame, columns=columns, show="headings")
    
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150 if col != "标题" else 250)
    
    for r in active:
        dt = datetime.fromisoformat(r["remind_at"])
        status = "每日" if r.get("repeat") == "daily" else "一次性"
        tree.insert("", tk.END, values=(
            dt.strftime("%m-%d %H:%M"),
            r["title"],
            status
        ), tags=(r["id"],))
    
    tree.pack(fill=tk.BOTH, expand=True)
    
    root.mainloop()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # 被计划任务调用
        reminder_id = sys.argv[1]
        check_and_notify()
    else:
        show_gui()
