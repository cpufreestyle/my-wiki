#!/usr/bin/env python3
"""
Quick Reminder UI - 快速提醒设置界面 (Apple 风 · 浅色/深色)
统一设计系统：浅灰/深灰背景 / 白卡或深卡 / Apple 蓝强调
支持运行时切换浅色/深色，偏好写入 config/theme_pref.txt 与另一桌面 App 同步。
"""
import tkinter as tk
from tkinter import ttk
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reminder_manager import add_reminder, preset_reminders, load_reminders
from theme import (
    FONT, HINTS, get_tokens, load_theme_pref, save_theme_pref,
)


class PresetCard(tk.Frame):
    """白卡式预设按钮，绑定整卡点击（token 由外部传入以支持深色）"""

    def __init__(self, master, name, hint, on_click, T):
        super().__init__(master, bg=T["SURFACE"], highlightbackground=T["BORDER"], highlightthickness=1)
        self.T = T
        inner = tk.Frame(self, bg=T["SURFACE"])
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=14, pady=12)

        head = tk.Frame(inner, bg=T["SURFACE"])
        head.pack(fill=tk.X)
        tk.Label(head, text="●", fg=T["ACCENT"], bg=T["SURFACE"], font=(FONT, 9)).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(head, text=name, bg=T["SURFACE"], fg=T["TEXT"], font=(FONT, 14, "bold")).pack(side=tk.LEFT)
        tk.Label(inner, text=hint, bg=T["SURFACE"], fg=T["TEXT2"], font=(FONT, 11),
                 anchor="w").pack(fill=tk.X, padx=(18, 0), pady=(2, 0))

        cb = lambda e: on_click()
        self._bind_all(self, cb)

    def _bind_all(self, widget, cb):
        widget.bind("<Button-1>", cb)
        widget.config(cursor="hand2")
        for child in widget.winfo_children():
            self._bind_all(child, cb)


class ReminderUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MyWiki 快速提醒")
        self.root.geometry("420x660")
        self.root.option_add("*Font", (FONT, 13))
        self.mode = load_theme_pref()
        self.T = get_tokens(self.mode)
        self.root.configure(bg=self.T["BG"])
        self.build()

    # ---------- 主题切换 ----------
    def toggle_theme(self):
        self.mode = "dark" if self.mode == "light" else "light"
        save_theme_pref(self.mode)
        self.T = get_tokens(self.mode)
        self.root.configure(bg=self.T["BG"])
        self.build()

    # ---------- 构建界面 ----------
    def build(self):
        T = self.T
        for w in self.root.winfo_children():
            w.destroy()

        # Header（标题 + 主题切换）
        header = tk.Frame(self.root, bg=T["BG"])
        header.pack(pady=(24, 6))
        tk.Label(header, text="⏰", font=(FONT, 30), bg=T["BG"]).pack()
        tk.Label(header, text="快速提醒", font=(FONT, 21, "bold"), bg=T["BG"], fg=T["TEXT"]).pack(pady=(4, 0))
        sub = tk.Frame(header, bg=T["BG"])
        sub.pack(pady=(2, 0))
        tk.Label(sub, text="MyWiki · 一键设置常用提醒", font=(FONT, 12), bg=T["BG"], fg=T["TEXT2"]).pack(side=tk.LEFT)
        icon = "🌙" if self.mode == "light" else "☀️"
        tk.Button(sub, text=icon, command=self.toggle_theme, bg=T["SURFACE"], fg=T["TEXT"],
                  relief="flat", bd=1, font=(FONT, 14), cursor="hand2", width=2,
                  activebackground=T["BTN_HOVER"]).pack(side=tk.LEFT, padx=(10, 0))

        # 预设网格
        grid = tk.Frame(self.root, bg=T["BG"])
        grid.pack(padx=20, pady=(14, 0), fill="both", expand=True)
        self.presets = preset_reminders()
        for i, (name, t) in enumerate(self.presets.items()):
            card = PresetCard(grid, name, HINTS.get(name, ""),
                              lambda n=name, tt=t: self.set_reminder(n, tt), T)
            card.grid(row=i // 2, column=i % 2, padx=6, pady=6, sticky="nsew")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # 操作按钮
        actions = tk.Frame(self.root, bg=T["BG"])
        actions.pack(padx=20, pady=(14, 0), fill="x")
        tk.Button(actions, text="➕ 自定义提醒", bg=T["ORANGE"], fg="white", relief="flat", bd=0,
                  font=(FONT, 13, "bold"), activebackground=T["ORANGE_H"], cursor="hand2", height=2,
                  command=self.custom_reminder).pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 6))
        tk.Button(actions, text="📋 待发送", bg=T["GREEN"], fg="white", relief="flat", bd=0,
                  font=(FONT, 13, "bold"), activebackground=T["GREEN_H"], cursor="hand2", height=2,
                  command=self.view_pending).pack(side=tk.LEFT, fill="x", expand=True, padx=(6, 0))

        self.status = tk.Label(self.root, text="点击按钮设置提醒", font=(FONT, 11), bg=T["BG"], fg=T["TEXT2"])
        self.status.pack(pady=(16, 0))

    # ---------- 交互 ----------
    def set_reminder(self, name, remind_time):
        content = self.ask_content(f"设置提醒：{name}",
                                    f"时间：{remind_time.strftime('%Y-%m-%d %H:%M')}",
                                    "请输入提醒内容")
        if content:
            add_reminder(remind_time, content)
            self.status.config(text=f"已设置：{name}")
            self.toast(f"✅ 提醒已设置\n{name} · {remind_time.strftime('%Y-%m-%d %H:%M')}")

    def custom_reminder(self):
        T = self.T
        win = tk.Toplevel(self.root)
        win.title("自定义提醒")
        win.configure(bg=T["BG"])
        win.geometry("320x270")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="自定义提醒", font=(FONT, 16, "bold"), bg=T["BG"], fg=T["TEXT"]).pack(padx=20, pady=(18, 6), anchor="w")
        tk.Label(win, text="提醒时间 (YYYY-MM-DD HH:MM)", font=(FONT, 11), bg=T["BG"], fg=T["TEXT2"]).pack(padx=20, anchor="w")

        time_var = tk.StringVar(value=(datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"))
        ttk.Entry(win, textvariable=time_var, font=(FONT, 13)).pack(padx=20, fill="x", pady=(4, 10))

        tk.Label(win, text="提醒内容", font=(FONT, 11), bg=T["BG"], fg=T["TEXT2"]).pack(padx=20, anchor="w")
        msg_var = tk.StringVar()
        me = ttk.Entry(win, textvariable=msg_var, font=(FONT, 13))
        me.pack(padx=20, fill="x")
        me.focus_set()

        def ok():
            try:
                t = datetime.strptime(time_var.get().strip(), "%Y-%m-%d %H:%M")
            except ValueError:
                self.toast("时间格式错误"); return
            m = msg_var.get().strip()
            if not m:
                self.toast("请输入内容"); return
            add_reminder(t, m)
            self.status.config(text="已设置：自定义")
            win.destroy()
            self.toast(f"✅ 自定义提醒已设置\n{t.strftime('%Y-%m-%d %H:%M')}")

        def cancel():
            win.destroy()

        self._modal_buttons(win, cancel, ok)
        win.bind("<Return>", lambda e: ok())
        win.wait_window(win)

    def view_pending(self):
        T = self.T
        pending = load_reminders()[::-1][:20]
        win = tk.Toplevel(self.root)
        win.title("待发送提醒")
        win.configure(bg=T["BG"])
        win.geometry("340x440")
        win.transient(self.root)

        tk.Label(win, text="待发送提醒", font=(FONT, 16, "bold"), bg=T["BG"], fg=T["TEXT"]).pack(padx=20, pady=(18, 10), anchor="w")
        if not pending:
            tk.Label(win, text="当前没有待发送的提醒", font=(FONT, 13), bg=T["BG"], fg=T["TEXT2"]).pack(padx=20)
            return

        canvas = tk.Canvas(win, bg=T["BG"], highlightthickness=0)
        scroll = tk.Scrollbar(win, command=canvas.yview)
        inner = tk.Frame(canvas, bg=T["BG"])
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        for r in pending:
            card = tk.Frame(inner, bg=T["SURFACE"], highlightbackground=T["BORDER"], highlightthickness=1)
            card.pack(fill="x", padx=20, pady=5)
            tk.Label(card, text=r["remind_at"], font=(FONT, 12, "bold"), bg=T["SURFACE"], fg=T["ACCENT"]).pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(card, text=r["message"], font=(FONT, 13), bg=T["SURFACE"], fg=T["TEXT"],
                     wraplength=280, justify="left").pack(anchor="w", padx=14, pady=(0, 10))

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # ---------- 通用组件 ----------
    def ask_content(self, title, sub, placeholder):
        T = self.T
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=T["BG"])
        win.geometry("320x220")
        win.transient(self.root)
        win.grab_set()
        result = {"val": None}

        tk.Label(win, text=title, font=(FONT, 16, "bold"), bg=T["BG"], fg=T["TEXT"]).pack(padx=20, pady=(18, 2), anchor="w")
        tk.Label(win, text=sub, font=(FONT, 11), bg=T["BG"], fg=T["TEXT2"]).pack(padx=20, pady=(0, 12), anchor="w")
        var = tk.StringVar()
        entry = ttk.Entry(win, textvariable=var, font=(FONT, 13))
        entry.pack(padx=20, fill="x")
        entry.focus_set()

        def ok():
            result["val"] = var.get().strip()
            win.destroy()

        self._modal_buttons(win, win.destroy, ok)
        win.bind("<Return>", lambda e: ok())
        win.bind("<Escape>", lambda e: win.destroy())
        self.root.wait_window(win)
        return result["val"]

    def _modal_buttons(self, win, on_cancel, on_ok):
        T = self.T
        btns = tk.Frame(win, bg=T["BG"])
        btns.pack(padx=20, pady=(16, 18), fill="x")
        tk.Button(btns, text="取消", bg=T["SURFACE"], fg=T["TEXT"], relief="flat", bd=1,
                  font=(FONT, 13, "bold"), activebackground=T["BTN_HOVER"], command=on_cancel).pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 6))
        tk.Button(btns, text="确定", bg=T["ACCENT"], fg="white", relief="flat", bd=0,
                  font=(FONT, 13, "bold"), activebackground=T["ACCENT_H"], command=on_ok).pack(side=tk.LEFT, fill="x", expand=True, padx=(6, 0))

    def toast(self, msg):
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.configure(bg="#1D1D1F")
        tk.Label(t, text=msg, bg="#1D1D1F", fg="white", font=(FONT, 12), padx=16, pady=10).pack()
        t.update_idletasks()
        w, h = t.winfo_reqwidth(), t.winfo_reqheight()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + self.root.winfo_height() - 80
        t.geometry(f"{w}x{h}+{x}+{y}")
        t.after(2200, t.destroy)


def main():
    root = tk.Tk()
    app = ReminderUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
