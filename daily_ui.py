#!/usr/bin/env python3
"""
Quick Daily Note UI - 快速日记界面
浮动窗口，快速记录每日想法
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import os
from datetime import datetime

WIKI_DIR = r"D:\Users\michael\MyWiki"
DAILY_DIR = os.path.join(WIKI_DIR, "daily")

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def load_today_note():
    """加载今天的日记"""
    filename = f"{DAILY_DIR}/{get_today()}.md"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    return f"# {get_today()} 日记\n\n"

def save_note():
    """保存日记"""
    content = text_area.get("1.0", tk.END).strip()
    filename = f"{DAILY_DIR}/{get_today()}.md"
    
    # 确保日期文件夹存在
    if not os.path.exists(DAILY_DIR):
        os.makedirs(DAILY_DIR)
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    
    status_label.config(text=f"✓ 已保存 {get_today()}", fg="#4CAF50")
    root.after(2000, lambda: status_label.config(text="就绪", fg="gray"))

def insert_template():
    """插入模板"""
    template = """
## 今天完成

- 

## 思考

- 

## 明日计划

- 
"""
    text_area.insert(tk.END, template)

# 创建主窗口
root = tk.Tk()
root.title(f"📓 日记 - {get_today()}")
root.geometry("600x500")
root.attributes("-topmost", True)  # 总是置顶

# 主题色
bg_color = "#1e1e1e"
fg_color = "#d4d4d4"
accent_color = "#569cd6"

root.configure(bg=bg_color)

# 顶部栏
top_frame = tk.Frame(root, bg=bg_color)
top_frame.pack(fill=tk.X, padx=10, pady=10)

title_label = tk.Label(top_frame, text=f"📅 {get_today()}", font=("Segoe UI", 14, "bold"), 
                     bg=bg_color, fg=fg_color)
title_label.pack(side=tk.LEFT)

template_btn = tk.Button(top_frame, text="📝 模板", command=insert_template,
                    bg="#333", fg=fg_color, relief=tk.FLAT, padx=10)
template_btn.pack(side=tk.RIGHT)

# 文本区域
text_area = scrolledtext.ScrolledText(root, font=("Consolas", 12), 
                                       bg=bg_color, fg=fg_color,
                                       insertbackground=fg_color,
                                       wrap=tk.WORD)
text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

# 加载今天内容
text_area.insert("1.0", load_today_note())

# 底部栏
bottom_frame = tk.Frame(root, bg=bg_color)
bottom_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

save_btn = tk.Button(bottom_frame, text="💾 保存", command=save_note,
                   bg=accent_color, fg="white", relief=tk.FLAT, padx=20, pady=5)
save_btn.pack(side=tk.RIGHT)

status_label = tk.Label(bottom_frame, text="就绪", font=("Segoe UI", 9),
                       bg=bg_color, fg="gray")
status_label.pack(side=tk.LEFT)

# Ctrl+S 保存快捷键
root.bind("<Control-s>", lambda e: save_note())
root.bind("<Control-S>", lambda e: save_note())

if __name__ == "__main__":
    root.mainloop()