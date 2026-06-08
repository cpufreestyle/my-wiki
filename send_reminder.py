#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
My Wiki v2.0 - 提醒发送脚本
被 Windows 任务计划调用，发送到期提醒通知
用法: python send_reminder.py <reminder_id>
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reminder_manager import check_and_notify, load_reminders

def main():
    if len(sys.argv) < 2:
        print("用法: python send_reminder.py <reminder_id>")
        sys.exit(1)
    
    reminder_id = sys.argv[1]
    
    # 检查并发送通知
    check_and_notify()
    
    # 标记完成
    from reminder_manager import done_reminder
    done_reminder(reminder_id)
    print(f"[OK] 提醒 {reminder_id} 已处理")

if __name__ == "__main__":
    main()
