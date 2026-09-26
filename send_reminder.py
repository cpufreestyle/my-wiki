#!/usr/bin/env python3
"""
Send Reminder - 发送提醒（被 Windows 任务计划调用）
简化版：只写文件，由 OpenClaw 心跳检查并发送
"""
import sys
import json
import os
from datetime import datetime

# 重复提醒推进：一次性→sent；重复→排下一次；耗尽→done。
# 打包版或异常环境下 import 失败时，退化为原来的 sent 标记逻辑。
try:
    from reminder_manager import advance_reminder
except Exception:  # noqa: BLE001
    advance_reminder = None

# 数据目录跟随统一解析（环境变量 MYWIKI_ROOT > vault > 仓库根），
# 避免 macOS/Linux 上把 Windows 硬编码路径当成相对目录而创建垃圾文件夹。
try:
    from wiki_paths import WIKI_DIR
except Exception:  # noqa: BLE001
    WIKI_DIR = os.path.dirname(os.path.abspath(__file__))
REMINDER_DIR = os.path.join(WIKI_DIR, "reminders")
REMINDER_FILE = os.path.join(REMINDER_DIR, "reminders.json")
PENDING_FILE = os.path.join(REMINDER_DIR, "pending_notifications.json")

def load_reminders():
    """加载所有提醒"""
    if os.path.exists(REMINDER_FILE):
        with open(REMINDER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_reminders(reminders):
    """保存提醒列表"""
    with open(REMINDER_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def load_pending():
    """加载待发送通知"""
    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_pending(pending):
    """保存待发送通知"""
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

def notify_openclaw(message):
    """
    通知 OpenClaw 发送消息
    写入 pending_notifications.json，由心跳检查并发送
    """
    pending = load_pending()
    notification = {
        "id": len(pending) + 1,
        "message": f"[Reminder] {message}",
        "created_at": datetime.now().isoformat(),
        "status": "pending"  # pending, sent, failed
    }
    pending.append(notification)
    save_pending(pending)
    print(f"[OK] Notification queued: {message}")
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python send_reminder.py <reminder_id>")
        sys.exit(1)
    
    reminder_id = int(sys.argv[1])
    
    # 加载提醒
    reminders = load_reminders()
    reminder = None
    for r in reminders:
        if r["id"] == reminder_id:
            reminder = r
            break
    
    if not reminder:
        print(f"Error: Reminder ID {reminder_id} not found")
        sys.exit(1)
    
    # 通知 OpenClaw（写入文件，由心跳发送）
    success = notify_openclaw(reminder["message"])
    
    if success:
        if advance_reminder is not None:
            updated = advance_reminder(reminder_id)
            if updated is None:
                print(f"[FAIL] Reminder advance failed: {reminder['message']}")
                sys.exit(1)
            if updated.get("status") == "pending":
                print(f"[OK] Reminder recurring, next at {updated['remind_at']}")
            else:
                print(f"[OK] Reminder processed: {reminder['message']}")
        else:
            # 标记为已发送
            for r in reminders:
                if r["id"] == reminder_id:
                    r["status"] = "sent"
                    break
            save_reminders(reminders)
            print(f"[OK] Reminder processed: {reminder['message']}")
    else:
        print(f"[FAIL] Reminder processing failed: {reminder['message']}")
        sys.exit(1)

if __name__ == "__main__":
    main()
