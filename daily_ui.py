#!/usr/bin/env python3
"""
Quick Daily Note UI - 快速日记界面 (Apple 风 · 浅色/深色)
浮动窗口，快速记录每日想法。统一设计系统：浅灰/深灰背景 / 白卡或深卡 / Apple 蓝强调。
支持运行时切换浅色/深色，偏好写入 config/theme_pref.txt 与另一桌面 App 同步。
"""
import tkinter as tk
from tkinter import scrolledtext
import os
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DAILY_DIR = os.path.join(REPO_DIR, "daily")

# 统一设计 token 来自 theme.py（与 reminder_ui.py / 网页版共用一套值）
from theme import FONT, get_tokens, load_theme_pref, save_theme_pref


def get_today():
    return datetime.now().strftime("%Y-%m-%d")


def load_today_note():
    """加载今天的日记"""
    filename = os.path.join(DAILY_DIR, f"{get_today()}.md")
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    return f"# {get_today()} 日记\n\n"


# ---------- 模块级状态 ----------
mode = load_theme_pref()
tok = get_tokens(mode)
root = tk.Tk()
text_area: scrolledtext.ScrolledText | None = None
status: tk.Label | None = None


def save_note():
    """保存日记"""
    assert text_area is not None and status is not None
    T = tok
    content = text_area.get("1.0", tk.END).strip()
    filename = os.path.join(DAILY_DIR, f"{get_today()}.md")

    if not os.path.exists(DAILY_DIR):
        os.makedirs(DAILY_DIR)

    with open(filename, "w", encoding="utf-8") as f:
        _ = f.write(content)

    st = status
    _ = st.config(text=f"✓ 已保存 {get_today()}", fg=T["GREEN_H"])

    def _reset_status() -> None:
        _ = st.config(text="就绪", fg=T["TEXT2"])
    _ = root.after(2000, _reset_status)


def insert_template():
    """插入模板"""
    assert text_area is not None
    template = """
## 今天完成

- 

## 思考

- 

## 明日计划

- 
"""
    _ = text_area.insert(tk.END, template)


def toggle_theme():
    global mode, tok
    mode = "dark" if mode == "light" else "light"
    save_theme_pref(mode)
    tok = get_tokens(mode)
    build()


# ---------- 主窗口 ----------
def build():
    global text_area, status
    T = tok
    root.title(f"📓 日记 - {get_today()}")
    root.geometry("560x460")
    _ = root.attributes("-topmost", True)  # 总是置顶  # pyright: ignore[reportUnknownMemberType]
    _ = root.configure(bg=T["BG"])

    # 保留已输入的内容（切换主题时不丢失）
    existing = text_area.get("1.0", tk.END).strip() if text_area else ""
    if not existing:
        existing = load_today_note()

    for w in root.winfo_children():
        w.destroy()

    # 顶部栏
    top_frame = tk.Frame(root, bg=T["BG"])
    top_frame.pack(fill=tk.X, padx=16, pady=(14, 8))

    tk.Label(top_frame, text=f"📓 {get_today()}", font=(FONT, 16, "bold"),
             bg=T["BG"], fg=T["TEXT"]).pack(side=tk.LEFT)

    # 主题切换按钮（🌙/☀️）
    icon = "🌙" if mode == "light" else "☀️"
    tk.Button(top_frame, text=icon, command=toggle_theme, bg=T["SURFACE"], fg=T["TEXT"],
              relief="flat", bd=1, font=(FONT, 14), cursor="hand2", width=2,
              activebackground=T["BTN_HOVER"]).pack(side=tk.RIGHT, padx=(0, 8))
    tk.Button(top_frame, text="📝 模板", command=insert_template, bg=T["SURFACE"], fg=T["TEXT"],
              relief="flat", bd=1, font=(FONT, 12, "bold"), activebackground=T["BTN_HOVER"],
              cursor="hand2", padx=12).pack(side=tk.RIGHT)

    # 编辑区（卡片容器）
    editor_frame = tk.Frame(root, bg=T["SURFACE"], highlightbackground=T["BORDER"], highlightthickness=1)
    editor_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

    text_area = scrolledtext.ScrolledText(
        editor_frame, font=(FONT, 13), bg=T["SURFACE"], fg=T["TEXT"], insertbackground=T["TEXT"],
        relief="flat", bd=0, wrap=tk.WORD, padx=14, pady=14
    )
    text_area.pack(fill=tk.BOTH, expand=True)
    text_area.insert("1.0", existing)

    # 底部栏
    bottom_frame = tk.Frame(root, bg=T["BG"])
    bottom_frame.pack(fill=tk.X, padx=16, pady=(0, 12))

    status = tk.Label(bottom_frame, text="就绪", font=(FONT, 11), bg=T["BG"], fg=T["TEXT2"])
    status.pack(side=tk.LEFT)

    tk.Button(bottom_frame, text="💾 保存", command=save_note, bg=T["ACCENT"], fg="white",
              relief="flat", bd=0, font=(FONT, 12, "bold"), activebackground=T["ACCENT_H"],
              cursor="hand2", padx=18, pady=6).pack(side=tk.RIGHT)


# Ctrl+S 保存快捷键
_ = root.bind("<Control-s>", lambda e: save_note())
_ = root.bind("<Control-S>", lambda e: save_note())

build()

if __name__ == "__main__":
    root.mainloop()
