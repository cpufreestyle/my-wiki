#!/usr/bin/env python3
"""
My Wiki - All-in-One Personal Knowledge Tool
日记 | 心情 | 提醒 | 标签
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import os
import subprocess
import sys
import re
import shutil
import urllib.request
import tempfile
from datetime import datetime, timedelta
from collections import Counter

# ==================== DEPENDENCY CHECK ====================
def check_obsidian():
    """Check if Obsidian is installed / 检测 Obsidian 是否安装"""
    # Check common install paths
    paths = [
        r"C:\Users\{}\AppData\Local\Obsidian\Obsidian.exe".format(os.getenv("USERNAME")),
        r"C:\Program Files\Obsidian\Obsidian.exe",
        r"C:\Program Files (x86)\Obsidian\Obsidian.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return True, p
    # Check registry
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Obsidian")
        path, _ = winreg.QueryValueEx(key, "InstallLocation")
        winreg.CloseKey(key)
        if path and os.path.exists(path):
            return True, os.path.join(path, "Obsidian.exe")
    except Exception:
        pass
    return False, None

def check_openclaw():
    """Check if OpenClaw is installed / 检测 OpenClaw 是否安装"""
    # Check if openclaw CLI exists
    try:
        result = subprocess.run(["openclaw", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, result.stdout.strip()
    except Exception:
        pass
    # Check common install paths
    paths = [
        r"C:\Users\{}\AppData\Local\Programs\openclaw\openclaw.exe".format(os.getenv("USERNAME")),
        r"C:\Program Files\QClaw\openclaw.exe",
        r"C:\Program Files (x86)\QClaw\openclaw.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return True, p
    return False, None

def download_file(url, dest):
    """Download file / 下载文件 (blocking, simple)"""
    import urllib.request
    # Use a simple download - progress bar is indeterminate
    urllib.request.urlretrieve(url, dest)

def install_obsidian(parent_window):
    """Download and install Obsidian / 下载并安装 Obsidian"""
    url = "https://github.com/obsidianmd/obsidian-releases/releases/download/v1.8.10/Obsidian-1.8.10.exe"
    tmp = tempfile.gettempdir()
    installer = os.path.join(tmp, "Obsidian-setup.exe")
    
    # Show download dialog / 显示下载对话框
    dlg = tk.Toplevel(parent_window)
    dlg.title("Downloading Obsidian / 下载 Obsidian")
    dlg.geometry("400x120")
    dlg.configure(bg=BG)
    dlg.transient(parent_window)
    dlg.grab_set()
    
    tk.Label(dlg, text="Downloading Obsidian installer...\n正在下载 Obsidian 安装包...", 
             bg=BG, fg=FG, font=("Segoe UI", 10)).pack(pady=15)
    progress = ttk.Progressbar(dlg, mode="indeterminate")
    progress.pack(fill="x", padx=30, pady=5)
    progress.start()
    dlg.update()
    
    try:
        download_file(url, installer)
        progress.stop()
        dlg.destroy()
        
        # Run installer silently / 静默安装
        result = subprocess.run([installer, "/SILENT", "/ALLUSERS"], timeout=300)
        os.remove(installer)
        return result.returncode == 0
    except Exception as e:
        progress.stop()
        dlg.destroy()
        messagebox.showerror("Error / 错误", "Failed to download Obsidian:\n{}".format(e))
        return False

def install_openclaw(parent_window):
    """Install OpenClaw via npm / 通过 npm 安装 OpenClaw"""
    try:
        # Check if npm exists
        subprocess.run(["npm", "--version"], capture_output=True, check=True, timeout=5)
    except Exception:
        messagebox.showerror("Error / 错误", 
            "npm not found. Please install Node.js first:\n"
            "npm 未找到，请先安装 Node.js：\nhttps://nodejs.org")
        return False
    
    dlg = tk.Toplevel(parent_window)
    dlg.title("Installing OpenClaw / 安装 OpenClaw")
    dlg.geometry("450x120")
    dlg.configure(bg=BG)
    dlg.transient(parent_window)
    dlg.grab_set()
    
    tk.Label(dlg, text="Installing OpenClaw globally...\n正在全局安装 OpenClaw...", 
             bg=BG, fg=FG, font=("Segoe UI", 10)).pack(pady=15)
    progress = ttk.Progressbar(dlg, mode="indeterminate")
    progress.pack(fill="x", padx=30, pady=5)
    progress.start()
    dlg.update()
    
    try:
        result = subprocess.run(["npm", "install", "-g", "openclaw"], 
                               capture_output=True, text=True, timeout=300)
        progress.stop()
        dlg.destroy()
        if result.returncode == 0:
            messagebox.showinfo("Success / 成功", "OpenClaw installed successfully!\nOpenClaw 安装成功！")
            return True
        else:
            messagebox.showerror("Error / 错误", "npm install failed:\n{}".format(result.stderr))
            return False
    except Exception as e:
        progress.stop()
        dlg.destroy()
        messagebox.showerror("Error / 错误", "Failed to install OpenClaw:\n{}".format(e))
        return False

def show_welcome_and_check():
    """Show welcome window and check dependencies / 显示欢迎窗口并检查依赖"""
    root = tk.Tk()
    root.title("MyWiki - First Run Setup / 首次运行设置")
    root.geometry("520x420")
    root.configure(bg=BG)
    root.resizable(False, False)
    
    # Icon
    if os.path.exists(ICON_PATH):
        try:
            root.iconbitmap(ICON_PATH)
        except Exception:
            pass
    
    # Title
    tk.Label(root, text="📝 MyWiki", bg=BG, fg=ACCENT, font=("Segoe UI", 20, "bold")).pack(pady=(25, 5))
    tk.Label(root, text="Personal Knowledge & Diary Manager\n个人知识库与日记管理工具", 
             bg=BG, fg=FG, font=("Segoe UI", 10)).pack()
    
    tk.Frame(root, height=2, bg=ACCENT).pack(fill="x", padx=40, pady=15)
    
    # Check status
    obsidian_ok, obsidian_path = check_obsidian()
    openclaw_ok, openclaw_ver = check_openclaw()
    
    status_frame = tk.Frame(root, bg=BG)
    status_frame.pack(pady=5)
    
    tk.Label(status_frame, text="System Check / 系统检测", bg=BG, fg=FG, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=30)
    
    def make_status(parent, label, ok):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", padx=30, pady=4)
        emoji = "✅" if ok else "❌"
        color = "#4ec9b0" if ok else "#f48771"
        tk.Label(f, text="{} {}".format(emoji, label), bg=BG, fg=color, font=("Segoe UI", 10), anchor="w").pack(side="left")
        return f
    
    make_status(status_frame, "Obsidian (知识库)", obsidian_ok)
    make_status(status_frame, "OpenClaw (AI 助手)", openclaw_ok)
    
    tk.Frame(root, height=2, bg=ACCENT).pack(fill="x", padx=40, pady=10)
    
    btn_frame = tk.Frame(root, bg=BG)
    btn_frame.pack(pady=10)
    
    proceed = tk.BooleanVar(value=False)
    
    def on_install_obsidian():
        if install_obsidian(root):
            messagebox.showinfo("Done / 完成", "Obsidian installed. Please restart MyWiki.\nObsidian 已安装，请重启 MyWiki。")
            root.quit()
    
    def on_install_openclaw():
        if install_openclaw(root):
            messagebox.showinfo("Done / 完成", "OpenClaw installed. Please restart MyWiki.\nOpenClaw 已安装，请重启 MyWiki。")
            root.quit()
    
    def on_proceed():
        proceed.set(True)
        root.quit()
    
    def on_exit():
        proceed.set(False)
        root.quit()
    
    if not obsidian_ok:
        tk.Button(btn_frame, text="Install Obsidian / 安装 Obsidian", 
                  command=on_install_obsidian,
                  bg=ACCENT, fg="white", font=("Segoe UI", 10), relief="flat", padx=15, pady=5).pack(pady=3)
    
    if not openclaw_ok:
        tk.Button(btn_frame, text="Install OpenClaw / 安装 OpenClaw", 
                  command=on_install_openclaw,
                  bg=ACCENT, fg="white", font=("Segoe UI", 10), relief="flat", padx=15, pady=5).pack(pady=3)
    
    btn_row = tk.Frame(btn_frame, bg=BG)
    btn_row.pack(pady=(10, 0))
    
    label = "Continue / 继续" if (obsidian_ok and openclaw_ok) else "Skip & Continue / 跳过并继续"
    tk.Button(btn_row, text=label, command=on_proceed,
              bg="#4ec9b0", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", padx=20, pady=6).pack(side="left", padx=5)
    tk.Button(btn_row, text="Exit / 退出", command=on_exit,
              bg="#333333", fg=FG, font=("Segoe UI", 10), relief="flat", padx=20, pady=6).pack(side="left", padx=5)
    
    tk.Label(root, text="Tips: Obsidian & OpenClaw are optional.\n提示：Obsidian 和 OpenClaw 是可选的，MyWiki 可独立运行。", 
             bg=BG, fg="#666666", font=("Segoe UI", 8)).pack(pady=(10, 5))
    
    root.mainloop()
    return proceed.get()

# ==================== PATHS ====================
WIKI_DIR = r"D:\Users\michael\MyWiki"
ICON_PATH = os.path.join(WIKI_DIR, "icon.ico")
DAILY_DIR = os.path.join(WIKI_DIR, "daily")
MOOD_DIR = os.path.join(WIKI_DIR, "mood")
REMINDER_DIR = os.path.join(WIKI_DIR, "reminders")
REMINDER_FILE = os.path.join(REMINDER_DIR, "reminders.json")
PENDING_FILE = os.path.join(REMINDER_DIR, "pending_notifications.json")

# ==================== THEME ====================
BG = "#1e1e1e"
BG2 = "#252526"
FG = "#d4d4d4"
ACCENT = "#569cd6"
ACCENT2 = "#4ec9b0"
BTN_BG = "#333333"
BTN_ACTIVE = "#3c3c3c"

# ==================== MOOD KEYWORDS ====================
MOOD_KEYWORDS = {
    "开心": ["开心", "高兴", "快乐", "喜悦", "顺利", "成功", "完美", "太好了", "哈哈", "精彩", "满意", "棒", "赞"],
    "平静": ["还行", "普通", "正常", "一般", "平静", "还好", "不错", "可以", "日常", "无特别"],
    "低落": ["难过", "伤心", "失望", "沮丧", "累", "困", "不舒服", "难受", "糟糕", "完蛋", "郁闷", "疲惫", "好累"],
    "兴奋": ["激动", "兴奋", "期待", "刺激", "太棒了", "厉害", "惊艳", "震撼", "太好了"],
    "焦虑": ["担心", "焦虑", "压力", "烦", "头疼", "麻烦", "纠结", "犹豫", "紧迫", "焦虑"]
}
NEGATION_WORDS = ["不", "没", "别", "无", "非", "不太", "不怎么"]
MOOD_EMOJI = {"开心": "😊", "平静": "😐", "低落": "😢", "兴奋": "🔥", "焦虑": "😰"}

# ==================== STOP WORDS ====================
STOP_WORDS = set([
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也",
    "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这",
    "今天", "明天", "昨天", "然后", "这个", "那个", "什么", "怎么", "为什么",
    "觉得", "感觉", "想", "认为", "知道", "可以", "可能", "应该", "需要",
    "一下", "一点", "一些", "几个", "多少", "很多", "非常", "特别", "真的",
    "还是", "但是", "不过", "而且", "或者", "因为", "所以", "如果", "虽然",
    "已经", "正在", "将要", "曾经", "一直", "总是", "刚刚", "刚才", "现在",
    "里面", "外面", "上面", "下面", "这里", "那里",
    "事情", "东西", "地方", "时候", "样子", "方面", "问题",
    "比较", "更", "最", "太", "挺", "蛮", "稍微", "有点",
    "开始", "继续", "结束", "完成", "进行", "发生", "出现", "变得"
])

DOMAIN_KEYWORDS = [
    "万达", "商场", "公园", "医院", "学校", "公司", "家", "办公室", "餐厅",
    "唱歌", "跳舞", "看电影", "逛街", "购物", "运动", "健身", "跑步", "游泳",
    "开会", "加班", "写代码", "调试", "测试", "部署", "上线", "修复", "优化",
    "朋友", "同事", "家人", "老板", "客户", "老师", "同学",
    "开心", "难过", "兴奋", "焦虑", "平静", "愤怒",
    "Python", "JavaScript", "React", "Vue", "Git", "Docker", "AI", "LLM"
]


# ==================== CORE FUNCTIONS ====================

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def get_now():
    return datetime.now().strftime("%H:%M:%S")

# --- Daily ---
def load_daily(date):
    path = os.path.join(DAILY_DIR, f"{date}.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"# {date} Diary\n\n"

def save_daily(date, content):
    os.makedirs(DAILY_DIR, exist_ok=True)
    path = os.path.join(DAILY_DIR, f"{date}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# --- Mood ---
def analyze_mood(text):
    mood_scores = {m: 0 for m in MOOD_KEYWORDS}
    matched = {m: [] for m in MOOD_KEYWORDS}
    for mood, keywords in MOOD_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                idx = text.find(kw)
                ctx = text[max(0, idx - 4):idx]
                if not any(neg in ctx for neg in NEGATION_WORDS):
                    mood_scores[mood] += 1
                    matched[mood].append(kw)
    best = max(mood_scores.items(), key=lambda x: x[1])
    if best[1] == 0:
        return "平静", 0.5, "no obvious mood"
    conf = min(best[1] / 3.0, 1.0)
    return best[0], conf, ", ".join(matched[best[0]])

def save_mood(date, mood, text, confidence, reason):
    os.makedirs(MOOD_DIR, exist_ok=True)
    path = os.path.join(MOOD_DIR, f"{date}.json")
    records = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
    records.append({
        "time": get_now(), "mood": mood, "text": text[:100],
        "confidence": round(confidence, 2), "reason": reason
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

def load_moods(date):
    path = os.path.join(MOOD_DIR, f"{date}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# --- Tags ---
def extract_tags(text, top_n=5):
    words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', text)
    words = [w for w in words if w not in STOP_WORDS and 2 <= len(w) <= 4 and not w.isdigit()]
    counts = Counter(words)
    domain = [(kw, 10) for kw in DOMAIN_KEYWORDS if kw in text]
    normal = counts.most_common(top_n * 2)
    all_kw = sorted(domain + normal, key=lambda x: x[1], reverse=True)
    return [t[0] for t in all_kw[:top_n]]

# --- Reminders ---
def load_reminders():
    if os.path.exists(REMINDER_FILE):
        with open(REMINDER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_reminders(reminders):
    os.makedirs(REMINDER_DIR, exist_ok=True)
    with open(REMINDER_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def add_reminder(remind_at, message):
    reminders = load_reminders()
    rid = max([r["id"] for r in reminders], default=0) + 1
    task_name = f"WikiReminder_{rid}"
    reminder = {
        "id": rid,
        "remind_at": remind_at.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending",
        "task_name": task_name
    }
    reminders.append(reminder)
    save_reminders(reminders)
    # Create Windows scheduled task
    script_path = os.path.join(WIKI_DIR, "send_reminder.py")
    python_exe = sys.executable  # Use absolute path
    date_str = remind_at.strftime("%Y/%m/%d")
    time_str = remind_at.strftime("%H:%M")
    cmd = ["schtasks", "/create", "/tn", task_name,
           "/tr", f'"{python_exe}" "{script_path}" {rid}',
           "/sc", "once", "/st", time_str, "/sd", date_str, "/f"]
    try:
        subprocess.run(cmd, capture_output=True, timeout=10)
    except Exception:
        pass
    return reminder

def cancel_reminder(rid):
    reminders = load_reminders()
    for r in reminders:
        if r["id"] == rid and r["status"] == "pending":
            if r.get("task_name"):
                try:
                    subprocess.run(["schtasks", "/delete", "/tn", r["task_name"], "/f"],
                                   capture_output=True, timeout=10)
                except Exception:
                    pass
            r["status"] = "cancelled"
            save_reminders(reminders)
            return True
    return False


# ==================== GUI APP ====================

class WikiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("My Wiki")
        self.root.geometry("700x550")
        self.root.configure(bg=BG)
        if os.path.exists(ICON_PATH):
            self.root.iconbitmap(ICON_PATH)
        self.root.attributes("-topmost", True)

        # Notebook (tabs)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BTN_BG, foreground=FG,
                        padding=[12, 6], font=("Segoe UI", 11))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])

        self.nb = ttk.Notebook(root, style="TNotebook")
        self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        self.build_daily_tab()
        self.build_mood_tab()
        self.build_reminder_tab()

        # Status bar
        self.status = tk.Label(root, text="Ready", font=("Segoe UI", 9),
                               bg=BG, fg="gray", anchor="w")
        self.status.pack(fill=tk.X, padx=10, pady=4)

        # Keyboard shortcuts
        root.bind("<Control-s>", lambda e: self.save_daily())
        root.bind("<Control-S>", lambda e: self.save_daily())

    def _label(self, parent, text, **kw):
        font = kw.pop("font", ("Segoe UI", kw.pop("size", 11)))
        return tk.Label(parent, text=text, bg=BG, fg=FG, font=font, **kw)

    def _btn(self, parent, text, cmd, bg=BTN_BG, fg=FG, **kw):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                         activebackground=BTN_ACTIVE, activeforeground=fg,
                         relief=tk.FLAT, font=("Segoe UI", 10), cursor="hand2", **kw)

    # ==================== DAILY TAB ====================
    def build_daily_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="  Diary  ")

        # Top bar
        top = tk.Frame(tab, bg=BG)
        top.pack(fill=tk.X, padx=10, pady=(10, 5))
        self._label(top, f"  {get_today()}", size=13, font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)
        self._btn(top, "Template", self.insert_template, padx=8).pack(side=tk.RIGHT, padx=2)
        self._btn(top, "Tags", self.extract_and_show_tags, padx=8).pack(side=tk.RIGHT, padx=2)

        # Text area
        self.daily_text = scrolledtext.ScrolledText(tab, font=("Consolas", 12),
                                                     bg=BG2, fg=FG, insertbackground=FG,
                                                     wrap=tk.WORD, relief=tk.FLAT)
        self.daily_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.daily_text.insert("1.0", load_daily(get_today()))

        # Bottom
        bot = tk.Frame(tab, bg=BG)
        bot.pack(fill=tk.X, padx=10, pady=(0, 8))
        self._btn(bot, "  Save  ", self.save_daily, bg=ACCENT, fg="white", padx=16, pady=4).pack(side=tk.RIGHT)

        self.tag_display = tk.Label(bot, text="", bg=BG, fg=ACCENT2, font=("Segoe UI", 9))
        self.tag_display.pack(side=tk.LEFT)

    def insert_template(self):
        template = "\n## Done\n- \n\n## Thoughts\n- \n\n## Tomorrow\n- \n"
        self.daily_text.insert(tk.END, template)

    def save_daily(self):
        content = self.daily_text.get("1.0", tk.END).strip()
        save_daily(get_today(), content)
        self.status.config(text=f"Diary saved - {get_today()} {get_now()}", fg=ACCENT2)

    def extract_and_show_tags(self):
        content = self.daily_text.get("1.0", tk.END)
        tags = extract_tags(content)
        if tags:
            self.tag_display.config(text=f"Tags: {', '.join(tags)}")
            self.status.config(text=f"Extracted {len(tags)} tags", fg=ACCENT2)
        else:
            self.tag_display.config(text="No tags found")
            self.status.config(text="No keywords found", fg="gray")

    # ==================== MOOD TAB ====================
    def build_mood_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="  Mood  ")

        # Input
        top = tk.Frame(tab, bg=BG)
        top.pack(fill=tk.X, padx=10, pady=(10, 5))
        self._label(top, "  How are you feeling?", size=13, font=("Segoe UI", 13, "bold")).pack(anchor="w")

        self.mood_input = scrolledtext.ScrolledText(tab, height=3, font=("Segoe UI", 12),
                                                      bg=BG2, fg=FG, insertbackground=FG,
                                                      wrap=tk.WORD, relief=tk.FLAT)
        self.mood_input.pack(fill=tk.X, padx=10, pady=5)

        # Quick mood buttons
        quick = tk.Frame(tab, bg=BG)
        quick.pack(fill=tk.X, padx=10, pady=2)
        for mood, emoji in MOOD_EMOJI.items():
            self._btn(quick, f"{emoji} {mood}", lambda m=mood: self.quick_mood(m),
                      padx=10, pady=4).pack(side=tk.LEFT, padx=3)

        # Analyze button
        btn_frame = tk.Frame(tab, bg=BG)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        self._btn(btn_frame, "  Auto Analyze  ", self.analyze_mood_ui, bg=ACCENT, fg="white",
                  padx=16, pady=4).pack(side=tk.LEFT)

        self.mood_result = tk.Label(btn_frame, text="", bg=BG, fg=ACCENT2, font=("Segoe UI", 12))
        self.mood_result.pack(side=tk.LEFT, padx=10)

        # History
        self._label(tab, "  Today's Records", size=10).pack(anchor="w", padx=10, pady=(10, 2))
        self.mood_history = scrolledtext.ScrolledText(tab, height=10, font=("Consolas", 11),
                                                        bg=BG2, fg=FG, wrap=tk.WORD, relief=tk.FLAT,
                                                        state=tk.DISABLED)
        self.mood_history.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        self.refresh_mood_history()

    def quick_mood(self, mood):
        text = self.mood_input.get("1.0", tk.END).strip()
        if not text:
            text = f"(quick: {mood})"
        save_mood(get_today(), mood, text, 1.0, "manual")
        self.mood_result.config(text=f"{MOOD_EMOJI.get(mood, '')} {mood} - Saved!")
        self.mood_input.delete("1.0", tk.END)
        self.refresh_mood_history()
        self.status.config(text=f"Mood saved: {mood}", fg=ACCENT2)

    def analyze_mood_ui(self):
        text = self.mood_input.get("1.0", tk.END).strip()
        if not text:
            self.mood_result.config(text="Type something first!")
            return
        mood, conf, reason = analyze_mood(text)
        save_mood(get_today(), mood, text, conf, reason)
        emoji = MOOD_EMOJI.get(mood, "")
        self.mood_result.config(text=f"{emoji} {mood} ({conf:.0%})")
        self.mood_input.delete("1.0", tk.END)
        self.refresh_mood_history()
        self.status.config(text=f"Mood: {mood} ({conf:.0%})", fg=ACCENT2)

    def refresh_mood_history(self):
        records = load_moods(get_today())
        self.mood_history.config(state=tk.NORMAL)
        self.mood_history.delete("1.0", tk.END)
        if records:
            for r in records:
                emoji = MOOD_EMOJI.get(r.get("mood", ""), "")
                line = f"[{r.get('time', '?')}] {emoji} {r.get('mood', '?')} ({r.get('confidence', 0):.0%}) - {r.get('text', '')[:40]}\n"
                self.mood_history.insert(tk.END, line)
        else:
            self.mood_history.insert("1.0", "  No records today yet.")
        self.mood_history.config(state=tk.DISABLED)

    # ==================== REMINDER TAB ====================
    def build_reminder_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="  Reminder  ")

        # Preset buttons
        top = tk.Frame(tab, bg=BG)
        top.pack(fill=tk.X, padx=10, pady=(10, 5))
        self._label(top, "  Quick Reminders", size=13, font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 5))

        presets = tk.Frame(tab, bg=BG)
        presets.pack(fill=tk.X, padx=10, pady=5)
        preset_items = [
            ("+1h", 1), ("+2h", 2), ("+3h", 3),
            ("Tomorrow 9am", "tmr9"), ("Tomorrow 6pm", "tmr18")
        ]
        for label, val in preset_items:
            self._btn(presets, label, lambda v=val: self.preset_reminder(v),
                      padx=10, pady=6).pack(side=tk.LEFT, padx=3)

        # Custom reminder
        custom = tk.Frame(tab, bg=BG)
        custom.pack(fill=tk.X, padx=10, pady=10)
        self._label(custom, "Custom:", size=10).pack(side=tk.LEFT)
        self.reminder_msg = tk.Entry(custom, font=("Segoe UI", 11), bg=BG2, fg=FG,
                                      insertbackground=FG, relief=tk.FLAT, width=25)
        self.reminder_msg.pack(side=tk.LEFT, padx=5)
        self.reminder_time = tk.Entry(custom, font=("Segoe UI", 11), bg=BG2, fg=FG,
                                       insertbackground=FG, relief=tk.FLAT, width=15)
        self.reminder_time.insert(0, "HH:MM")
        self.reminder_time.pack(side=tk.LEFT, padx=5)
        self._btn(custom, "Add", self.add_custom_reminder, bg=ACCENT, fg="white", padx=10).pack(side=tk.LEFT, padx=5)

        # Reminder list
        self._label(tab, "  Pending", size=10).pack(anchor="w", padx=10, pady=(10, 2))
        self.reminder_list = scrolledtext.ScrolledText(tab, height=8, font=("Consolas", 11),
                                                         bg=BG2, fg=FG, wrap=tk.WORD, relief=tk.FLAT,
                                                         state=tk.DISABLED)
        self.reminder_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        # Cancel button
        bot = tk.Frame(tab, bg=BG)
        bot.pack(fill=tk.X, padx=10, pady=(0, 8))
        self._label(bot, "Cancel ID:", size=9).pack(side=tk.LEFT)
        self.cancel_id = tk.Entry(bot, font=("Segoe UI", 10), bg=BG2, fg=FG,
                                    insertbackground=FG, relief=tk.FLAT, width=5)
        self.cancel_id.pack(side=tk.LEFT, padx=5)
        self._btn(bot, "Cancel", self.cancel_reminder_ui, padx=8).pack(side=tk.LEFT, padx=5)

        self.refresh_reminder_list()

    def preset_reminder(self, val):
        now = datetime.now()
        msg = self.reminder_msg.get().strip() or "Reminder!"
        if isinstance(val, int):
            target = now + timedelta(hours=val)
        elif val == "tmr9":
            target = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        elif val == "tmr18":
            target = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        else:
            return
        r = add_reminder(target, msg)
        self.status.config(text=f"Reminder set: {target.strftime('%H:%M')} - {msg}", fg=ACCENT2)
        self.refresh_reminder_list()

    def add_custom_reminder(self):
        msg = self.reminder_msg.get().strip()
        time_str = self.reminder_time.get().strip()
        if not msg:
            self.status.config(text="Enter a message first!", fg="orange")
            return
        try:
            h, m = map(int, time_str.split(":"))
            target = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= datetime.now():
                target += timedelta(days=1)
            add_reminder(target, msg)
            self.status.config(text=f"Reminder set: {target.strftime('%H:%M')} - {msg}", fg=ACCENT2)
            self.refresh_reminder_list()
        except ValueError:
            self.status.config(text="Invalid time format (HH:MM)", fg="orange")

    def cancel_reminder_ui(self):
        try:
            rid = int(self.cancel_id.get().strip())
            if cancel_reminder(rid):
                self.status.config(text=f"Reminder #{rid} cancelled", fg=ACCENT2)
                self.refresh_reminder_list()
            else:
                self.status.config(text=f"Cannot cancel #{rid}", fg="orange")
        except ValueError:
            self.status.config(text="Enter valid ID", fg="orange")

    def refresh_reminder_list(self):
        reminders = load_reminders()
        pending = [r for r in reminders if r["status"] == "pending"]
        self.reminder_list.config(state=tk.NORMAL)
        self.reminder_list.delete("1.0", tk.END)
        if pending:
            for r in pending:
                line = f"  #{r['id']}  [{r['remind_at']}]  {r['message']}\n"
                self.reminder_list.insert(tk.END, line)
        else:
            self.reminder_list.insert("1.0", "  No pending reminders.")
        self.reminder_list.config(state=tk.DISABLED)


# ==================== MAIN ====================
if __name__ == "__main__":
    # First run check / 首次运行检测
    proceed = show_welcome_and_check()
    if not proceed:
        sys.exit(0)
    
    # Start main app / 启动主程序
    root = tk.Tk()
    app = WikiApp(root)
    root.mainloop()
