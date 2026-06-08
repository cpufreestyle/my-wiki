#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
My Wiki - 桌面知识管理系统
基于 Tkinter 的单文件主程序
"""
import os
import sys
import json
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime, date
from pathlib import Path

# ===== 导入本地模块 =====
try:
    from config import *
    from wiki_tool import update_index, read_daily, write_daily, analyze_with_llm, run_script
    from mood_analyzer import analyze_mood, save_mood, get_recent_moods
    from tag_extractor import extract_all
    from reminder_manager import add_reminder, load_reminders, remove_reminder, done_reminder
except ImportError as e:
    print(f"模块导入错误: {e}")
    sys.exit(1)

# ===== 主题颜色 =====
THEME = {
    "bg":        "#1e1e1e",
    "bg2":       "#252526",
    "bg3":       "#2d2d30",
    "fg":        "#cccccc",
    "fg2":       "#9d9d9d",
    "accent":    "#569cd6",
    "accent2":   "#4ec9b0",
    "green":     "#6a9955",
    "orange":    "#ce9178",
    "btn_bg":    "#333333",
    "btn_hl":    "#3c3c3c",
    "border":    "#3c3c3c",
}

# ===== 主应用 =====
class MyWikiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("My Wiki - 个人知识管理")
        self.root.geometry("1000x700")
        self.root.configure(bg=THEME["bg"])
        
        self._setup_style()
        self._build_ui()
        self._load_index()
        
        # 检查 Obsidian
        if OBSIDIAN_PATH:
            self.status(f"✅ Obsidian 已配置")
        else:
            self.status("⚠️ 未检测到 Obsidian，请安装后配置")
    
    def _setup_style(self):
        """配置 ttk 样式"""
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure("TFrame", background=THEME["bg"])
        style.configure("Card.TFrame", background=THEME["bg2"])
        style.configure("TLabelframe", background=THEME["bg"], foreground=THEME["fg"])
        style.configure("TLabelframe.Label", background=THEME["bg"], foreground=THEME["fg"])
        
        style.configure("TLabel", background=THEME["bg"], foreground=THEME["fg"])
        style.configure("Title.TLabel", background=THEME["bg"], foreground=THEME["accent"],
                       font=("Segoe UI", 14, "bold"))
        style.configure("Sub.TLabel", background=THEME["bg"], foreground=THEME["fg2"])
        
        style.configure("TButton", background=THEME["btn_bg"], foreground=THEME["fg"],
                       bordercolor=THEME["border"], lightcolor=THEME["btn_bg"],
                       darkcolor=THEME["btn_bg"])
        style.map("TButton", background=[("active", THEME["btn_hl"])])
        
        style.configure("TEntry", fieldbackground=THEME["bg2"], foreground=THEME["fg"],
                       bordercolor=THEME["border"])
        style.configure("TText", background=THEME["bg2"], foreground=THEME["fg"])
    
    def _build_ui(self):
        """构建 UI"""
        # 顶部标题栏
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        ttk.Label(header, text="📚 My Wiki", style="Title.TLabel").pack(side=tk.LEFT)
        
        self.status_label = ttk.Label(header, text="就绪", style="Sub.TLabel")
        self.status_label.pack(side=tk.RIGHT)
        
        # 主布局：左侧边栏 + 右侧内容
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 左侧边栏
        sidebar = ttk.Frame(main, width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        sidebar.pack_propagate(False)
        
        self._build_sidebar(sidebar)
        
        # 右侧内容
        self.content = ttk.Frame(main)
        self.content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 启动日记视图
        self._show_daily()
    
    def _build_sidebar(self, parent):
        """构建侧边栏"""
        nav_items = [
            ("📝 写日记",     self._show_daily),
            ("🗓️ 索引",       self._show_index),
            ("💭 心情",       self._show_mood),
            ("🏷️ 标签",       self._show_tags),
            ("⏰ 提醒",       self._show_reminders),
            ("🔧 工具",       self._show_tools),
            ("🔄 同步",       self._sync_files),
        ]
        
        for i, (label, cmd) in enumerate(nav_items):
            btn = tk.Button(parent, text=label, font=("Segoe UI", 10),
                           bg=THEME["btn_bg"], fg=THEME["fg"],
                           activebackground=THEME["btn_hl"], activeforeground=THEME["fg"],
                           relief=tk.FLAT, bd=0, pady=8,
                           anchor="w", padx=15, command=cmd)
            btn.pack(fill=tk.X, pady=1)
        
        # 底部：Obsidian 按钮
        tk.Frame(parent, height=20).pack()
        obs_btn = tk.Button(parent, text="🔍 打开 Obsidian",
                          font=("Segoe UI", 9), bg=THEME["bg2"], fg=THEME["fg2"],
                          relief=tk.FLAT, bd=0, pady=5, command=self._open_obsidian)
        obs_btn.pack(fill=tk.X, padx=5, pady=5)
    
    def _clear_content(self):
        """清空右侧内容区"""
        for widget in self.content.winfo_children():
            widget.destroy()
    
    def _show_daily(self):
        """日记视图"""
        self._clear_content()
        
        frame = ttk.Frame(self.content)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 日期导航
        nav = ttk.Frame(frame)
        nav.pack(fill=tk.X, pady=(0, 5))
        
        self.date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        ttk.Entry(nav, textvariable=self.date_var, width=12).pack(side=tk.LEFT)
        
        ttk.Button(nav, text="◀ 前一天", command=self._prev_day).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav, text="今天", command=self._go_today).pack(side=tk.LEFT)
        ttk.Button(nav, text="后一天 ▶", command=self._next_day).pack(side=tk.LEFT, padx=5)
        
        # 编辑器
        self.editor = scrolledtext.ScrolledText(frame, wrap=tk.WORD,
            bg=THEME["bg2"], fg=THEME["fg"], insertbackground=THEME["accent"],
            font=("Consolas", 11), relief=tk.FLAT, padx=10, pady=10)
        self.editor.pack(fill=tk.BOTH, expand=True)
        
        # 操作栏
        ops = ttk.Frame(frame)
        ops.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(ops, text="💾 保存", command=self._save_daily).pack(side=tk.LEFT, padx=3)
        ttk.Button(ops, text="🏷️ 提取标签", command=self._extract_tags).pack(side=tk.LEFT, padx=3)
        ttk.Button(ops, text="🤖 LLM 分析", command=self._analyze_llm).pack(side=tk.LEFT, padx=3)
        ttk.Button(ops, text="💭 心情", command=self._save_mood).pack(side=tk.LEFT, padx=3)
        
        self.tag_label = ttk.Label(ops, text="", style="Sub.TLabel")
        self.tag_label.pack(side=tk.RIGHT)
        
        self._load_daily()
    
    def _show_index(self):
        """索引视图"""
        self._clear_content()
        
        frame = ttk.Frame(self.content)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="📋 索引", style="Title.TLabel").pack(pady=5)
        
        # 工具栏
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, padx=5)
        ttk.Button(toolbar, text="🔄 刷新", command=self._load_index).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📁 打开目录", command=self._open_dir).pack(side=tk.LEFT, padx=3)
        
        self.index_tree = ttk.Treeview(frame, columns=("日期", "摘要"), show="tree headings")
        self.index_tree.heading("#0", text="标题")
        self.index_tree.heading("日期", text="日期")
        self.index_tree.heading("摘要", text="摘要")
        self.index_tree.column("#0", width=300)
        self.index_tree.column("日期", width=100)
        self.index_tree.column("摘要", width=400)
        
        scroll = ttk.Scrollbar(frame, command=self.index_tree.yview)
        self.index_tree.configure(yscrollcommand=scroll.set)
        self.index_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        self._load_index()
    
    def _show_mood(self):
        """心情视图"""
        self._clear_content()
        
        frame = ttk.Frame(self.content)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="💭 心情趋势", style="Title.TLabel").pack(pady=5)
        
        moods = get_recent_moods(14)
        
        if moods:
            canvas = tk.Canvas(frame, bg=THEME["bg"], height=200, highlightthickness=0)
            canvas.pack(fill=tk.X, padx=10, pady=10)
            
            w = 600
            h = 150
            step = w / max(len(moods) - 1, 1)
            
            points_pos = [0, 0.3, 0.6, 1.0]
            points_neg = [1.0, 0.7, 0.4, 0.0]
            
            for i, m in enumerate(moods):
                x = i * step
                mood = m.get("mood", "neutral")
                conf = m.get("confidence", 0.5)
                
                if mood == "positive":
                    y = h - conf * h
                    color = "#6a9955"
                elif mood == "negative":
                    y = conf * h
                    color = "#ce9178"
                else:
                    y = h / 2
                    color = "#569cd6"
                
                canvas.create_oval(x-5, y-5, x+5, y+5, fill=color, outline="")
                canvas.create_text(x, y-15, text=m.get("date", "")[-5:], 
                                 fill=THEME["fg2"], font=("Segoe UI", 8))
        else:
            ttk.Label(frame, text="暂无心情记录，写日记时选择心情即可自动保存",
                     style="Sub.TLabel").pack(pady=30)
    
    def _show_tags(self):
        """标签视图"""
        self._clear_content()
        
        frame = ttk.Frame(self.content)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="🏷️ 标签浏览器", style="Title.TLabel").pack(pady=5)
        
        # 分析所有日记
        all_text = ""
        for f in DAILY_DIR.glob("*.md"):
            all_text += f.read_text(encoding='utf-8-sig') + "\n"
        
        result = extract_all(all_text)
        
        # 显示标签云
        tags_frame = ttk.Frame(frame)
        tags_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        ttk.Label(tags_frame, text=f"发现 {len(result['all'])} 个标签：",
                 style="Sub.TLabel").pack(anchor="w")
        
        tags_text = tk.Text(tags_frame, bg=THEME["bg"], fg=THEME["fg"],
                           font=("Segoe UI", 11), relief=tk.FLAT, wrap=tk.WORD)
        tags_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        for tag in result['all']:
            tags_text.insert(tk.END, f"#{tag}  ", "")
        
        ttk.Label(tags_frame, text=f"领域标签: {', '.join(result['domains'])}",
                 style="Sub.TLabel").pack(anchor="w", pady=5)
    
    def _show_reminders(self):
        """提醒视图"""
        self._clear_content()
        
        frame = ttk.Frame(self.content)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题 + 添加按钮
        header = ttk.Frame(frame)
        header.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(header, text="⏰ 提醒管理", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="+ 新提醒", command=self._add_reminder).pack(side=tk.RIGHT)
        
        # 提醒列表
        cols = ("时间", "标题", "状态")
        tree = ttk.Treeview(frame, columns=cols, show="")
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=150 if col != "标题" else 300)
        
        reminders = load_reminders()
        for r in reminders:
            if r.get("done"):
                continue
            dt = datetime.fromisoformat(r["remind_at"])
            status = "🔁 每日" if r.get("repeat") == "daily" else "⏱️ 一次性"
            tree.insert("", tk.END, values=(
                dt.strftime("%Y-%m-%d %H:%M"),
                r["title"],
                status
            ))
        
        tree.pack(fill=tk.BOTH, expand=True, padx=5)
    
    def _show_tools(self):
        """工具视图"""
        self._clear_content()
        
        frame = ttk.Frame(self.content)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="🔧 工具箱", style="Title.TLabel").pack(pady=5)
        
        tools = [
            ("🔄 刷新索引",    "更新 INDEX.md"),
            ("📊 知识图谱",   "查看知识图谱数据"),
            ("📖 打开目录",   "打开日记目录"),
            ("💻 终端工具",   "运行 scripts/ 下的脚本"),
        ]
        
        for label, desc in tools:
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, padx=20, pady=5)
            tk.Button(row, text=label, font=("Segoe UI", 10),
                     bg=THEME["btn_bg"], fg=THEME["fg"],
                     relief=tk.FLAT, padx=10, pady=5,
                     anchor="w", command=lambda l=label: self._run_tool(l)).pack(side=tk.LEFT)
            ttk.Label(row, text=desc, style="Sub.TLabel").pack(side=tk.LEFT, padx=10)
    
    # ===== 操作方法 =====
    
    def _load_daily(self):
        """加载日记内容"""
        date_str = self.date_var.get()
        content = read_daily(date_str)
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", content)
    
    def _save_daily(self):
        """保存日记"""
        content = self.editor.get("1.0", tk.END).rstrip()
        date_str = self.date_var.get()
        write_daily(content, date_str)
        self.status(f"✅ 已保存 {date_str}.md")
    
    def _prev_day(self):
        d = datetime.strptime(self.date_var.get(), "%Y-%m-%d")
        d -= __import__('datetime').timedelta(days=1)
        self.date_var.set(d.strftime("%Y-%m-%d"))
        self._load_daily()
    
    def _next_day(self):
        d = datetime.strptime(self.date_var.get(), "%Y-%m-%d")
        d += __import__('datetime').timedelta(days=1)
        self.date_var.set(d.strftime("%Y-%m-%d"))
        self._load_daily()
    
    def _go_today(self):
        self.date_var.set(date.today().strftime("%Y-%m-%d"))
        self._load_daily()
    
    def _extract_tags(self):
        """提取当前日记的标签"""
        text = self.editor.get("1.0", tk.END)
        result = extract_all(text)
        tags_str = " | ".join(result['all'])
        self.tag_label.config(text=f"🏷️ {tags_str}")
    
    def _analyze_llm(self):
        """LLM 分析"""
        text = self.editor.get("1.0", tk.END)
        if len(text.strip()) < 20:
            self.status("⚠️ 内容太少")
            return
        
        self.status("🤖 LLM 分析中...")
        self.root.update()
        
        result = analyze_with_llm(text)
        
        # 弹窗显示结果
        popup = tk.Toplevel(self.root)
        popup.title("🤖 LLM 分析结果")
        popup.geometry("600x400")
        popup.configure(bg=THEME["bg"])
        
        txt = scrolledtext.ScrolledText(popup, bg=THEME["bg2"], fg=THEME["fg"],
                                        font=("Consolas", 11), relief=tk.FLAT, padx=10)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert("1.0", result)
        
        self.status("✅ 分析完成")
    
    def _save_mood(self):
        """保存心情"""
        text = self.editor.get("1.0", tk.END)
        mood, conf, _ = analyze_mood(text)
        date_str = self.date_var.get()
        save_mood(date_str, mood, conf)
        emoji = {"positive": "😊", "negative": "😔", "neutral": "😐"}.get(mood, "❓")
        self.status(f"💭 心情已保存: {emoji} {mood} ({conf:.0%})")
    
    def _load_index(self):
        """加载索引"""
        if hasattr(self, 'index_tree'):
            self.index_tree.delete(*self.index_tree.get_children())
            
            daily_files = sorted(DAILY_DIR.glob("*.md"), reverse=True)[:50]
            for f in daily_files:
                try:
                    content = f.read_text(encoding='utf-8-sig')
                    m = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                    title = m.group(1) if m else "无标题"
                    date_str = f.stem
                    
                    self.index_tree.insert("", tk.END, text=title,
                                          values=(date_str, content[:100].replace('\n', ' ')))
                except Exception:
                    pass
    
    def _sync_files(self):
        """同步文件（刷新索引 + 统计）"""
        count = update_index()
        self.status(f"🔄 索引已更新 ({count} 篇日记)")
    
    def _open_dir(self):
        """打开日记目录"""
        import subprocess
        subprocess.Popen(["explorer", str(DAILY_DIR)])
    
    def _open_obsidian(self):
        """打开 Obsidian"""
        if OBSIDIAN_PATH:
            import subprocess
            subprocess.Popen([OBSIDIAN_PATH, str(WIKI_DIR)])
        else:
            messagebox.showwarning("未找到 Obsidian", "请先安装 Obsidian")
    
    def _add_reminder(self):
        """添加提醒弹窗"""
        popup = tk.Toplevel(self.root)
        popup.title("新提醒")
        popup.geometry("400x200")
        popup.configure(bg=THEME["bg"])
        
        ttk.Label(popup, text="标题：").pack(anchor="w", padx=20, pady=(20,0))
        title_entry = ttk.Entry(popup, width=40)
        title_entry.pack(padx=20)
        
        ttk.Label(popup, text="时间 (YYYY-MM-DD HH:MM)：").pack(anchor="w", padx=20, pady=(10,0))
        time_entry = ttk.Entry(popup, width=40)
        time_entry.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M"))
        time_entry.pack(padx=20)
        
        def do_add():
            title = title_entry.get()
            time_str = time_entry.get()
            try:
                dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                add_reminder(title, title, dt.isoformat())
                self.status(f"✅ 提醒已添加: {title}")
                popup.destroy()
            except ValueError:
                messagebox.showerror("错误", "时间格式不对")
        
        ttk.Button(popup, text="添加", command=do_add).pack(pady=20)
    
    def _run_tool(self, label):
        """运行工具"""
        if "刷新索引" in label:
            self._sync_files()
        elif "打开目录" in label:
            self._open_dir()
        elif "知识图谱" in label:
            graph = __import__('wiki_tool').load_knowledge_graph()
            count = len(graph.get("nodes", []))
            self.status(f"📊 知识图谱: {count} 个节点")
        elif "终端工具" in label:
            self.status("💻 请使用命令行: python wiki_tool.py")
    
    def status(self, msg):
        """更新状态栏"""
        self.status_label.config(text=msg)

# ===== 入口 =====
if __name__ == "__main__":
    root = tk.Tk()
    app = MyWikiApp(root)
    root.mainloop()
