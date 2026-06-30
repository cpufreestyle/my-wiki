#!/usr/bin/env python3
"""
Quick Reminder UI - 快速提醒设置界面
一键设置常用提醒时间
"""
import tkinter as tk
from tkinter import messagebox, simpledialog
import sys
import os

# 添加wiki目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reminder_manager import add_reminder, preset_reminders, load_reminders

class ReminderUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Quick Reminder - 快速提醒")
        self.root.geometry("400x500")
        self.root.configure(bg="#2b2b2b")
        
        # 标题
        title = tk.Label(
            root,
            text="⏰ 快速提醒设置",
            font=("Arial", 16, "bold"),
            bg="#2b2b2b",
            fg="#ffffff"
        )
        title.pack(pady=20)
        
        # 预设按钮区域
        btn_frame = tk.Frame(root, bg="#2b2b2b")
        btn_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.presets = preset_reminders()
        
        # 创建预设按钮
        for i, (name, time) in enumerate(self.presets.items()):
            btn = tk.Button(
                btn_frame,
                text=f"{name}\n({time.strftime('%m-%d %H:%M')})",
                font=("Arial", 11),
                bg="#4a9eff",
                fg="#ffffff",
                activebackground="#357abd",
                activeforeground="#ffffff",
                relief="flat",
                cursor="hand2",
                height=2,
                command=lambda n=name, t=time: self.set_reminder(n, t)
            )
            btn.pack(fill="x", pady=5)
        
        # 自定义提醒按钮
        custom_btn = tk.Button(
            btn_frame,
            text="➕ 自定义提醒",
            font=("Arial", 11),
            bg="#f0ad4e",
            fg="#ffffff",
            activebackground="#ec971f",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            height=2,
            command=self.custom_reminder
        )
        custom_btn.pack(fill="x", pady=10)
        
        # 查看待发送提醒按钮
        view_btn = tk.Button(
            btn_frame,
            text="📋 查看待发送提醒",
            font=("Arial", 11),
            bg="#5cb85c",
            fg="#ffffff",
            activebackground="#4cae4c",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            height=2,
            command=self.view_pending
        )
        view_btn.pack(fill="x", pady=5)
        
        # 状态栏
        self.status_label = tk.Label(
            root,
            text="点击按钮设置提醒",
            font=("Arial", 9),
            bg="#2b2b2b",
            fg="#888888"
        )
        self.status_label.pack(pady=10)
    
    def set_reminder(self, name, remind_time):
        """设置预设提醒"""
        message = simpledialog.askstring(
            "提醒内容",
            f"设置提醒：{name}\n时间：{remind_time.strftime('%Y-%m-%d %H:%M')}\n\n请输入提醒内容：",
            parent=self.root
        )
        
        if message and message.strip():
            reminder = add_reminder(remind_time, message.strip())
            messagebox.showinfo(
                "提醒已设置",
                f"✅ 提醒已设置！\n\n时间：{remind_time.strftime('%Y-%m-%d %H:%M')}\n内容：{message}",
                parent=self.root
            )
            self.status_label.config(text=f"已设置：{name}")
    
    def custom_reminder(self):
        """自定义提醒"""
        messagebox.showinfo(
            "自定义提醒",
            "自定义提醒功能开发中...\n\n暂时请使用预设按钮",
            parent=self.root
        )
    
    def view_pending(self):
        """查看待发送提醒"""
        pending = load_reminders()
        if not pending:
            messagebox.showinfo("待发送提醒", "当前没有待发送的提醒", parent=self.root)
            return
        
        text = "待发送提醒：\n\n"
        for r in pending[-10:]:  # 只显示最近10条
            text += f"[{r['id']}] {r['remind_at']}\n"
            text += f"    {r['message']}\n\n"
        
        messagebox.showinfo("待发送提醒", text, parent=self.root)

def main():
    root = tk.Tk()
    app = ReminderUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
