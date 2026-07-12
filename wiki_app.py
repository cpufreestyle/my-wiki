#!/usr/bin/env python3
"""
My Wiki - All-in-One Personal Knowledge Tool
日记 | 心情 | 提醒 | 标签
"""
import os
# 抑制 macOS 系统 Tk (8.5) 的弃用警告（命令行里黄色感叹号）
os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
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
    """检测 Obsidian 是否安装（跨平台）。"""
    if sys.platform == "darwin":
        if os.path.exists("/Applications/Obsidian.app"):
            return True, "/Applications/Obsidian.app"
        return False, None
    if sys.platform == "win32":
        paths = [
            r"C:\Users\{}\AppData\Local\Obsidian\Obsidian.exe".format(os.getenv("USERNAME")),
            r"C:\Program Files\Obsidian\Obsidian.exe",
            r"C:\Program Files (x86)\Obsidian\Obsidian.exe",
        ]
        for p in paths:
            if os.path.exists(p):
                return True, p
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
    """检测 OpenClaw 是否安装（跨平台）。

    注意：双击 app 启动时进程的 PATH 往往不含终端 shell 的 PATH，
    因此只靠 `openclaw` 命令可能找不到，需要枚举常见绝对路径。
    """
    candidates = []
    if sys.platform == "darwin":
        candidates = [
            "/Applications/OpenClaw.app",
            "/usr/local/bin/openclaw",
            "/opt/homebrew/bin/openclaw",
            os.path.expanduser("~/.local/bin/openclaw"),
            os.path.expanduser("~/.npm-global/bin/openclaw"),
            os.path.expanduser("~/.cargo/bin/openclaw"),
            # QClaw 自带的 OpenClaw（macOS 上的实际安装位置）
            os.path.expanduser("~/Library/Application Support/QClaw/openclaw"),
            os.path.expanduser("~/Library/Application Support/QClaw/openclaw/node_modules/.bin/openclaw"),
        ]
    elif sys.platform == "win32":
        candidates = [
            r"C:\Users\{}\AppData\Local\Programs\openclaw\openclaw.exe".format(os.getenv("USERNAME")),
            r"C:\Program Files\QClaw\openclaw.exe",
            r"C:\Program Files (x86)\QClaw\openclaw.exe",
        ]
    # 动态获取 npm 全局 bin 目录（GUI 启动 PATH 受限时也能命中）
    try:
        out = subprocess.run(["npm", "prefix", "-g"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            candidates.append(os.path.join(out.stdout.strip(), "bin", "openclaw"))
    except Exception:
        pass
    # PATH 中查找（覆盖终端能直接运行的情况）
    found = shutil.which("openclaw")
    if found:
        candidates.insert(0, found)
    for c in candidates:
        if c.endswith(".app"):
            if os.path.exists(c):
                return True, c
            continue
        if os.path.exists(c):
            try:
                r = subprocess.run([c, "--version"], capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    return True, (r.stdout.strip() or c)
            except Exception:
                pass
            return True, c
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
    dlg.resizable(True, True)
    dlg.transient(parent_window)
    dlg.grab_set()
    
    tk.Label(dlg, text="Downloading Obsidian installer...\n正在下载 Obsidian 安装包...", 
             bg=BG, fg=FG, font=ui(10)).pack(pady=15)
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
    dlg.resizable(True, True)
    dlg.transient(parent_window)
    dlg.grab_set()
    
    tk.Label(dlg, text="Installing OpenClaw globally...\n正在全局安装 OpenClaw...", 
             bg=BG, fg=FG, font=ui(10)).pack(pady=15)
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

def show_welcome_and_check(parent):
    """
    在已有的主 Tk 根 (parent) 之上显示欢迎/首次运行窗口（Toplevel）。

    关键:
      - 整个进程**只有一个 Tk() 根实例**，欢迎框只是它的 Toplevel 子窗口。
      - **不使用 grab_set()**：macOS 下模态 grab 会拦截主窗口的全部输入，
        导致"主界面看不见输入框 / 无法点击文本框"。改为非模态窗口，
        主界面始终在背后可见且可交互。
      - 由主程序的 root.mainloop() 统一驱动事件。

    按钮行为:
      - 继续/跳过: 关闭 Toplevel
      - 退出:      关闭整个程序 (parent.destroy())

    设置环境变量 MYWIKI_SKIP_WELCOME=1 可完全跳过欢迎框。
    """
    if os.environ.get("MYWIKI_SKIP_WELCOME") == "1":
        return

    dlg = tk.Toplevel(parent)
    dlg.title("MyWiki - First Run Setup / 首次运行设置")
    dlg.geometry("600x540")
    dlg.configure(bg=BG)
    # 允许鼠标拖拽调整大小
    dlg.resizable(True, True)
    dlg.minsize(420, 360)

    # 注意: 刻意**不**使用 grab_set() / -topmost，避免遮挡并锁死主窗口输入
    try:
        dlg.transient(parent)
    except Exception:
        pass

    # Icon
    if os.path.exists(ICON_PATH):
        try:
            dlg.iconbitmap(ICON_PATH)
        except Exception:
            pass

    # Title
    tk.Label(dlg, text="📝 MyWiki", bg=BG, fg=ACCENT, font=ui(20, bold=True)).pack(pady=(25, 5))
    tk.Label(dlg, text="Personal Knowledge & Diary Manager\n个人知识库与日记管理工具",
             bg=BG, fg=FG, font=ui(10)).pack()

    tk.Frame(dlg, height=2, bg=ACCENT).pack(fill="x", padx=40, pady=15)

    # Check status
    obsidian_ok, obsidian_path = check_obsidian()
    openclaw_ok, openclaw_ver = check_openclaw()

    status_frame = tk.Frame(dlg, bg=BG)
    status_frame.pack(pady=5)

    tk.Label(status_frame, text="System Check / 系统检测", bg=BG, fg=FG, font=ui(11, bold=True)).pack(anchor="w", padx=30)

    def make_status(p, label, ok):
        f = tk.Frame(p, bg=BG)
        f.pack(fill="x", padx=30, pady=4)
        emoji = "✅" if ok else "❌"
        color = "#4ec9b0" if ok else "#f48771"
        tk.Label(f, text="{} {}".format(emoji, label), bg=BG, fg=color, font=ui(10), anchor="w").pack(side="left")
        return f

    make_status(status_frame, "Obsidian (知识库)", obsidian_ok)
    make_status(status_frame, "OpenClaw (AI 助手)", openclaw_ok)

    # 语音识别就绪检测（ffmpeg 录音 + SpeechRecognition 识别）
    v_ffmpeg, v_sr = voice_mood.deps_status()
    voice_ok = v_ffmpeg and v_sr

    # 语音状态行（保存 label 引用，安装完成后刷新为已就绪）
    voice_row = tk.Frame(status_frame, bg=BG)
    voice_row.pack(fill="x", padx=30, pady=4)
    voice_lbl = tk.Label(
        voice_row,
        text="✅ 语音识别 (麦克风记录心情)" if voice_ok
             else "❌ 语音识别 (缺依赖，可一键安装)",
        bg=BG, fg="#4ec9b0" if voice_ok else "#f48771",
        font=ui(10), anchor="w")
    voice_lbl.pack(side="left")

    # 一键安装语音依赖（后台 pip 安装，按钮显示进度 / 可重试）
    _voice_btn = {"ref": None}

    # 后台线程安装，主线程轮询 after 取结果（避免跨线程直接调用 after）
    _voice_result = {}

    def on_install_voice():
        btn = _voice_btn["ref"]
        if btn is not None:
            btn.set_enabled(False)
            btn.config(text="安装中…")
        voice_lbl.config(text="❌ 语音识别 (安装中…)")
        _voice_result.clear()

        def run():
            try:
                _voice_result["v"] = voice_mood.auto_install_deps()
            except Exception as e:
                _voice_result["v"] = (False, False, ["安装异常：{}".format(e)])

        threading.Thread(target=run, daemon=True).start()
        parent.after(150, _poll_voice_install)

    def _poll_voice_install():
        r = _voice_result.get("v")
        if r is None:
            parent.after(150, _poll_voice_install)
            return
        _finish_voice(*r)

    def _finish_voice(f_ok, s_ok, notes):
        ok = f_ok and s_ok
        btn = _voice_btn["ref"]
        if ok:
            voice_lbl.config(text="✅ 语音识别 (麦克风记录心情)", fg="#4ec9b0")
            if btn is not None:
                btn.destroy()
            messagebox.showinfo("安装完成 / Done",
                                "语音依赖已安装，可前往「心情」页点击 🎤 使用。\n"
                                "Voice deps installed. Go to the Mood tab and tap 🎤.")
        else:
            if btn is not None:
                btn.set_enabled(True)
                btn.config(text="重试安装语音 / Retry")
            detail = "语音依赖安装失败，请手动安装：\n" \
                     "Voice deps install failed, manual install:"
            if not f_ok:
                detail += "\n" + t("voice_need_ffmpeg")
            if not s_ok:
                detail += "\n" + t("voice_need_sr").format(py=sys.executable)
            if notes:
                detail += "\n\n" + "\n".join(notes)
            messagebox.showerror("语音依赖安装失败 / Failed", detail)

    tk.Frame(dlg, height=2, bg=ACCENT).pack(fill="x", padx=40, pady=10)

    btn_frame = tk.Frame(dlg, bg=BG)
    btn_frame.pack(pady=10)

    def on_install_obsidian():
        if install_obsidian(dlg):
            messagebox.showinfo("Done / 完成", "Obsidian installed. Please restart MyWiki.\nObsidian 已安装，请重启 MyWiki。")
            dlg.destroy()

    def on_install_openclaw():
        if install_openclaw(dlg):
            messagebox.showinfo("Done / 完成", "OpenClaw installed. Please restart MyWiki.\nOpenClaw 已安装，请重启 MyWiki。")
            dlg.destroy()

    def on_proceed():
        # 欢迎框为非模态：直接关闭即可，主界面一直在背后可见可交互
        dlg.destroy()
        # macOS 下关闭 Toplevel 后主窗口不会自动拿回键盘焦点，
        # 必须显式把焦点交给第一个输入框，否则文本框"输不进字"
        try:
            parent.after(10, lambda: _focus_first_input(parent))
        except Exception:
            pass

    def on_exit():
        parent.destroy()

    if not obsidian_ok:
        _make_clickable_label(btn_frame, "Install Obsidian / 安装 Obsidian",
                              on_install_obsidian,
                              bg=INPUT_BG, fg=ACCENT, hover_bg=BTN_ACTIVE,
                              font=ui(10), padx=15, pady=5).pack(pady=3)

    if not openclaw_ok:
        _make_clickable_label(btn_frame, "Install OpenClaw / 安装 OpenClaw",
                              on_install_openclaw,
                              bg=INPUT_BG, fg=ACCENT, hover_bg=BTN_ACTIVE,
                              font=ui(10), padx=15, pady=5).pack(pady=3)

    if not voice_ok:
        vb = _make_clickable_label(btn_frame, "Install Voice / 安装语音依赖",
                                   on_install_voice,
                                   bg=INPUT_BG, fg=ACCENT, hover_bg=BTN_ACTIVE,
                                   font=ui(10), padx=15, pady=5)
        vb.pack(pady=3)
        _voice_btn["ref"] = vb

    btn_row = tk.Frame(btn_frame, bg=BG)
    btn_row.pack(pady=(10, 0))

    label = "Continue / 继续" if (obsidian_ok and openclaw_ok) else "Skip & Continue / 跳过并继续"
    _make_clickable_label(btn_row, label, on_proceed,
                          bg=INPUT_BG, fg=ACCENT, hover_bg=BTN_ACTIVE,
                          font=ui(10, bold=True), padx=20, pady=6).pack(side=tk.LEFT, padx=5)
    _make_clickable_label(btn_row, "Exit / 退出", on_exit,
                          bg=INPUT_BG, fg=INPUT_FG, hover_bg=BTN_ACTIVE,
                          font=ui(10), padx=20, pady=6).pack(side=tk.LEFT, padx=5)

    tk.Label(dlg, text="Tips: Obsidian & OpenClaw are optional.\n提示：Obsidian 和 OpenClaw 是可选的，MyWiki 可独立运行。",
             bg=BG, fg=MUTED, font=ui(8)).pack(pady=(10, 5))

    # 不调用 wait_window: 主 root.mainloop() 会驱动本 Toplevel 的事件

def _focus_first_input(root):
    """把焦点交给主窗口第一个可输入控件，确保键盘事件能被接收。"""
    for child in root.winfo_children():
        _walk_focus(child)


def _walk_focus(w):
    try:
        cls = w.winfo_class()
    except Exception:
        return False
    # ScrolledText 内部真正可输入的是它的 Text 子控件（ScrolledText 本身是 Frame）
    if "ScrolledText" in type(w).__name__ or cls == "ScrolledText":
        try:
            kids = w.winfo_children()
            text_child = None
            for k in kids:
                if k.winfo_class() == "Text":
                    text_child = k
                    break
            target = text_child if text_child is not None else w
            target.focus_set()
            try:
                target.see("1.0")
            except Exception:
                pass
            return True
        except Exception:
            pass
        return False
    # 普通 Text / Entry 直接聚焦
    if cls in ("Text", "Entry"):
        try:
            w.focus_set()
            w.see("1.0")
        except Exception:
            pass
        return True
    # 递归子控件
    try:
        for c in w.winfo_children():
            if _walk_focus(c):
                return True
    except Exception:
        pass
    return False


# ==================== PATHS ====================
from pathlib import Path as _Path
_SCRIPT_DIR = _Path(__file__).parent
WIKI_DIR = str(_SCRIPT_DIR.parent.parent / "wiki")
# 图标解析：直接 `python wiki_app.py` 时脚本目录即仓库根，真实图标位于
# 仓库根/icon.ico 与 assets/AppIcon.icns（WIKI_DIR 指向仓库外，旧路径取不到图标）。
# 按平台优先选 .icns（macOS Tk 支持）/ .ico（Windows/Linux），确保窗口图标真正生效。
def _resolve_app_icon():
    cands = []
    if sys.platform == "darwin":
        cands.append(os.path.join(_SCRIPT_DIR, "assets", "AppIcon.icns"))
    cands.append(os.path.join(_SCRIPT_DIR, "icon.ico"))
    cands.append(os.path.join(_SCRIPT_DIR, "wiki", "icon.ico"))
    cands.append(os.path.join(_SCRIPT_DIR, "assets", "AppIcon.icns"))
    for c in cands:
        if os.path.exists(c):
            return c
    return ""

ICON_PATH = _resolve_app_icon()
DAILY_DIR = os.path.join(WIKI_DIR, "daily")
MOOD_DIR = os.path.join(WIKI_DIR, "mood")
REMINDER_DIR = os.path.join(WIKI_DIR, "reminders")
REMINDER_FILE = os.path.join(REMINDER_DIR, "reminders.json")
PENDING_FILE = os.path.join(REMINDER_DIR, "pending_notifications.json")

# ==================== THEME（统一设计系统：Apple 风浅/深色，与网页端 reminder_web.html / reminder_ui.py / daily_ui.py 共用 theme.py） ====================
from theme import get_tokens, load_theme_pref, save_theme_pref

# 语音识别心情（ffmpeg 录音 + SpeechRecognition 在线识别，无需 pyaudio）
import threading
import voice_mood

MODE = load_theme_pref()  # 浅色 / 深色，与另外两个桌面端及网页端同步

def apply_theme(mode):
    """把 theme.py 的 token 映射到本程序的配色常量（支持浅/深色，与网页端一致）。"""
    T = get_tokens(mode)
    global BG, BG2, FG, INPUT_BG, INPUT_FG, INPUT_INSERT, ACCENT, ACCENT2, BTN_BG, BTN_ACTIVE, MUTED
    global BORDER, ORANGE, GREEN, ORANGE_H, GREEN_H, ACCENT_H
    BG = T["BG"]                # 页面背景：浅灰 / 深灰
    BG2 = T["SURFACE"]          # 次级背景 / 卡片：白 / 深卡
    FG = T["TEXT"]              # 主文字
    INPUT_BG = T["SURFACE"]     # 输入框 / 主按钮：白卡 / 深卡
    INPUT_FG = T["TEXT"]        # 输入文字
    INPUT_INSERT = T["TEXT"]    # 光标
    ACCENT = T["ACCENT"]        # Apple 蓝（深浅一致）
    ACCENT2 = T["GREEN"]        # 成功 / 强调绿
    BTN_BG = T["BG"]            # 次级按钮背景（浅灰 / 深灰）
    BTN_ACTIVE = T["BTN_HOVER"] # 按钮 hover
    MUTED = T["TEXT2"]          # 次要文字
    BORDER = T["BORDER"]        # 卡片描边
    ORANGE = T["ORANGE"]        # 自定义提醒（橙）
    GREEN = T["GREEN"]          # 查看 / 成功（绿）
    ORANGE_H = T["ORANGE_H"]    # 橙 hover
    GREEN_H = T["GREEN_H"]      # 绿 hover
    ACCENT_H = T["ACCENT_H"]    # 蓝 hover

apply_theme(MODE)

# ==================== FONTS (跨平台) ====================
# Segoe UI / Consolas 是 Windows 字体，macOS 上不存在，会导致字体渲染异常、
# 中文显示为方块、控件被挤压看不清。这里按平台选择系统自带字体。
if sys.platform == "darwin":            # macOS
    UI_FONT = "PingFang SC"             # 系统中文/英文通用无衬线字体
    MONO_FONT = "Menlo"                 # 等宽字体
elif sys.platform.startswith("win"):    # Windows
    UI_FONT = "Microsoft YaHei UI"
    MONO_FONT = "Consolas"
else:                                    # Linux 等
    UI_FONT = "Noto Sans CJK SC"
    MONO_FONT = "DejaVu Sans Mono"

# ==================== 字号缩放（全屏使用时整体放大） ====================
# 以全屏为基础调大文字与图标（emoji 随字号放大）。改这里即可整体微调。
FONT_SCALE = 1.2


def ui(size, bold=False):
    """返回按 FONT_SCALE 缩放后的 UI 字体元组。"""
    sz = int(round(size * FONT_SCALE))
    return (UI_FONT, sz, "bold") if bold else (UI_FONT, sz)


def mono(size):
    """返回按 FONT_SCALE 缩放后的等宽字体元组。"""
    return (MONO_FONT, int(round(size * FONT_SCALE)))


def _make_clickable_label(parent, text, command, bg, fg, hover_bg=None,
                          font=None, padx=15, pady=5, cursor="hand2"):
    """可点击按钮（用 tk.Label 实现）。

    macOS 原生 tk.Button 在深色系统外观下会忽略 bg/fg，导致按钮底色/文字
    被系统接管、在深色模式下几乎看不清。tk.Label 的 bg/fg 永远生效，
    因此用它做按钮可保证配色正确。提供 set_enabled / invoke 以兼容
    原 tk.Button 的部分用法（state、invoke）。
    """
    if font is None:
        font = ui(10)
    lbl = tk.Label(parent, text=text, bg=bg, fg=fg, font=font,
                   padx=padx, pady=pady, cursor=cursor)
    _cmd = {"enabled": True, "command": command}

    def _do_click(_=None):
        if _cmd["enabled"]:
            _cmd["command"]()

    def _on_enter(_):
        if hover_bg and _cmd["enabled"]:
            lbl.config(bg=hover_bg)

    def _on_leave(_):
        if hover_bg:
            lbl.config(bg=bg)

    lbl.bind("<Button-1>", _do_click)
    lbl.bind("<Enter>", _on_enter)
    lbl.bind("<Leave>", _on_leave)

    def set_enabled(enabled):
        _cmd["enabled"] = bool(enabled)
        if enabled:
            lbl.config(cursor=cursor)
            lbl.bind("<Button-1>", _do_click)
        else:
            lbl.config(cursor="")
            try:
                lbl.unbind("<Button-1>")
            except Exception:
                pass

    lbl.set_enabled = set_enabled
    lbl.invoke = lambda: _do_click()
    return lbl

# ==================== I18N 语言字典 ====================
LANG = "zh"  # 默认中文；可切换为 "en"
I18N = {
    "zh": {
        "app_title": "我的知识库",
        "tab_diary": "  日记  ", "tab_mood": "  心情  ",
        "tab_reminder": "  提醒  ", "tab_share": "  共享  ",
        "ready": "就绪", "lang_btn": "EN",
        "template": "模板", "tags": "标签", "save": "  保存  ",
        "diary_saved": "日记已保存", "extracted_tags": "已提取 {n} 个标签",
        "no_tags": "未找到标签", "no_keywords": "未发现关键词",
        "mood_q": "  今天感觉如何？", "auto_analyze": "  自动分析  ",
        "today_records": "  今日记录", "no_records": "  今日暂无记录。",
        "type_first": "请先输入内容！", "mood_saved": "心情已保存：{m}",
        "voice": "🎤 语音", "voice_stop": "⏹ 停止",
        "voice_autosave": "识别后自动保存", "voice_filled": "已填入，请检查后保存",
        "voice_missing_ffmpeg": "ffmpeg（录音）", "voice_missing_sr": "SpeechRecognition（识别）",
        "voice_confirm_install": "缺少语音依赖：{n}\n\n是否自动安装？（需要联网，使用 pip）",
        "voice_installing": "正在安装语音依赖…", "voice_install_ok": "语音依赖已就绪",
        "voice_install_fail": "语音依赖安装失败，请手动安装：",
        "voice_recording": "正在聆听…（最多 {n} 秒）",
        "voice_recognizing": "识别中…", "voice_done": "已识别语音",
        "voice_cancel": "已取消", "voice_empty": "没听清，请再说一次。",
        "voice_netfail": "识别服务不可用（需联网）",
        "voice_need_ffmpeg": "语音功能需要 ffmpeg（用于录音）\n\n请先安装：\n  brew install ffmpeg\n\n安装后重试。",
        "voice_need_sr": "语音识别需要 Python 包 SpeechRecognition\n\n请安装：\n  {py} -m pip install SpeechRecognition\n\n识别使用 Google 在线接口，需要联网。",
        "mic_perm_btn": "🔧",
        "mic_perm_title": "麦克风权限",
        "mic_perm_help": "若录音失败或提示「麦克风权限被拒绝」：\n\n1) 打开「系统设置 › 隐私与安全性 › 麦克风」，给运行本程序的终端/应用（Terminal、iTerm 或 MyWiki.app）开启权限；\n2) 或点击下方「一键重置」清空授权，重启后重新弹窗允许；\n3) 完全退出 MyWiki 后重新打开再试。",
        "mic_perm_reset": "🔄 一键重置麦克风权限",
        "mic_perm_reset_ok": "已重置麦克风授权。请完全退出 MyWiki 并重新打开，首次录音会重新请求权限，请点「允许」。",
        "mic_perm_reset_fail": "重置失败（可能无需重置，或需手动操作）。请手动到「系统设置 › 隐私与安全性 › 麦克风」开启权限。",
        "mic_perm_only_mac": "一键重置仅支持 macOS。请手动到「系统设置 › 隐私与安全性 › 麦克风」开启权限。",
        "close": "关闭",
        "quick_reminders": "  快捷提醒", "custom": "自定义：",
        "add": "添加", "pending": "  待提醒", "cancel_id": "取消编号：",
        "cancel": "取消", "no_pending": "  暂无待提醒。",
        "enter_msg": "请先输入提醒内容！", "bad_time": "时间格式错误（HH:MM）",
        "enter_id": "请输入有效编号", "reminder_set": "提醒已设置：{t} - {m}",
        "reminder_cancelled": "提醒 #{i} 已取消", "cannot_cancel": "无法取消 #{i}",
        "tmr9": "明天9点", "tmr18": "明天18点",
        "share_title": "🌐 共享知识库 — Obsidian × 所有 Agent",
        "refresh": "刷新", "start_server": "▶ 启动 MCP 服务",
        "open_obsidian": "🔭 在 Obsidian 打开", "broadcast": "🔔 通知 Agent",
    },
    "en": {
        "app_title": "My Wiki",
        "tab_diary": "  Diary  ", "tab_mood": "  Mood  ",
        "tab_reminder": "  Reminder  ", "tab_share": "  Share  ",
        "ready": "Ready", "lang_btn": "中",
        "template": "Template", "tags": "Tags", "save": "  Save  ",
        "diary_saved": "Diary saved", "extracted_tags": "Extracted {n} tags",
        "no_tags": "No tags found", "no_keywords": "No keywords found",
        "mood_q": "  How are you feeling?", "auto_analyze": "  Auto Analyze  ",
        "today_records": "  Today's Records", "no_records": "  No records today yet.",
        "type_first": "Type something first!", "mood_saved": "Mood saved: {m}",
        "voice": "🎤 Voice", "voice_stop": "⏹ Stop",
        "voice_autosave": "Auto-save after recognition", "voice_filled": "Filled in — review then save",
        "voice_missing_ffmpeg": "ffmpeg (recording)", "voice_missing_sr": "SpeechRecognition (recognition)",
        "voice_confirm_install": "Missing voice deps: {n}\n\nAuto-install now? (needs internet, uses pip)",
        "voice_installing": "Installing voice deps…", "voice_install_ok": "Voice deps ready",
        "voice_install_fail": "Voice deps install failed. Manual install:",
        "voice_recording": "Listening… (max {n}s)",
        "voice_recognizing": "Recognizing…", "voice_done": "Voice recognized",
        "voice_cancel": "Cancelled", "voice_empty": "Couldn't hear that, try again.",
        "voice_netfail": "Recognition service unavailable (needs internet)",
        "voice_need_ffmpeg": "Voice needs ffmpeg (for recording)\n\nInstall it:\n  brew install ffmpeg\n\nThen retry.",
        "voice_need_sr": "Voice recognition needs the SpeechRecognition package\n\nInstall:\n  {py} -m pip install SpeechRecognition\n\nUses Google's online API (needs internet).",
        "mic_perm_btn": "🔧",
        "mic_perm_title": "Microphone Permission",
        "mic_perm_help": "If recording fails or you see 'microphone permission denied':\n\n1) Open System Settings › Privacy & Security › Microphone and enable the app running MyWiki (Terminal, iTerm or MyWiki.app);\n2) Or click 'Reset' below to clear authorization, then restart and re-allow;\n3) Fully quit MyWiki and reopen before retrying.",
        "mic_perm_reset": "🔄 Reset Microphone Permission",
        "mic_perm_reset_ok": "Microphone authorization reset. Fully quit MyWiki, reopen it, and allow access when prompted on first recording.",
        "mic_perm_reset_fail": "Reset failed (maybe not needed, or do it manually). Please enable microphone in System Settings › Privacy & Security › Microphone.",
        "mic_perm_only_mac": "One-click reset is macOS only. Please enable microphone manually in System Settings › Privacy & Security › Microphone.",
        "close": "Close",
        "quick_reminders": "  Quick Reminders", "custom": "Custom:",
        "add": "Add", "pending": "  Pending", "cancel_id": "Cancel ID:",
        "cancel": "Cancel", "no_pending": "  No pending reminders.",
        "enter_msg": "Enter a message first!", "bad_time": "Invalid time format (HH:MM)",
        "enter_id": "Enter valid ID", "reminder_set": "Reminder set: {t} - {m}",
        "reminder_cancelled": "Reminder #{i} cancelled", "cannot_cancel": "Cannot cancel #{i}",
        "tmr9": "Tomorrow 9am", "tmr18": "Tomorrow 6pm",
        "share_title": "🌐 Shared Wiki — Obsidian × All Agents",
        "refresh": "Refresh", "start_server": "▶ Start MCP Server",
        "open_obsidian": "🔭 Open in Obsidian", "broadcast": "🔔 Notify Agents",
    },
}

def t(key, **kw):
    """取当前语言文案，支持 {n}/{m}/{t}/{i} 占位符"""
    s = I18N.get(LANG, I18N["zh"]).get(key, key)
    return s.format(**kw) if kw else s

# ==================== MOOD KEYWORDS ====================
MOOD_KEYWORDS = {
    "开心": ["开心", "高兴", "快乐", "喜悦", "顺利", "成功", "完美", "太好了", "哈哈", "精彩", "满意", "棒", "赞", "好玩", "有趣", "好吃", "舒服", "放松", "享受", "愉快", "不错", "挺好的", "喜欢", "爱", "谢", "感谢", "酷", "帅", "美", "值得", "收获"],
    "平静": ["还行", "普通", "正常", "一般", "平静", "还好", "日常", "无特别", "没什么", "老样子", "照常", "平淡", "安静", "稳定", "规律"],
    "低落": ["难过", "伤心", "失望", "沮丧", "累", "困", "不舒服", "难受", "糟糕", "完蛋", "郁闷", "疲惫", "好累", "无聊", "烦闷", "心痛", "委屈", "倒霉", "不顺", "挫折", "失败", "放弃", "孤独", "寂寞", "想哭", "哭", "累死", "不想"],
    "兴奋": ["激动", "兴奋", "期待", "刺激", "太棒了", "厉害", "惊艳", "震撼", "太好了", "哇", "牛", "强", "爽", "燃", "沸腾", "迫不及待", "终于"],
    "焦虑": ["担心", "焦虑", "压力", "烦", "头疼", "麻烦", "纠结", "犹豫", "紧迫", "急", "紧张", "害怕", "恐惧", "慌", "不安", "心烦", "烦躁", "压力大", "赶", "来不及", "怎么办"]
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
        return "平静", 0.3, "未检测到明显情绪词"
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
        self.root.title(t("app_title"))
        # 默认以全屏（最大化）为基准，方便看清放大后的文字与图标。
        # 优先用原生最大化；若当前 Tk 构建不支持则回退为手动全屏几何。
        try:
            if sys.platform == "darwin":
                self.root.attributes("-zoomed", True)   # macOS 最大化
            else:
                self.root.state("zoomed")               # Windows / Linux 最大化
        except Exception:
            try:
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                top_inset = 28 if sys.platform == "darwin" else 0
                self.root.geometry("{}x{}+0+0".format(sw, sh - top_inset))
            except Exception:
                self.root.geometry("1100x720")
        # 保留一个合理的最小尺寸，缩小时也不至于挤压
        self.root.minsize(760, 620)
        # 允许鼠标拖拽调整主窗口大小
        self.root.resizable(True, True)
        self.root.configure(bg=BG)
        if os.path.exists(ICON_PATH):
            try:
                self.root.iconbitmap(ICON_PATH)
            except Exception:
                pass

        # ttk 样式：使用跨平台字体，并给 Tab 更大 padding 防止文字贴边
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        if style.theme_use() == "clam":
            # clam 主题下标签栏背景完全可控：深底 + 浅字，不受系统深浅模式影响
            style.configure("TNotebook", background=BG, borderwidth=0)
            style.configure("TNotebook.Tab", padding=[16, 8], font=ui(12),
                            background=BG2, foreground=FG, borderwidth=1)
            style.map("TNotebook.Tab",
                      background=[("selected", ACCENT)],
                      foreground=[("selected", "white")])
        else:
            # Aqua 兜底（系统标签栏为浅色背景）：未选中用主文字色，深浅模式都清晰
            style.configure("TNotebook.Tab", padding=[16, 8], font=ui(12),
                            background=BG2, foreground=FG)
            style.map("TNotebook.Tab",
                      background=[("selected", ACCENT), ("!selected", BG2)],
                      foreground=[("selected", "white"), ("!selected", FG)])

        # 顶部工具条：语言切换按钮
        self._build_topbar()

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 0))

        self.build_daily_tab()
        self.build_mood_tab()
        self.build_reminder_tab()
        self.build_share_tab()

        # Status bar（字号加大更清晰）
        self.status = tk.Label(root, text=t("ready"), font=ui(10),
                               bg=BG, fg=MUTED, anchor="w")
        self.status.pack(fill=tk.X, padx=10, pady=4)

        # Keyboard shortcuts
        root.bind("<Control-s>", lambda e: self.save_daily())
        root.bind("<Control-S>", lambda e: self.save_daily())

        # 启动即把键盘焦点交给日记文本框（macOS 下 Tk 不会自动聚焦）
        try:
            self.daily_text.focus_set()
        except Exception:
            pass

    def _build_topbar(self):
        """顶部工具条，含中英文切换按钮"""
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill=tk.X, padx=8, pady=(6, 0))
        tk.Label(bar, text="📝 " + t("app_title"), bg=BG, fg=ACCENT,
                 font=ui(13, bold=True)).pack(side=tk.LEFT, padx=4)
        _make_clickable_label(bar, t("lang_btn"), self.toggle_language,
                               bg=INPUT_BG, fg=ACCENT, hover_bg=BTN_ACTIVE,
                               font=ui(10, bold=True),
                               padx=12, pady=2).pack(side=tk.RIGHT, padx=4)
        # 主题切换（浅色/深色，与网页端及另外两个桌面端同步偏好）
        theme_icon = "🌙" if MODE == "light" else "☀️"
        _make_clickable_label(bar, theme_icon, self.toggle_theme,
                              bg=INPUT_BG, fg=ACCENT, hover_bg=BTN_ACTIVE,
                              font=ui(10, bold=True),
                              padx=10, pady=2).pack(side=tk.RIGHT, padx=2)

    def toggle_language(self):
        """中/英切换：切换 LANG 后重建整个界面"""
        self._stop_voice_if_running()
        global LANG
        LANG = "en" if LANG == "zh" else "zh"
        # 销毁所有子控件后重建
        for child in list(self.root.winfo_children()):
            child.destroy()
        self.__init__(self.root)

    def toggle_theme(self):
        """浅色/深色切换：写入偏好并整体重建界面（与 reminder/daily 桌面端及网页端同步）。"""
        self._stop_voice_if_running()
        global MODE
        MODE = "dark" if MODE == "light" else "light"
        save_theme_pref(MODE)
        apply_theme(MODE)
        # 保留当前窗口尺寸
        geo = self.root.geometry()
        # 销毁所有子控件后重建
        for child in list(self.root.winfo_children()):
            child.destroy()
        self.__init__(self.root)
        self.root.geometry(geo)

    def _label(self, parent, text, **kw):
        font = kw.pop("font", ui(kw.pop("size", 11)))
        return tk.Label(parent, text=text, bg=BG, fg=FG, font=font, **kw)

    def _btn(self, parent, text, cmd, bg=BTN_BG, fg=FG, **kw):
        padx = kw.get("padx", 15)
        pady = kw.get("pady", 5)
        return _make_clickable_label(parent, text, cmd, bg=bg, fg=fg,
                                     hover_bg=BTN_ACTIVE, font=ui(10),
                                     padx=padx, pady=pady)

    def _accent_btn(self, parent, text, cmd, **kw):
        """主操作按钮（填充蓝，对应网页 .btn-primary）"""
        padx = kw.get("padx", 15)
        pady = kw.get("pady", 5)
        return _make_clickable_label(parent, text, cmd, bg=ACCENT, fg="white",
                                     hover_bg=ACCENT_H, font=ui(11, bold=True),
                                     padx=padx, pady=pady)

    # ---------- 卡片式布局组件（与网页端 reminder_web.html / reminder_ui.py 一致） ----------
    def _section(self, parent, text):
        """小标题（对应网页 .section-title：次要灰、加粗、上下留白）"""
        tk.Label(parent, text=text, bg=BG, fg=MUTED,
                 font=ui(12, bold=True)).pack(anchor="w", padx=12, pady=(16, 6))

    def _card(self, parent, padx=10, pady=8, **pack_kw):
        """白卡容器（SURFACE + 1px BORDER），内容放里面即呈卡片式。"""
        c = tk.Frame(parent, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        c.pack(padx=padx, pady=pady, fill=tk.BOTH, expand=True, **pack_kw)
        return c

    def _bind_click(self, widget, cb):
        """把点击绑定到整个卡片（含所有子控件），并变成手型光标。"""
        try:
            widget.bind("<Button-1>", lambda e: cb())
            widget.config(cursor="hand2")
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_click(child, cb)

    def _make_card(self, parent, title, hint=None, dot_color=None, on_click=None):
        """生成一张可点卡片（对应网页 .preset-card）：圆点 + 标题 + 可选副文案。"""
        card = tk.Frame(parent, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        head = tk.Frame(card, bg=BG2)
        head.pack(fill=tk.X, padx=14, pady=(12, 2))
        if dot_color:
            tk.Label(head, text="●", fg=dot_color, bg=BG2, font=ui(9)).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(head, text=title, bg=BG2, fg=FG, font=ui(13, bold=True)).pack(side=tk.LEFT)
        if hint:
            tk.Label(card, text=hint, bg=BG2, fg=MUTED, font=ui(11),
                     anchor="w").pack(fill=tk.X, padx=(32, 14), pady=(0, 12))
        if on_click:
            self._bind_click(card, on_click)
        return card

    # ==================== DAILY TAB ====================
    def build_daily_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text=t("tab_diary"))

        # 顶部：日期 + 模板/标签 按钮
        top = tk.Frame(tab, bg=BG)
        top.pack(fill=tk.X, padx=10, pady=(6, 0))
        self._label(top, f"  {get_today()}", font=ui(13, bold=True)).pack(side=tk.LEFT)
        self._btn(top, t("tags"), self.extract_and_show_tags, padx=8).pack(side=tk.RIGHT, padx=2)
        self._btn(top, t("template"), self.insert_template, padx=8).pack(side=tk.RIGHT, padx=2)

        # 编辑区卡片（白卡 + 卡内浅底输入框，对应网页 .field input）
        editor = self._card(tab)
        self.daily_text = scrolledtext.ScrolledText(editor, font=mono(13),
                                                     bg=BG, fg=FG, insertbackground=INPUT_INSERT,
                                                     wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
                                                     highlightthickness=0, padx=10, pady=10, takefocus=1)
        self.daily_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.daily_text.insert("1.0", load_daily(get_today()))

        # 底部：保存（主按钮）+ 标签显示
        bot = tk.Frame(tab, bg=BG)
        bot.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._accent_btn(bot, t("save"), self.save_daily, padx=18, pady=6).pack(side=tk.RIGHT)

        self.tag_display = tk.Label(bot, text="", bg=BG, fg=ACCENT2, font=ui(10))
        self.tag_display.pack(side=tk.LEFT)

    def _refocus(self, widget):
        """macOS 下点击按钮后文本框会失焦，需要显式恢复键盘焦点。"""
        try:
            widget.focus_set()
        except Exception:
            pass

    def insert_template(self):
        template = "\n## Done\n- \n\n## Thoughts\n- \n\n## Tomorrow\n- \n"
        self.daily_text.insert(tk.END, template)
        self._refocus(self.daily_text)

    def save_daily(self):
        content = self.daily_text.get("1.0", tk.END).strip()
        save_daily(get_today(), content)
        self.status.config(text=f"{t('diary_saved')} - {get_today()} {get_now()}", fg=ACCENT2)
        self._refocus(self.daily_text)

    def extract_and_show_tags(self):
        content = self.daily_text.get("1.0", tk.END)
        tags = extract_tags(content)
        if tags:
            self.tag_display.config(text=f"{t('tags')}: {', '.join(tags)}")
            self.status.config(text=t("extracted_tags", n=len(tags)), fg=ACCENT2)
        else:
            self.tag_display.config(text=t("no_tags"))
            self.status.config(text=t("no_keywords"), fg=MUTED)
        self._refocus(self.daily_text)

    # ==================== MOOD TAB ====================
    def build_mood_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text=t("tab_mood"))

        # 小标题
        self._section(tab, t("mood_q"))

        # 输入卡片
        inp = self._card(tab, pady=6)
        self.mood_input = scrolledtext.ScrolledText(inp, height=3, font=ui(12),
                                                      bg=BG, fg=FG, insertbackground=INPUT_INSERT,
                                                      wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
                                                      highlightthickness=0, padx=10, pady=8, takefocus=1)
        self.mood_input.pack(fill=tk.X, padx=8, pady=8)

        # 语音输入行（🎤 录音 → 识别填框 → 自动分析）
        vrow = tk.Frame(inp, bg=BG2)
        vrow.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.voice_btn = self._btn(vrow, t("voice"), self.on_voice_toggle, padx=14, pady=3)
        self.voice_btn.pack(side=tk.LEFT)
        # 麦克风权限帮助/一键重置入口
        self._btn(vrow, t("mic_perm_btn"), lambda: self._show_mic_permission_dialog(),
                  padx=8, pady=3, font=ui(11)).pack(side=tk.LEFT)
        # 识别后自动保存开关（持久化到 config/voice_autosave.txt）
        self.voice_autosave = tk.BooleanVar(value=voice_mood.load_autosave_pref())
        tk.Checkbutton(vrow, text=t("voice_autosave"), variable=self.voice_autosave,
                       command=lambda: voice_mood.save_autosave_pref(self.voice_autosave.get()),
                       bg=BG2, fg=MUTED, activebackground=BG2, activeforeground=FG,
                       selectcolor=BG2, font=ui(10),
                       cursor="hand2", bd=0, highlightthickness=0).pack(side=tk.RIGHT)
        self.voice_status = tk.Label(vrow, text="", bg=BG2, fg=MUTED, font=ui(10))
        self.voice_status.pack(side=tk.LEFT, padx=10)

        # 语音识别器（回调通过 root.after 抛回主线程）
        ffmpeg_ok, sr_ok = voice_mood.deps_status()
        self.voice_deps_ok = ffmpeg_ok and sr_ok
        self.voice_recorder = voice_mood.VoiceRecorder(
            on_status=lambda s, m: self.root.after(0, self.on_voice_status, s, m),
            on_result=lambda txt, acou=None: self.root.after(0, self.on_voice_result, txt, acou),
            on_error=lambda msg: self.root.after(0, self.on_voice_error, msg),
            on_acoustics=lambda acou: self.root.after(0, self.on_voice_acoustics, acou),
        )

        # 快捷心情（卡片式，对应网页 preset-card 网格）
        grid = tk.Frame(tab, bg=BG)
        grid.pack(fill=tk.X, padx=10, pady=(4, 0))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        for i, (mood, emoji) in enumerate(MOOD_EMOJI.items()):
            card = self._make_card(grid, f"{emoji} {mood}", dot_color=ACCENT,
                                   on_click=lambda m=mood: self.quick_mood(m))
            card.grid(row=i // 2, column=i % 2, padx=5, pady=5, sticky="nsew")

        # 分析按钮（主按钮）
        btn_frame = tk.Frame(tab, bg=BG)
        btn_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        self._accent_btn(btn_frame, t("auto_analyze"), self.analyze_mood_ui, padx=16, pady=6).pack(side=tk.LEFT)
        self.mood_result = tk.Label(btn_frame, text="", bg=BG, fg=ACCENT2, font=ui(12))
        self.mood_result.pack(side=tk.LEFT, padx=10)

        # 今日记录卡片
        self._section(tab, t("today_records"))
        hist = self._card(tab)
        self.mood_history = scrolledtext.ScrolledText(hist, height=8, font=mono(12),
                                                        bg=BG, fg=FG, wrap=tk.WORD, relief=tk.FLAT,
                                                        borderwidth=0, highlightthickness=0,
                                                        padx=10, pady=8, state=tk.DISABLED)
        self.mood_history.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.refresh_mood_history()

    def quick_mood(self, mood):
        text = self.mood_input.get("1.0", tk.END).strip()
        if not text:
            text = f"(quick: {mood})"
        save_mood(get_today(), mood, text, 1.0, "manual")
        self.mood_result.config(text=f"{MOOD_EMOJI.get(mood, '')} {mood} ✓")
        self.mood_input.delete("1.0", tk.END)
        self.refresh_mood_history()
        self.status.config(text=t("mood_saved", m=mood), fg=ACCENT2)
        self._refocus(self.mood_input)

    def analyze_mood_ui(self, acoustics=None):
        """分析心情，可融合声学特征。"""
        text = self.mood_input.get("1.0", tk.END).strip()
        if not text and not acoustics:
            self.mood_result.config(text=t("type_first"))
            self._refocus(self.mood_input)
            return

        # 文本分析
        text_mood, text_conf, text_reason = ("平静", 0, "")
        if text:
            text_mood, text_conf, text_reason = analyze_mood(text)

        # 声学分析
        acou_mood, acou_conf, acou_detail = (None, 0, "")
        if acoustics:
            acou_mood, acou_conf, acou_detail = voice_mood.acoustics_to_mood(acoustics)

        # 融合：文本分析为主（权重 0.6），声学为辅（权重 0.4）
        if acou_mood and text:
            # 两者都有：加权融合
            MOODS = list(MOOD_EMOJI.keys())
            combined_scores = {m: 0 for m in MOODS}
            combined_scores[text_mood] += text_conf * 0.6
            combined_scores[acou_mood] += acou_conf * 0.4
            best_mood = max(combined_scores, key=combined_scores.get)
            best_conf = min(combined_scores[best_mood], 1.0)
            reason_parts = []
            if text_reason and text_reason != "未检测到明显情绪词":
                reason_parts.append("文本: {}".format(text_reason))
            if acou_detail:
                reason_parts.append("声音: {}".format(acou_detail))
            reason = " | ".join(reason_parts) if reason_parts else acou_detail or text_reason
        elif acou_mood and not text:
            # 只有声学分析（文字识别失败）
            best_mood = acou_mood
            best_conf = acou_conf
            reason = "声音分析: {}".format(acou_detail)
        else:
            # 只有文本分析
            best_mood = text_mood
            best_conf = text_conf
            reason = text_reason

        save_text = text if text else "(语音: {})".format(acou_detail[:50])
        save_mood(get_today(), best_mood, save_text, best_conf, reason)
        emoji = MOOD_EMOJI.get(best_mood, "")
        # 显示更丰富的结果
        detail = ""
        if acou_mood and text_mood and acou_mood != text_mood:
            detail = " (文本→{} 声音→{})".format(text_mood, acou_mood)
        self.mood_result.config(text=f"{emoji} {best_mood} ({best_conf:.0%}){detail}")
        self.mood_input.delete("1.0", tk.END)
        self.refresh_mood_history()
        self.status.config(text=t("mood_saved", m=f"{best_mood} ({best_conf:.0%})"), fg=ACCENT2)
        self._refocus(self.mood_input)

    # ---------- 语音识别心情 ----------
    def _voice_lang(self):
        return "zh-CN" if LANG == "zh" else "en-US"

    def on_voice_toggle(self):
        if not getattr(self, "voice_deps_ok", False):
            ffmpeg_ok, sr_ok = voice_mood.deps_status()
            if not (ffmpeg_ok and sr_ok):
                need = []
                if not ffmpeg_ok:
                    need.append(t("voice_missing_ffmpeg"))
                if not sr_ok:
                    need.append(t("voice_missing_sr"))
                if not messagebox.askyesno("语音依赖缺失",
                                           t("voice_confirm_install").format(n="、".join(need))):
                    return
                self._start_voice_install()
                return
        if self.voice_recorder.running:
            self.voice_recorder.stop()
            # 立即更新 UI，不等后台回调（避免按钮卡在"停止"状态）
            self.voice_btn.config(text=t("voice"))
            self.voice_status.config(text=t("voice_cancel"))
            self.status.config(text=t("voice_cancel"), fg=MUTED)
            return
        self.voice_btn.config(text=t("voice_stop"))
        self.voice_status.config(text=t("voice_recording").format(n=voice_mood.MAX_SECONDS))
        self.status.config(text=t("voice_recording").format(n=voice_mood.MAX_SECONDS), fg=MUTED)
        self.voice_recorder.start(lang=self._voice_lang())

    # ---------- 语音依赖自动安装 ----------
    def _start_voice_install(self):
        """在后台线程跑 pip 安装，按钮置灰并显示进度；主线程轮询取结果。"""
        self.voice_btn.set_enabled(False)
        self.voice_btn.config(text=t("voice_installing"))
        self.voice_status.config(text=t("voice_installing"))
        self.status.config(text=t("voice_installing"), fg=MUTED)
        self._voice_install_result = None
        threading.Thread(target=self._install_voice_deps, daemon=True).start()
        # 主线程调度首次轮询（避免跨线程直接调用 after）
        self.root.after(150, self._poll_voice_install)

    def _install_voice_deps(self):
        try:
            self._voice_install_result = voice_mood.auto_install_deps()
        except Exception as e:
            self._voice_install_result = (False, False, ["安装异常：{}".format(e)])

    def _poll_voice_install(self):
        if self._voice_install_result is None:
            self.root.after(150, self._poll_voice_install)
            return
        ffmpeg_ok, sr_ok, notes = self._voice_install_result
        self._voice_install_result = None
        self._on_voice_install_done(ffmpeg_ok, sr_ok, notes)

    def _on_voice_install_done(self, ffmpeg_ok, sr_ok, notes):
        self.voice_btn.set_enabled(True)
        ok = ffmpeg_ok and sr_ok
        self.voice_deps_ok = ok
        if ok:
            self.voice_status.config(text=t("voice_install_ok"))
            self.status.config(text=t("voice_install_ok"), fg=ACCENT2)
            self.on_voice_toggle()  # 依赖就绪，直接开始录音
            return
        detail = t("voice_install_fail")
        if not ffmpeg_ok:
            detail += "\n" + t("voice_need_ffmpeg")
        if not sr_ok:
            detail += "\n" + t("voice_need_sr").format(py=sys.executable)
        if notes:
            detail += "\n\n" + "\n".join(notes)
        messagebox.showerror("语音依赖安装失败", detail)

    def on_voice_result(self, text, acoustics=None):
        # 填入心情输入框（只有有文字时才填）
        if text:
            try:
                cur = self.mood_input.get("1.0", tk.END).strip()
                if cur:
                    self.mood_input.insert(tk.END, "\n" + text)
                else:
                    self.mood_input.insert("1.0", text)
            except Exception:
                pass
        self.voice_btn.config(text=t("voice"))
        # 显示识别到的文字或声学特征
        if text:
            display_text = text[:40] + ("…" if len(text) > 40 else "")
        else:
            # 文字识别失败，显示声音特征摘要
            acou_mood, acou_conf, acou_detail = voice_mood.acoustics_to_mood(acoustics)
            display_text = "声音→{} ({})".format(acou_mood, acou_detail[:30])
        # 识别后：开关开则自动分析保存；否则仅填入等用户检查再手动保存
        if self.voice_autosave.get():
            try:
                self.voice_status.config(text="已识别：{}".format(display_text))
            except Exception:
                pass
            self.status.config(text="已识别：{}".format(display_text), fg=ACCENT2)
            self.analyze_mood_ui(acoustics=acoustics)
        else:
            try:
                self.voice_status.config(text="已填入：{}".format(display_text))
            except Exception:
                pass
            self.status.config(text="已填入，请检查后保存", fg=ACCENT2)
            self._refocus(self.mood_input)

    def on_voice_acoustics(self, features):
        """声学分析结果回调，在识别前先显示声音特征。"""
        try:
            acou_mood, acou_conf, acou_detail = voice_mood.acoustics_to_mood(features)
            emoji = MOOD_EMOJI.get(acou_mood, "")
            self.voice_status.config(
                text="声音特征: {} {} {}".format(emoji, acou_mood, acou_detail[:20] if acou_detail else ""))
        except Exception:
            pass

    def on_voice_error(self, msg):
        self.voice_btn.config(text=t("voice"))
        try:
            self.voice_status.config(text=msg)
        except Exception:
            pass
        self.status.config(text=msg, fg="orange")
        # 麦克风权限被拒：自动弹出帮助/重置对话框
        low = (msg or "").lower()
        if "麦克风权限被拒绝" in (msg or "") or "microphone" in low or "operation not permitted" in low:
            self._show_mic_permission_dialog()

    def on_voice_status(self, state, msg):
        if state == "recording":
            self.voice_btn.config(text=t("voice_stop"))
        elif state in ("idle", "done"):
            self.voice_btn.config(text=t("voice"))
        try:
            self.voice_status.config(text=msg)
        except Exception:
            pass

    # ---------- 麦克风权限帮助 / 一键重置 ----------
    def _show_mic_permission_dialog(self):
        """弹出麦克风权限说明与「一键重置」对话框（macOS）。"""
        dlg = tk.Toplevel(self.root)
        dlg.title(t("mic_perm_title"))
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)
        try:
            dlg.configure(bg=BG)
        except Exception:
            pass

        pad = {"padx": 16, "pady": 12}
        tk.Label(dlg, text=t("mic_perm_help"), justify=tk.LEFT, wraplength=400,
                 bg=BG, fg=FG, font=ui(11)).pack(anchor=tk.W, **pad)

        btn_row = tk.Frame(dlg, bg=BG)
        btn_row.pack(fill=tk.X, padx=16, pady=(0, 14))
        self._accent_btn(btn_row, t("mic_perm_reset"),
                         lambda: self._reset_mic_permission(dlg), padx=12, pady=5).pack(side=tk.LEFT)
        self._btn(btn_row, t("close"), dlg.destroy, padx=12, pady=5).pack(side=tk.LEFT, padx=(8, 0))

        # 居中显示
        dlg.update_idletasks()
        w, h = dlg.winfo_width(), dlg.winfo_height()
        pw, ph = self.root.winfo_x(), self.root.winfo_y()
        dlg.geometry("+{}+{}".format(pw + (self.root.winfo_width() - w) // 2,
                                     ph + (self.root.winfo_height() - h) // 2))

    def _reset_mic_permission(self, dlg):
        """执行 tccutil reset Microphone（仅 macOS），随后提示重启。"""
        import subprocess
        if sys.platform != "darwin":
            dlg.grab_release()
            dlg.destroy()
            messagebox.showinfo(t("mic_perm_title"), t("mic_perm_only_mac"))
            return
        try:
            res = subprocess.run(["tccutil", "reset", "Microphone"],
                                 capture_output=True, text=True, timeout=20)
            ok = res.returncode == 0
            detail = (res.stderr or res.stdout or "").strip()
        except Exception as e:
            ok, detail = False, str(e)
        dlg.grab_release()
        dlg.destroy()
        if ok:
            messagebox.showinfo(t("mic_perm_title"), t("mic_perm_reset_ok"))
        else:
            extra = "\n\n{}".format(detail[:300]) if detail else ""
            messagebox.showerror(t("mic_perm_title"), t("mic_perm_reset_fail") + extra)

    def _stop_voice_if_running(self):
        rec = getattr(self, "voice_recorder", None)
        if rec is not None and rec.running:
            try:
                rec.stop()
            except Exception:
                pass

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
            self.mood_history.insert("1.0", t("no_records"))
        self.mood_history.config(state=tk.DISABLED)

    # ==================== REMINDER TAB ====================
    def build_reminder_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text=t("tab_reminder"))

        # 小标题
        self._section(tab, t("quick_reminders"))

        # 预设卡片（2 列网格，对应网页 preset-grid）
        grid = tk.Frame(tab, bg=BG)
        grid.pack(fill=tk.X, padx=10, pady=(0, 4))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        preset_items = [
            ("+1h", 1, "快速稍后提醒"),
            ("+2h", 2, "午间 / 会议"),
            ("+3h", 3, "下午安排"),
            (t("tmr9"), "tmr9", "晨间待办"),
            (t("tmr18"), "tmr18", "下班提醒"),
        ]
        for i, (label, val, hint) in enumerate(preset_items):
            card = self._make_card(grid, label, hint, dot_color=ACCENT,
                                   on_click=lambda v=val: self.preset_reminder(v))
            card.grid(row=i // 2, column=i % 2, padx=5, pady=5, sticky="nsew")

        # 自定义提醒卡片
        ccard = self._card(tab, pady=6)
        head = tk.Frame(ccard, bg=BG2)
        head.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(head, text=t("custom"), bg=BG2, fg=FG, font=ui(11, bold=True)).pack(side=tk.LEFT)
        row = tk.Frame(ccard, bg=BG2)
        row.pack(fill=tk.X, padx=12, pady=(0, 10))
        self.reminder_msg = tk.Entry(row, font=ui(11), bg=BG, fg=FG,
                                      insertbackground=INPUT_INSERT, relief=tk.FLAT, width=22)
        self.reminder_msg.pack(side=tk.LEFT, padx=(0, 6))
        self.reminder_time = tk.Entry(row, font=ui(11), bg=BG, fg=FG,
                                       insertbackground=INPUT_INSERT, relief=tk.FLAT, width=12)
        self.reminder_time.insert(0, "HH:MM")
        self.reminder_time.pack(side=tk.LEFT, padx=(0, 6))
        self._accent_btn(row, t("add"), self.add_custom_reminder, padx=12, pady=3).pack(side=tk.LEFT)

        # 待提醒卡片列表
        self._section(tab, t("pending"))
        self._build_pending_cards(tab)

        # 取消提醒
        bot = tk.Frame(tab, bg=BG)
        bot.pack(fill=tk.X, padx=10, pady=(6, 10))
        self._label(bot, t("cancel_id"), size=10).pack(side=tk.LEFT)
        self.cancel_id = tk.Entry(bot, font=ui(10), bg=BG, fg=FG,
                                    insertbackground=INPUT_INSERT, relief=tk.FLAT, width=6)
        self.cancel_id.pack(side=tk.LEFT, padx=5)
        self._btn(bot, t("cancel"), self.cancel_reminder_ui, padx=10).pack(side=tk.LEFT, padx=5)

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
        self.status.config(text=t("reminder_set", t=target.strftime('%H:%M'), m=msg), fg=ACCENT2)
        self.refresh_reminder_list()

    def add_custom_reminder(self):
        msg = self.reminder_msg.get().strip()
        time_str = self.reminder_time.get().strip()
        if not msg:
            self.status.config(text=t("enter_msg"), fg="orange")
            return
        try:
            h, m = map(int, time_str.split(":"))
            target = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= datetime.now():
                target += timedelta(days=1)
            add_reminder(target, msg)
            self.status.config(text=t("reminder_set", t=target.strftime('%H:%M'), m=msg), fg=ACCENT2)
            self.refresh_reminder_list()
        except ValueError:
            self.status.config(text=t("bad_time"), fg="orange")

    def cancel_reminder_ui(self):
        try:
            rid = int(self.cancel_id.get().strip())
            if cancel_reminder(rid):
                self.status.config(text=t("reminder_cancelled", i=rid), fg=ACCENT2)
                self.refresh_reminder_list()
            else:
                self.status.config(text=t("cannot_cancel", i=rid), fg="orange")
        except ValueError:
            self.status.config(text=t("enter_id"), fg="orange")

    def _build_pending_cards(self, parent):
        """可滚动的待提醒卡片列表容器（对应网页 .pending-list）"""
        outer = self._card(parent, pady=0)
        self.rem_canvas = tk.Canvas(outer, bg=BG2, highlightthickness=0)
        self.rem_scroll = tk.Scrollbar(outer, command=self.rem_canvas.yview)
        self.rem_inner = tk.Frame(self.rem_canvas, bg=BG2)
        self.rem_canvas.create_window((0, 0), window=self.rem_inner, anchor="nw")
        self.rem_canvas.configure(yscrollcommand=self.rem_scroll.set)
        self.rem_canvas.pack(side="left", fill="both", expand=True)
        self.rem_scroll.pack(side="right", fill="y")

    def refresh_reminder_list(self):
        for w in list(self.rem_inner.winfo_children()):
            w.destroy()
        reminders = load_reminders()
        pending = [r for r in reminders if r["status"] == "pending"]
        if not pending:
            tk.Label(self.rem_inner, text=t("no_pending"), bg=BG2, fg=MUTED,
                     font=ui(11)).pack(fill=tk.X, padx=14, pady=14)
        else:
            for r in pending:
                card = tk.Frame(self.rem_inner, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
                card.pack(fill=tk.X, padx=14, pady=6)
                tk.Label(card, text="#{}  {}".format(r["id"], r["remind_at"]),
                         font=ui(12, bold=True), bg=BG2, fg=ACCENT).pack(anchor="w", padx=14, pady=(10, 2))
                tk.Label(card, text=r["message"], font=ui(13), bg=BG2, fg=FG,
                         wraplength=320, justify="left").pack(anchor="w", padx=14, pady=(0, 10))
        self.rem_inner.update_idletasks()
        self.rem_canvas.configure(scrollregion=self.rem_canvas.bbox("all"))

    # ==================== SHARE TAB (Obsidian × All Agents) ====================
    def _shared_modules(self):
        """懒加载共享 Wiki 模块，返回 (wiki_core, agent_registry, obsidian_bridge) 或 None"""
        try:
            shared = os.path.join(_SCRIPT_DIR, "modules", "shared-wiki")
            if shared not in sys.path:
                sys.path.insert(0, shared)
            import wiki_core as _wc
            import agent_registry as _ar
            import obsidian_bridge as _ob
            return _wc, _ar, _ob
        except Exception as e:
            messagebox.showerror("Shared module error",
                                 "无法加载共享 Wiki 模块 (modules/shared-wiki):\n{}".format(e))
            return None

    def build_share_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text=t("tab_share"))

        # ---- 顶部说明 ----
        head = tk.Frame(tab, bg=BG)
        head.pack(fill=tk.X, padx=10, pady=(10, 4))
        self._label(head, t("share_title"),
                    font=ui(12, bold=True)).pack(side=tk.LEFT)
        self._btn(head, t("refresh"), self.share_refresh,
                  bg=BTN_BG, fg=FG, padx=10).pack(side=tk.RIGHT)

        # ---- 可拖拽分隔的上下两栏：上=内容框，下=操作按钮 ----
        # 用 PanedWindow 提供可鼠标拖拽的分隔条，让内容框能手动调整大小
        pw = tk.PanedWindow(tab, orient=tk.VERTICAL, bg=BG,
                            sashwidth=6, sashrelief=tk.RAISED,
                            showhandle=True, handlepad=10, handlesize=10)
        pw.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        # 状态区（内容框，可拖拽分隔条改变高度）— 白卡 + 卡内浅底
        status = tk.Frame(pw, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        self.share_status = scrolledtext.ScrolledText(status, height=9, font=mono(11),
                                                      bg=BG, fg=FG, insertbackground=INPUT_INSERT,
                                                      wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
                                                      highlightthickness=0,
                                                      padx=8, pady=6, state=tk.DISABLED)
        self.share_status.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        pw.add(status, minsize=120, height=360)

        # ---- 操作按钮（放在下方，可拖拽分隔条调整上方内容框大小） ----
        acts = tk.Frame(pw, bg=BG)
        self._accent_btn(acts, t("start_server"), self.share_start_server, padx=12).pack(side=tk.LEFT, padx=3)
        self._btn(acts, t("open_obsidian"), self.share_open_obsidian,
                  bg=BTN_BG, fg=FG, padx=12).pack(side=tk.LEFT, padx=3)
        self._btn(acts, t("broadcast"), self.share_broadcast,
                  bg=BTN_BG, fg=FG, padx=12).pack(side=tk.LEFT, padx=3)
        pw.add(acts, minsize=40)

        # 初始填充
        self.share_refresh()

    def share_set_status(self, text):
        self.share_status.config(state=tk.NORMAL)
        self.share_status.delete("1.0", tk.END)
        self.share_status.insert(tk.END, text)
        self.share_status.config(state=tk.DISABLED)

    def share_refresh(self):
        """刷新 Agent 与 Obsidian 状态"""
        mods = self._shared_modules()
        if not mods:
            return
        _wc, _ar, _ob = mods
        lines = []
        # Obsidian
        try:
            vaults = _ob.discover_vaults()
            wiki_v = _ob.detect_wiki_vault()
            if wiki_v:
                lines.append("📓 Obsidian Vault: {}  (已连接)".format(wiki_v["name"]))
            else:
                cfg_v = _ob.vault_name()
                if cfg_v and cfg_v != "my-wiki":
                    lines.append("📓 Obsidian Vault: {}  (按 config/obsidian.json)".format(cfg_v))
                else:
                    lines.append("📓 Obsidian: 未在本机以 Vault 打开当前 wiki")
                    lines.append("   → 在 config/obsidian.json 配置 vault_name / vault_path")
            lines.append("   发现 {} 个本地 Vault".format(len(vaults)))
        except Exception as e:
            lines.append("📓 Obsidian: 检测失败 ({})".format(e))
        lines.append("")
        # Agents
        try:
            agents = _ar.discover()
            lines.append("🤖 发现的 Agent ({} 个):".format(len(agents)))
            for a in agents:
                caps = ",".join(a.get("capabilities", [])[:3]) or "-"
                lines.append("  • {}  [{}]  {}".format(a["name"], a["status"], caps))
        except Exception as e:
            lines.append("🤖 Agent 发现失败: {}".format(e))
        lines.append("")
        lines.append("Wiki root: {}".format(_wc.WIKI_ROOT))
        lines.append("笔记数: {}".format(len(_wc.list_notes())))
        self.share_set_status("\n".join(lines))

    def share_start_server(self):
        """后台启动 MCP Server（让所有 Agent 可接入共享 Wiki）"""
        mods = self._shared_modules()
        if not mods:
            return
        _wc, _ar, _ob = mods
        server_py = os.path.join(_SCRIPT_DIR, "modules", "shared-wiki", "mcp_server.py")
        if not os.path.exists(server_py):
            messagebox.showerror("Error", "找不到 mcp_server.py")
            return
        # 启动前检测依赖：mcp 未安装会导致子进程静默退出
        try:
            import mcp  # noqa: F401
        except ImportError:
            messagebox.showerror(
                "缺少依赖: mcp",
                "当前 Python 环境未安装 mcp 包，MCP Server 无法启动。\n\n"
                "请先安装依赖:\n"
                "  {} -m pip install mcp\n\n"
                "安装后再点此按钮启动。".format(sys.executable))
            return
        try:
            # 后台启动，不阻塞 GUI（stderr 写入日志便于排错）
            log_path = os.path.join(WIKI_DIR, "mcp_server.log")
            log_f = open(log_path, "w")
            proc = subprocess.Popen([sys.executable, server_py],
                                    stdout=log_f, stderr=subprocess.STDOUT)
            self._mcp_proc = proc
            self.status.config(text="MCP Server 已启动 (pid={})".format(proc.pid))
            messagebox.showinfo("MCP Server",
                                "MyWiki MCP Server 已在后台启动。\n\n"
                                "在你的 Agent 宿主 (Claude Desktop / Cursor / OpenClaw) 配置:\n"
                                '  command: {}\n  args: ["{}"]'.format(sys.executable, server_py))
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    def share_open_obsidian(self):
        """在 Obsidian 中打开今日日记"""
        mods = self._shared_modules()
        if not mods:
            return
        _wc, _ar, _ob = mods
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            cmd = _ob.open_note("daily/{}".format(today))
            self.status.config(text="已在 Obsidian 打开 {}".format(today))
        except Exception as e:
            messagebox.showerror("打开失败", str(e))

    def share_broadcast(self):
        """向所有 Agent 广播 Wiki 更新"""
        mods = self._shared_modules()
        if not mods:
            return
        _wc, _ar, _ob = mods
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            _ar.discover()
            result = _ar.broadcast("wiki.updated", {"rel": "daily/{}.md".format(today)})
            sent, failed, skipped = result["sent"], result["failed"], result["skipped"]
            if sent or failed:
                msg = ("通知完成\n\n已发布更新: daily/{}.md\n\n".format(today) +
                       "✅ 已推送 ({}): {}\n".format(len(sent), ", ".join(sent) or "无") +
                       "❌ 失败 ({}): {}\n".format(len(failed), ", ".join(failed) or "无") +
                       "⏭ 跳过 ({}): {}\n".format(len(skipped), ", ".join(skipped) or "无") +
                       "\n说明: 仅支持 webhook 的 Agent 会真正收到更新；"
                       "模型服务(Ollama/LM-Studio)与文件同步型(Obsidian/OpenClaw 等)不参与通知。")
            else:
                msg = ("通知完成，但本次没有可接收的 Agent（不是错误）。\n\n"
                       "已发布更新: daily/{}.md\n\n".format(today) +
                       "当前跳过项:\n  · " + "\n  · ".join(skipped) + "\n\n" +
                       "含义:\n"
                       "  - Ollama-API / LM-Studio-API: 仅用于探测本地模型服务，不接收通知\n"
                       "  - OpenClaw / Claude / Cursor / Memo / Obsidian: 通过共享文件同步，无需通知\n\n"
                       "当你有 Agent 暴露 http://host:port/webhook 并登记后，才会真正推送过去。")
            self.status.config(text="已通知 Agent")
            messagebox.showinfo("通知 Agent", msg)
            self.share_refresh()
        except Exception as e:
            messagebox.showerror("广播失败", str(e))


# ==================== MAIN ====================
if __name__ == "__main__":
    # 整个进程只有一个 Tk() 根实例
    root = tk.Tk()

    # 构建主界面（先绘制，确保输入框始终可见可交互）
    app = WikiApp(root)
    root.update_idletasks()

    # 在首个主循环刷新后显示非模态欢迎框（Toplevel，单根单 mainloop）
    # 欢迎框不再 grab，主界面在其背后依然可点击、可输入
    root.after(200, show_welcome_and_check, root)

    # Start main loop / 启动主事件循环
    root.mainloop()
