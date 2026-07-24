#!/usr/bin/env python3
"""
My Wiki - All-in-One Personal Knowledge Tool
日记 | 心情 | 提醒 | 标签

PySide6 版本 —— 替代原 Tkinter 实现。
PySide6 的信号槽机制天然线程安全，子线程可通过信号把结果投递到主线程，
不再需要手动轮询队列。
"""
import os
import json
import subprocess
import sys
import re
import shutil
import urllib.request
import tempfile
import threading
from datetime import datetime, timedelta
from collections import Counter

from PySide6.QtCore import Qt, Signal, QObject, QThread, QTimer, QSize
from PySide6.QtGui import QFont, QAction, QShortcut, QKeySequence, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QPlainTextEdit, QLineEdit, QCheckBox,
    QScrollArea, QFrame, QMessageBox, QProgressDialog, QDialog, QSplitter,
    QSizePolicy, QSpacerItem
)

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
    return False, None


def check_openclaw():
    """检测 OpenClaw 是否安装（跨平台）。"""
    candidates = []
    if sys.platform == "darwin":
        candidates = [
            "/Applications/OpenClaw.app",
            "/usr/local/bin/openclaw",
            "/opt/homebrew/bin/openclaw",
            os.path.expanduser("~/.local/bin/openclaw"),
            os.path.expanduser("~/.npm-global/bin/openclaw"),
            os.path.expanduser("~/.cargo/bin/openclaw"),
            os.path.expanduser("~/Library/Application Support/QClaw/openclaw"),
            os.path.expanduser("~/Library/Application Support/QClaw/openclaw/node_modules/.bin/openclaw"),
        ]
    elif sys.platform == "win32":
        candidates = [
            r"C:\Users\{}\AppData\Local\Programs\openclaw\openclaw.exe".format(os.getenv("USERNAME")),
            r"C:\Program Files\QClaw\openclaw.exe",
            r"C:\Program Files (x86)\QClaw\openclaw.exe",
        ]
    try:
        out = subprocess.run(["npm", "prefix", "-g"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            candidates.append(os.path.join(out.stdout.strip(), "bin", "openclaw"))
    except Exception:
        pass
    found = shutil.which("openclaw")
    if found:
        candidates.insert(0, found)
    for c in candidates:
        if c.endswith(".app"):
            if os.path.exists(c):
                return True, c
            continue
        if os.path.exists(c):
            return True, c
    return False, None


# ==================== PATHS ====================
from pathlib import Path as _Path
_SCRIPT_DIR = _Path(__file__).parent
def _resolve_wiki_dir():
    """wiki 数据根目录。

    优先级: 环境变量 MYWIKI_ROOT > config/obsidian.json 的 vault_path (Obsidian vault) > 仓库根(_SCRIPT_DIR)。
    """
    env = os.environ.get("MYWIKI_ROOT")
    if env and os.path.isdir(os.path.expanduser(env)):
        return os.path.expanduser(env)
    cfg = os.path.join(_SCRIPT_DIR, "config", "obsidian.json")
    if os.path.exists(cfg):
        try:
            vp = json.load(open(cfg, encoding="utf-8")).get("vault_path", "")
            if vp and os.path.isdir(os.path.expanduser(vp)):
                return os.path.expanduser(vp)
        except Exception:
            pass
    return str(_SCRIPT_DIR)

WIKI_DIR = _resolve_wiki_dir()

def _resolve_app_icon():
    cands = []
    if sys.platform == "darwin":
        cands.append(os.path.join(_SCRIPT_DIR, "assets", "AppIcon.icns"))
    cands.append(os.path.join(_SCRIPT_DIR, "icon.ico"))
    cands.append(os.path.join(_SCRIPT_DIR, "icon.png"))
    for c in cands:
        if os.path.exists(c):
            return c
    return ""

ICON_PATH = _resolve_app_icon()
DAILY_DIR = os.path.join(WIKI_DIR, "daily")
MOOD_DIR = os.path.join(WIKI_DIR, "mood")
REMINDER_DIR = os.path.join(WIKI_DIR, "reminders")
REMINDER_FILE = os.path.join(REMINDER_DIR, "reminders.json")

# ==================== THEME ====================
from theme import get_tokens, load_theme_pref, save_theme_pref
import voice_mood

MODE = load_theme_pref()

def get_theme_colors(mode=None):
    """返回主题色 dict，供 QSS 样式表使用。"""
    T = get_tokens(mode or MODE)
    return T

def apply_qss(app, mode=None):
    """生成并应用 QSS 全局样式表。"""
    T = get_theme_colors(mode)
    bg = T["BG"]
    surface = T["SURFACE"]
    text = T["TEXT"]
    text2 = T["TEXT2"]
    accent = T["ACCENT"]
    accent_h = T["ACCENT_H"]
    border = T["BORDER"]
    btn_hover = T["BTN_HOVER"]
    green = T["GREEN"]
    orange = T["ORANGE"]

    qss = f"""
    QMainWindow, QWidget {{
        background-color: {bg};
        color: {text};
        font-family: {UI_FONT};
        font-size: {int(12 * FONT_SCALE)}px;
    }}
    QTabWidget::pane {{
        border: 1px solid {border};
        border-radius: 6px;
        top: -1px;
    }}
    QTabBar::tab {{
        background: {surface};
        color: {text};
        padding: 10px 24px;
        margin-right: 2px;
        border: 1px solid {border};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        font-size: {int(13 * FONT_SCALE)}px;
    }}
    QTabBar::tab:selected {{
        background: {accent};
        color: white;
    }}
    QTabBar::tab:hover:!selected {{
        background: {btn_hover};
    }}
    QPushButton {{
        background-color: {surface};
        color: {text};
        border: 1px solid {border};
        border-radius: 5px;
        padding: 7px 16px;
        font-size: {int(11 * FONT_SCALE)}px;
    }}
    QPushButton:hover {{
        background-color: {btn_hover};
    }}
    QPushButton:pressed {{
        background-color: {accent_h};
    }}
    QPushButton[primary="true"] {{
        background-color: {accent};
        color: white;
        border: none;
        font-weight: bold;
        font-size: {int(12 * FONT_SCALE)}px;
        padding: 8px 18px;
    }}
    QPushButton[primary="true"]:hover {{
        background-color: {accent_h};
    }}
    QPlainTextEdit, QLineEdit {{
        background-color: {bg};
        color: {text};
        border: 1px solid {border};
        border-radius: 4px;
        padding: 6px;
        font-size: {int(12 * FONT_SCALE)}px;
    }}
    QPlainTextEdit:focus, QLineEdit:focus {{
        border: 1px solid {accent};
    }}
    QCheckBox {{
        color: {text2};
        font-size: {int(10 * FONT_SCALE)}px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
    }}
    QLabel {{
        color: {text};
        background: transparent;
    }}
    QScrollArea {{
        border: none;
        background: {surface};
    }}
    QScrollBar:vertical {{
        background: {surface};
        width: 10px;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background: {border};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {accent};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0;
    }}
    QSplitter::handle {{
        background: {border};
        height: 3px;
    }}
    QSplitter::handle:hover {{
        background: {accent};
    }}
    """
    app.setStyleSheet(qss)


# ==================== FONTS ====================
if sys.platform == "darwin":
    UI_FONT = "PingFang SC"
    MONO_FONT = "Menlo"
elif sys.platform.startswith("win"):
    UI_FONT = "Microsoft YaHei UI"
    MONO_FONT = "Consolas"
else:
    UI_FONT = "Noto Sans CJK SC"
    MONO_FONT = "DejaVu Sans Mono"

FONT_SCALE = 1.2

def ui_font(size, bold=False):
    sz = int(round(size * FONT_SCALE))
    f = QFont(UI_FONT, sz)
    f.setBold(bold)
    return f

def mono_font(size):
    return QFont(MONO_FONT, int(round(size * FONT_SCALE)))


# ==================== I18N ====================
LANG = "zh"
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
        "mic_perm_help": "若录音失败或提示「麦克风权限被拒绝」：\n\n1) 打开「系统设置 › 隐私与安全性 › 麦克风」，给运行本程序的终端/应用开启权限；\n2) 或点击下方「一键重置」清空授权，重启后重新弹窗允许；\n3) 完全退出 MyWiki 后重新打开再试。",
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
        "voice_need_sr": "Voice recognition needs SpeechRecognition\n\nInstall:\n  {py} -m pip install SpeechRecognition\n\nUses Google's online API (needs internet).",
        "mic_perm_btn": "🔧",
        "mic_perm_title": "Microphone Permission",
        "mic_perm_help": "If recording fails or you see 'microphone permission denied':\n\n1) Open System Settings › Privacy & Security › Microphone and enable the app;\n2) Or click 'Reset' below to clear authorization;\n3) Fully quit MyWiki and reopen before retrying.",
        "mic_perm_reset": "🔄 Reset Microphone Permission",
        "mic_perm_reset_ok": "Microphone authorization reset. Fully quit MyWiki, reopen, and allow access when prompted.",
        "mic_perm_reset_fail": "Reset failed. Please enable microphone in System Settings › Privacy & Security › Microphone.",
        "mic_perm_only_mac": "One-click reset is macOS only. Please enable microphone manually.",
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

def extract_tags(text, top_n=5):
    words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', text)
    words = [w for w in words if w not in STOP_WORDS and 2 <= len(w) <= 4 and not w.isdigit()]
    counts = Counter(words)
    domain = [(kw, 10) for kw in DOMAIN_KEYWORDS if kw in text]
    normal = counts.most_common(top_n * 2)
    all_kw = sorted(domain + normal, key=lambda x: x[1], reverse=True)
    return [t[0] for t in all_kw[:top_n]]

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
    reminder = {
        "id": rid,
        "remind_at": remind_at.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending",
    }
    reminders.append(reminder)
    save_reminders(reminders)
    return reminder

def cancel_reminder(rid):
    reminders = load_reminders()
    for r in reminders:
        if r["id"] == rid and r["status"] == "pending":
            r["status"] = "cancelled"
            save_reminders(reminders)
            return True
    return False


# ==================== 线程安全的语音信号中继 ====================
class VoiceSignals(QObject):
    """语音识别的信号中继：子线程 emit 信号 → 主线程槽函数执行。
    PySide6 的信号槽默认是队列连接（跨线程时自动排队），天然线程安全。
    """
    status_update = Signal(str, str)      # state, msg
    result_ready = Signal(object, object)  # text(str|None), acoustics(dict|None)
    error_occurred = Signal(str)           # msg
    acoustics_ready = Signal(object)       # features dict


# ==================== GUI APP ====================
class WikiApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("app_title"))
        self.setMinimumSize(760, 620)

        # 最大化窗口
        self.showMaximized()

        # 设置窗口图标
        if ICON_PATH and os.path.exists(ICON_PATH):
            try:
                self.setWindowIcon(QIcon(ICON_PATH))
            except Exception:
                pass

        # 语音信号中继（线程安全）
        self.voice_signals = VoiceSignals()
        self.voice_signals.status_update.connect(self.on_voice_status)
        self.voice_signals.result_ready.connect(self.on_voice_result)
        self.voice_signals.error_occurred.connect(self.on_voice_error)
        self.voice_signals.acoustics_ready.connect(self.on_voice_acoustics)

        # 语音识别器
        ffmpeg_ok, sr_ok = voice_mood.deps_status()
        self.voice_deps_ok = ffmpeg_ok and sr_ok
        self.voice_recorder = voice_mood.VoiceRecorder(
            on_status=lambda s, m: self.voice_signals.status_update.emit(s, m),
            on_result=lambda txt, acou=None: self.voice_signals.result_ready.emit(txt, acou),
            on_error=lambda msg: self.voice_signals.error_occurred.emit(msg),
            on_acoustics=lambda acou: self.voice_signals.acoustics_ready.emit(acou),
        )

        # 构建界面
        self._build_ui()

        # 快捷键
        save_sc = QShortcut(QKeySequence("Ctrl+S"), self)
        save_sc.activated.connect(self.save_daily)

        # 启动后聚焦日记编辑器
        QTimer.singleShot(100, lambda: self.daily_text.setFocus())

    # ==================== UI 构建 ====================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 6, 8, 4)
        layout.setSpacing(4)

        # 顶部工具条
        self._build_topbar(layout)

        # 标签页
        self.nb = QTabWidget()
        layout.addWidget(self.nb, stretch=1)

        self._build_daily_tab()
        self._build_mood_tab()
        self._build_reminder_tab()
        self._build_share_tab()

        # 状态栏
        self.status_label = QLabel(t("ready"))
        self.status_label.setStyleSheet("color: #888; padding: 2px 8px;")
        layout.addWidget(self.status_label)

    def _build_topbar(self, parent_layout):
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(4, 2, 4, 2)
        bar_layout.setSpacing(4)

        title = QLabel("📝 " + t("app_title"))
        title.setStyleSheet(f"color: {get_theme_colors()['ACCENT']}; font-weight: bold; font-size: {int(15*FONT_SCALE)}px;")
        bar_layout.addWidget(title)
        bar_layout.addStretch()

        theme_icon = "🌙" if MODE == "light" else "☀️"
        self.theme_btn = QPushButton(theme_icon)
        self.theme_btn.setFixedWidth(40)
        self.theme_btn.clicked.connect(self.toggle_theme)
        bar_layout.addWidget(self.theme_btn)

        self.lang_btn = QPushButton(t("lang_btn"))
        self.lang_btn.setFixedWidth(50)
        self.lang_btn.clicked.connect(self.toggle_language)
        bar_layout.addWidget(self.lang_btn)

        parent_layout.addWidget(bar)

    def _section_label(self, parent_layout, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {get_theme_colors()['TEXT2']}; font-weight: bold; font-size: {int(12*FONT_SCALE)}px; padding: 8px 12px 4px;")
        parent_layout.addWidget(lbl)

    def _card_frame(self):
        T = get_theme_colors()
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {T['SURFACE']};
                border: 1px solid {T['BORDER']};
                border-radius: 6px;
            }}
        """)
        return card

    def _primary_btn(self, text, callback):
        btn = QPushButton(text)
        btn.setProperty("primary", True)
        btn.clicked.connect(callback)
        return btn

    # ==================== DAILY TAB ====================
    def _build_daily_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(6)

        # 顶部：日期 + 按钮
        top = QHBoxLayout()
        date_lbl = QLabel(f"  {get_today()}")
        date_lbl.setStyleSheet(f"font-weight: bold; font-size: {int(13*FONT_SCALE)}px;")
        top.addWidget(date_lbl)
        top.addStretch()
        tags_btn = QPushButton(t("tags"))
        tags_btn.clicked.connect(self.extract_and_show_tags)
        top.addWidget(tags_btn)
        tpl_btn = QPushButton(t("template"))
        tpl_btn.clicked.connect(self.insert_template)
        top.addWidget(tpl_btn)
        layout.addLayout(top)

        # 编辑器卡片
        editor_card = self._card_frame()
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(8, 8, 8, 8)
        self.daily_text = QPlainTextEdit()
        self.daily_text.setFont(mono_font(13))
        self.daily_text.setPlainText(load_daily(get_today()))
        editor_layout.addWidget(self.daily_text)
        layout.addWidget(editor_card, stretch=1)

        # 底部：保存 + 标签显示
        bot = QHBoxLayout()
        self.tag_display = QLabel("")
        self.tag_display.setStyleSheet(f"color: {get_theme_colors()['GREEN']};")
        bot.addWidget(self.tag_display)
        bot.addStretch()
        save_btn = self._primary_btn(t("save"), self.save_daily)
        bot.addWidget(save_btn)
        layout.addLayout(bot)

        self.nb.addTab(tab, t("tab_diary"))

    def insert_template(self):
        template = "\n## Done\n- \n\n## Thoughts\n- \n\n## Tomorrow\n- \n"
        self.daily_text.insertPlainText(template)
        self.daily_text.setFocus()

    def save_daily(self):
        content = self.daily_text.toPlainText().strip()
        save_daily(get_today(), content)
        self.status_label.setText(f"{t('diary_saved')} - {get_today()} {get_now()}")
        self.daily_text.setFocus()

    def extract_and_show_tags(self):
        content = self.daily_text.toPlainText()
        tags = extract_tags(content)
        if tags:
            self.tag_display.setText(f"{t('tags')}: {', '.join(tags)}")
            self.status_label.setText(t("extracted_tags", n=len(tags)))
        else:
            self.tag_display.setText(t("no_tags"))
            self.status_label.setText(t("no_keywords"))
        self.daily_text.setFocus()

    # ==================== MOOD TAB ====================
    def _build_mood_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(6)

        self._section_label(layout, t("mood_q"))

        # 输入卡片
        inp_card = self._card_frame()
        inp_layout = QVBoxLayout(inp_card)
        inp_layout.setContentsMargins(8, 8, 8, 8)
        self.mood_input = QPlainTextEdit()
        self.mood_input.setFont(ui_font(12))
        self.mood_input.setFixedHeight(70)
        inp_layout.addWidget(self.mood_input)

        # 语音行
        vrow = QHBoxLayout()
        self.voice_btn = QPushButton(t("voice"))
        self.voice_btn.clicked.connect(self.on_voice_toggle)
        vrow.addWidget(self.voice_btn)

        mic_btn = QPushButton(t("mic_perm_btn"))
        mic_btn.setFixedWidth(40)
        mic_btn.clicked.connect(self._show_mic_permission_dialog)
        vrow.addWidget(mic_btn)

        vrow.addStretch()

        self.voice_status = QLabel("")
        self.voice_status.setStyleSheet("color: #888;")
        vrow.addWidget(self.voice_status)
        vrow.addStretch()

        self.voice_autosave = QCheckBox(t("voice_autosave"))
        self.voice_autosave.setChecked(voice_mood.load_autosave_pref())
        self.voice_autosave.toggled.connect(
            lambda v: voice_mood.save_autosave_pref(v))
        vrow.addWidget(self.voice_autosave)
        inp_layout.addLayout(vrow)

        layout.addWidget(inp_card)

        # 快捷心情卡片网格
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(6)
        for i, (mood, emoji) in enumerate(MOOD_EMOJI.items()):
            card = self._mood_card(f"{emoji} {mood}", lambda m=mood: self.quick_mood(m))
            card.setFixedHeight(50)
            grid.addWidget(card, i // 2, i % 2)
        layout.addWidget(grid_widget)

        # 分析按钮
        btn_row = QHBoxLayout()
        analyze_btn = self._primary_btn(t("auto_analyze"), lambda: self.analyze_mood_ui())
        btn_row.addWidget(analyze_btn)
        self.mood_result = QLabel("")
        self.mood_result.setStyleSheet(f"color: {get_theme_colors()['GREEN']}; font-size: {int(13*FONT_SCALE)}px;")
        btn_row.addWidget(self.mood_result)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 今日记录
        self._section_label(layout, t("today_records"))
        hist_card = self._card_frame()
        hist_layout = QVBoxLayout(hist_card)
        hist_layout.setContentsMargins(8, 8, 8, 8)
        self.mood_history = QPlainTextEdit()
        self.mood_history.setFont(mono_font(11))
        self.mood_history.setReadOnly(True)
        hist_layout.addWidget(self.mood_history)
        layout.addWidget(hist_card, stretch=1)

        self.nb.addTab(tab, t("tab_mood"))
        self.refresh_mood_history()

    def _mood_card(self, title, on_click):
        T = get_theme_colors()
        card = QPushButton(title)
        card.clicked.connect(on_click)
        card.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['SURFACE']};
                color: {T['TEXT']};
                border: 1px solid {T['BORDER']};
                border-radius: 8px;
                font-size: {int(14*FONT_SCALE)}px;
                font-weight: bold;
                text-align: left;
                padding-left: 20px;
            }}
            QPushButton:hover {{
                background-color: {T['BTN_HOVER']};
                border: 1px solid {T['ACCENT']};
            }}
        """)
        return card

    def quick_mood(self, mood):
        text = self.mood_input.toPlainText().strip()
        if not text:
            text = f"(quick: {mood})"
        save_mood(get_today(), mood, text, 1.0, "manual")
        self.mood_result.setText(f"{MOOD_EMOJI.get(mood, '')} {mood} ✓")
        self.mood_input.clear()
        self.refresh_mood_history()
        self.status_label.setText(t("mood_saved", m=mood))
        self.mood_input.setFocus()

    def analyze_mood_ui(self, acoustics=None):
        text = self.mood_input.toPlainText().strip()
        if not text and not acoustics:
            self.mood_result.setText(t("type_first"))
            self.mood_input.setFocus()
            return

        text_mood, text_conf, text_reason = ("平静", 0, "")
        if text:
            text_mood, text_conf, text_reason = analyze_mood(text)

        acou_mood, acou_conf, acou_detail = (None, 0, "")
        if acoustics:
            acou_mood, acou_conf, acou_detail = voice_mood.acoustics_to_mood(acoustics)

        if acou_mood and text:
            MOODS = list(MOOD_EMOJI.keys())
            combined = {m: 0 for m in MOODS}
            combined[text_mood] += text_conf * 0.6
            combined[acou_mood] += acou_conf * 0.4
            best_mood = max(combined, key=combined.get)
            best_conf = min(combined[best_mood], 1.0)
            parts = []
            if text_reason and text_reason != "未检测到明显情绪词":
                parts.append("文本: {}".format(text_reason))
            if acou_detail:
                parts.append("声音: {}".format(acou_detail))
            reason = " | ".join(parts) if parts else acou_detail or text_reason
        elif acou_mood and not text:
            best_mood = acou_mood
            best_conf = acou_conf
            reason = "声音分析: {}".format(acou_detail)
        else:
            best_mood = text_mood
            best_conf = text_conf
            reason = text_reason

        save_text = text if text else "(语音: {})".format((acou_detail or "")[:50])
        save_mood(get_today(), best_mood, save_text, best_conf, reason)
        emoji = MOOD_EMOJI.get(best_mood, "")
        detail = ""
        if acou_mood and text_mood and acou_mood != text_mood:
            detail = " (文本→{} 声音→{})".format(text_mood, acou_mood)
        self.mood_result.setText(f"{emoji} {best_mood} ({best_conf:.0%}){detail}")
        self.mood_input.clear()
        self.refresh_mood_history()
        self.status_label.setText(t("mood_saved", m=f"{best_mood} ({best_conf:.0%})"))
        self.mood_input.setFocus()

    # ==================== 语音功能 ====================
    def _voice_lang(self):
        return "zh-CN" if LANG == "zh" else "en-US"

    def on_voice_toggle(self):
        if not self.voice_deps_ok:
            ffmpeg_ok, sr_ok = voice_mood.deps_status()
            if not (ffmpeg_ok and sr_ok):
                need = []
                if not ffmpeg_ok:
                    need.append(t("voice_missing_ffmpeg"))
                if not sr_ok:
                    need.append(t("voice_missing_sr"))
                reply = QMessageBox.question(self, "语音依赖缺失",
                    t("voice_confirm_install").format(n="、".join(need)))
                if reply != QMessageBox.StandardButton.Yes:
                    return
                self._start_voice_install()
                return

        if self.voice_recorder.running:
            self.voice_recorder.stop()
            self.voice_btn.setText(t("voice"))
            self.voice_status.setText("识别中…")
            self.status_label.setText("停止录音，正在识别…")
            return

        self.voice_btn.setText(t("voice_stop"))
        self.voice_status.setText(t("voice_recording").format(n=voice_mood.MAX_SECONDS))
        self.status_label.setText(t("voice_recording").format(n=voice_mood.MAX_SECONDS))
        self.voice_recorder.start(lang=self._voice_lang())

    def _start_voice_install(self):
        self.voice_btn.setEnabled(False)
        self.voice_btn.setText(t("voice_installing"))
        self.voice_status.setText(t("voice_installing"))

        self._install_thread = threading.Thread(target=self._install_voice_deps, daemon=True)
        self._install_thread.start()
        QTimer.singleShot(200, self._poll_voice_install)

    def _install_voice_deps(self):
        try:
            self._voice_install_result = voice_mood.auto_install_deps()
        except Exception as e:
            self._voice_install_result = (False, False, ["安装异常：{}".format(e)])

    def _poll_voice_install(self):
        if not hasattr(self, '_voice_install_result') or self._voice_install_result is None:
            if hasattr(self, '_install_thread') and self._install_thread.is_alive():
                QTimer.singleShot(200, self._poll_voice_install)
                return
        if hasattr(self, '_voice_install_result') and self._voice_install_result:
            ffmpeg_ok, sr_ok, notes = self._voice_install_result
            self._voice_install_result = None
            self.voice_btn.setEnabled(True)
            ok = ffmpeg_ok and sr_ok
            self.voice_deps_ok = ok
            if ok:
                self.voice_status.setText(t("voice_install_ok"))
                self.status_label.setText(t("voice_install_ok"))
                self.on_voice_toggle()
            else:
                detail = t("voice_install_fail")
                if not ffmpeg_ok:
                    detail += "\n" + t("voice_need_ffmpeg")
                if not sr_ok:
                    detail += "\n" + t("voice_need_sr").format(py=sys.executable)
                if notes:
                    detail += "\n\n" + "\n".join(notes)
                QMessageBox.critical(self, "语音依赖安装失败", detail)

    def on_voice_result(self, text, acoustics=None):
        if text:
            cur = self.mood_input.toPlainText().strip()
            if cur:
                self.mood_input.setPlainText(cur + "\n" + text)
            else:
                self.mood_input.setPlainText(text)

        self.voice_btn.setText(t("voice"))

        if text:
            display = text[:40] + ("…" if len(text) > 40 else "")
        elif acoustics:
            acou_mood, _, acou_detail = voice_mood.acoustics_to_mood(acoustics)
            display = "声音→{} ({})".format(acou_mood or "未知", (acou_detail or "")[:30])
        else:
            display = "未识别到内容"

        if self.voice_autosave.isChecked():
            self.voice_status.setText("已识别：{}".format(display))
            self.status_label.setText("已识别：{}".format(display))
            self.analyze_mood_ui(acoustics=acoustics)
        else:
            self.voice_status.setText("已填入：{}".format(display))
            self.status_label.setText("已填入，请检查后保存")
            self.mood_input.setFocus()

    def on_voice_acoustics(self, features):
        try:
            acou_mood, _, acou_detail = voice_mood.acoustics_to_mood(features)
            emoji = MOOD_EMOJI.get(acou_mood, "")
            self.voice_status.setText("声音特征: {} {} {}".format(
                emoji, acou_mood, (acou_detail or "")[:20]))
        except Exception:
            pass

    def on_voice_error(self, msg):
        self.voice_btn.setText(t("voice"))
        self.voice_status.setText(msg)
        self.status_label.setText(msg)
        low = (msg or "").lower()
        if "麦克风权限被拒绝" in (msg or "") or "microphone" in low or "operation not permitted" in low:
            self._show_mic_permission_dialog()

    def on_voice_status(self, state, msg):
        if state == "recording":
            self.voice_btn.setText(t("voice_stop"))
        elif state in ("idle", "done"):
            self.voice_btn.setText(t("voice"))
        self.voice_status.setText(msg)

    def _show_mic_permission_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(t("mic_perm_title"))
        dlg.setFixedWidth(420)
        dlg_layout = QVBoxLayout(dlg)
        help_lbl = QLabel(t("mic_perm_help"))
        help_lbl.setWordWrap(True)
        dlg_layout.addWidget(help_lbl)
        btn_row = QHBoxLayout()
        reset_btn = self._primary_btn(t("mic_perm_reset"), lambda: self._reset_mic_permission(dlg))
        btn_row.addWidget(reset_btn)
        close_btn = QPushButton(t("close"))
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)
        dlg_layout.addLayout(btn_row)
        dlg.exec()

    def _reset_mic_permission(self, dlg):
        if sys.platform != "darwin":
            dlg.accept()
            QMessageBox.information(self, t("mic_perm_title"), t("mic_perm_only_mac"))
            return
        try:
            res = subprocess.run(["tccutil", "reset", "Microphone"],
                                 capture_output=True, text=True, timeout=20)
            ok = res.returncode == 0
        except Exception:
            ok = False
        dlg.accept()
        if ok:
            QMessageBox.information(self, t("mic_perm_title"), t("mic_perm_reset_ok"))
        else:
            QMessageBox.critical(self, t("mic_perm_title"), t("mic_perm_reset_fail"))

    def _stop_voice_if_running(self):
        if self.voice_recorder and self.voice_recorder.running:
            try:
                self.voice_recorder.stop()
            except Exception:
                pass

    def refresh_mood_history(self):
        records = load_moods(get_today())
        lines = []
        if records:
            for r in records:
                emoji = MOOD_EMOJI.get(r.get("mood", ""), "")
                conf = r.get("confidence", 0)
                line = f"[{r.get('time', '?')}] {emoji} {r.get('mood', '?')} ({conf:.0%}) - {r.get('text', '')[:40]}"
                lines.append(line)
        else:
            lines.append(t("no_records"))
        self.mood_history.setPlainText("\n".join(lines))

    # ==================== REMINDER TAB ====================
    def _build_reminder_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(6)

        self._section_label(layout, t("quick_reminders"))

        # 预设卡片
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(6)
        preset_items = [
            ("+1h", 1, "快速稍后提醒"),
            ("+2h", 2, "午间 / 会议"),
            ("+3h", 3, "下午安排"),
            (t("tmr9"), "tmr9", "晨间待办"),
            (t("tmr18"), "tmr18", "下班提醒"),
        ]
        for i, (label, val, hint) in enumerate(preset_items):
            card = self._reminder_card(label, hint, lambda v=val: self.preset_reminder(v))
            grid.addWidget(card, i // 2, i % 2)
        layout.addWidget(grid_widget)

        # 自定义提醒卡片
        ccard = self._card_frame()
        clayout = QVBoxLayout(ccard)
        clayout.setContentsMargins(12, 10, 12, 10)
        clayout.addWidget(QLabel(t("custom")))
        row = QHBoxLayout()
        self.reminder_msg = QLineEdit()
        self.reminder_msg.setPlaceholderText("提醒内容…")
        row.addWidget(self.reminder_msg)
        self.reminder_time = QLineEdit()
        self.reminder_time.setPlaceholderText("HH:MM")
        self.reminder_time.setFixedWidth(80)
        row.addWidget(self.reminder_time)
        add_btn = self._primary_btn(t("add"), self.add_custom_reminder)
        row.addWidget(add_btn)
        clayout.addLayout(row)
        layout.addWidget(ccard)

        # 待提醒列表
        self._section_label(layout, t("pending"))
        self.pending_scroll = QScrollArea()
        self.pending_scroll.setWidgetResizable(True)
        self.pending_container = QWidget()
        self.pending_layout = QVBoxLayout(self.pending_container)
        self.pending_layout.setContentsMargins(0, 0, 0, 0)
        self.pending_layout.setSpacing(6)
        self.pending_layout.addStretch()
        self.pending_scroll.setWidget(self.pending_container)
        layout.addWidget(self.pending_scroll, stretch=1)

        # 取消提醒
        bot = QHBoxLayout()
        bot.addWidget(QLabel(t("cancel_id")))
        self.cancel_id_input = QLineEdit()
        self.cancel_id_input.setFixedWidth(60)
        bot.addWidget(self.cancel_id_input)
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.cancel_reminder_ui)
        bot.addWidget(cancel_btn)
        bot.addStretch()
        layout.addLayout(bot)

        self.nb.addTab(tab, t("tab_reminder"))
        self.refresh_reminder_list()

    def _reminder_card(self, title, hint, on_click):
        T = get_theme_colors()
        card = QPushButton()
        card.clicked.connect(on_click)
        card.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['SURFACE']};
                border: 1px solid {T['BORDER']};
                border-radius: 8px;
                text-align: left;
                padding: 12px 16px;
            }}
            QPushButton:hover {{
                border: 1px solid {T['ACCENT']};
                background-color: {T['BTN_HOVER']};
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-weight: bold; font-size: {int(13*FONT_SCALE)}px; border: none; background: transparent;")
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(title_lbl)
        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(f"color: {T['TEXT2']}; font-size: {int(10*FONT_SCALE)}px; border: none; background: transparent;")
        hint_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(hint_lbl)
        return card

    def preset_reminder(self, val):
        now = datetime.now()
        msg = self.reminder_msg.text().strip() or "Reminder!"
        if isinstance(val, int):
            target = now + timedelta(hours=val)
        elif val == "tmr9":
            target = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        elif val == "tmr18":
            target = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        else:
            return
        add_reminder(target, msg)
        self.status_label.setText(t("reminder_set", t=target.strftime('%H:%M'), m=msg))
        self.refresh_reminder_list()

    def add_custom_reminder(self):
        msg = self.reminder_msg.text().strip()
        time_str = self.reminder_time.text().strip()
        if not msg:
            self.status_label.setText(t("enter_msg"))
            return
        try:
            h, m = map(int, time_str.split(":"))
            target = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= datetime.now():
                target += timedelta(days=1)
            add_reminder(target, msg)
            self.status_label.setText(t("reminder_set", t=target.strftime('%H:%M'), m=msg))
            self.refresh_reminder_list()
        except ValueError:
            self.status_label.setText(t("bad_time"))

    def cancel_reminder_ui(self):
        try:
            rid = int(self.cancel_id_input.text().strip())
            if cancel_reminder(rid):
                self.status_label.setText(t("reminder_cancelled", i=rid))
                self.refresh_reminder_list()
            else:
                self.status_label.setText(t("cannot_cancel", i=rid))
        except ValueError:
            self.status_label.setText(t("enter_id"))

    def refresh_reminder_list(self):
        # 清除旧卡片（保留末尾的 stretch）
        while self.pending_layout.count() > 1:
            item = self.pending_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        reminders = load_reminders()
        pending = [r for r in reminders if r["status"] == "pending"]
        T = get_theme_colors()
        if not pending:
            empty = QLabel(t("no_pending"))
            empty.setStyleSheet(f"color: {T['TEXT2']}; padding: 14px;")
            self.pending_layout.insertWidget(0, empty)
        else:
            for r in pending:
                card = QFrame()
                card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {T['SURFACE']};
                        border: 1px solid {T['BORDER']};
                        border-radius: 6px;
                    }}
                """)
                cl = QVBoxLayout(card)
                cl.setContentsMargins(14, 10, 14, 10)
                head = QLabel(f"#{r['id']}  {r['remind_at']}")
                head.setStyleSheet(f"color: {T['ACCENT']}; font-weight: bold; font-size: {int(12*FONT_SCALE)}px; border: none; background: transparent;")
                cl.addWidget(head)
                body = QLabel(r["message"])
                body.setStyleSheet(f"font-size: {int(13*FONT_SCALE)}px; border: none; background: transparent;")
                body.setWordWrap(True)
                cl.addWidget(body)
                self.pending_layout.insertWidget(self.pending_layout.count() - 1, card)

    # ==================== SHARE TAB ====================
    def _shared_modules(self):
        try:
            shared = os.path.join(_SCRIPT_DIR, "modules", "shared-wiki")
            if shared not in sys.path:
                sys.path.insert(0, shared)
            import wiki_core as _wc
            import agent_registry as _ar
            import obsidian_bridge as _ob
            return _wc, _ar, _ob
        except Exception as e:
            QMessageBox.critical(self, "Shared module error",
                                 "无法加载共享 Wiki 模块:\n{}".format(e))
            return None

    def _build_share_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # 顶部
        top = QHBoxLayout()
        title = QLabel(t("share_title"))
        title.setStyleSheet(f"font-weight: bold; font-size: {int(12*FONT_SCALE)}px;")
        top.addWidget(title)
        top.addStretch()
        refresh_btn = QPushButton(t("refresh"))
        refresh_btn.clicked.connect(self.share_refresh)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        # 可拖拽分隔
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.share_status = QPlainTextEdit()
        self.share_status.setReadOnly(True)
        self.share_status.setFont(mono_font(11))
        splitter.addWidget(self.share_status)

        btns = QWidget()
        btn_layout = QHBoxLayout(btns)
        btn_layout.setContentsMargins(0, 4, 0, 0)
        start_btn = self._primary_btn(t("start_server"), self.share_start_server)
        btn_layout.addWidget(start_btn)
        obs_btn = QPushButton(t("open_obsidian"))
        obs_btn.clicked.connect(self.share_open_obsidian)
        btn_layout.addWidget(obs_btn)
        bcast_btn = QPushButton(t("broadcast"))
        bcast_btn.clicked.connect(self.share_broadcast)
        btn_layout.addWidget(bcast_btn)
        btn_layout.addStretch()
        splitter.addWidget(btns)
        splitter.setSizes([360, 40])
        layout.addWidget(splitter, stretch=1)

        self.nb.addTab(tab, t("tab_share"))
        self.share_refresh()

    def share_set_status(self, text):
        self.share_status.setPlainText(text)

    def share_refresh(self):
        mods = self._shared_modules()
        if not mods:
            return
        _wc, _ar, _ob = mods
        lines = []
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
        mods = self._shared_modules()
        if not mods:
            return
        server_py = os.path.join(_SCRIPT_DIR, "modules", "shared-wiki", "mcp_server.py")
        if not os.path.exists(server_py):
            QMessageBox.critical(self, "Error", "找不到 mcp_server.py")
            return
        try:
            import mcp  # noqa: F401
        except ImportError:
            QMessageBox.critical(self, "缺少依赖: mcp",
                "当前 Python 环境未安装 mcp 包。\n\n请先安装:\n  {} -m pip install mcp".format(sys.executable))
            return
        try:
            log_path = os.path.join(WIKI_DIR, "mcp_server.log")
            log_f = open(log_path, "w")
            proc = subprocess.Popen([sys.executable, server_py],
                                    stdout=log_f, stderr=subprocess.STDOUT)
            self._mcp_proc = proc
            self.status_label.setText("MCP Server 已启动 (pid={})".format(proc.pid))
            QMessageBox.information(self, "MCP Server",
                "MyWiki MCP Server 已在后台启动。\n\n"
                "在你的 Agent 宿主配置:\n"
                '  command: {}\n  args: ["{}"]'.format(sys.executable, server_py))
        except Exception as e:
            QMessageBox.critical(self, "启动失败", str(e))

    def share_open_obsidian(self):
        mods = self._shared_modules()
        if not mods:
            return
        _wc, _ar, _ob = mods
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            _ob.open_note("daily/{}".format(today))
            self.status_label.setText("已在 Obsidian 打开 {}".format(today))
        except Exception as e:
            QMessageBox.critical(self, "打开失败", str(e))

    def share_broadcast(self):
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
                       "⏭ 跳过 ({}): {}\n".format(len(skipped), ", ".join(skipped) or "无"))
            else:
                msg = ("通知完成，但本次没有可接收的 Agent。\n\n"
                       "已发布更新: daily/{}.md\n\n".format(today) +
                       "跳过项:\n  · " + "\n  · ".join(skipped))
            self.status_label.setText("已通知 Agent")
            QMessageBox.information(self, "通知 Agent", msg)
            self.share_refresh()
        except Exception as e:
            QMessageBox.critical(self, "广播失败", str(e))

    # ==================== 语言/主题切换 ====================
    def toggle_language(self):
        self._stop_voice_if_running()
        global LANG
        LANG = "en" if LANG == "zh" else "zh"
        self._rebuild_ui()

    def toggle_theme(self):
        self._stop_voice_if_running()
        global MODE
        MODE = "dark" if MODE == "light" else "light"
        save_theme_pref(MODE)
        self._rebuild_ui()

    def _rebuild_ui(self):
        """重建整个 UI（语言/主题切换后）。"""
        # 移除中央控件
        central = self.takeCentralWidget()
        if central:
            central.deleteLater()
        # 重新设置
        self.setWindowTitle(t("app_title"))
        apply_qss(QApplication.instance(), MODE)
        self._build_ui()


# ==================== WELCOME DIALOG ====================
class WelcomeDialog(QDialog):
    """首次运行欢迎框。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MyWiki - First Run Setup / 首次运行设置")
        self.setMinimumSize(500, 480)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("📝 MyWiki")
        title.setStyleSheet(f"font-size: {int(24*FONT_SCALE)}px; font-weight: bold; color: {get_theme_colors()['ACCENT']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Personal Knowledge & Diary Manager\n个人知识库与日记管理工具")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # 状态检测
        obsidian_ok, _ = check_obsidian()
        openclaw_ok, _ = check_openclaw()
        v_ffmpeg, v_sr = voice_mood.deps_status()
        voice_ok = v_ffmpeg and v_sr

        status_lbl = QLabel("System Check / 系统检测")
        status_lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(status_lbl)

        for label, ok in [("Obsidian (知识库)", obsidian_ok),
                          ("OpenClaw (AI 助手)", openclaw_ok),
                          ("语音识别 (麦克风记录心情)", voice_ok)]:
            emoji = "✅" if ok else "❌"
            color = "#4ec9b0" if ok else "#f48771"
            row = QLabel(f"{emoji} {label}")
            row.setStyleSheet(f"color: {color}; padding-left: 20px;")
            layout.addWidget(row)

        # 安装按钮
        btn_frame = QHBoxLayout()
        if not voice_ok:
            install_btn = QPushButton("Install Voice / 安装语音依赖")
            install_btn.setProperty("primary", True)
            install_btn.clicked.connect(self._install_voice)
            btn_frame.addWidget(install_btn)
        btn_frame.addStretch()
        layout.addLayout(btn_frame)

        # 继续/退出
        bottom = QHBoxLayout()
        continue_lbl = "Continue / 继续" if (obsidian_ok and openclaw_ok) else "Skip & Continue / 跳过并继续"
        continue_btn = QPushButton(continue_lbl)
        continue_btn.setProperty("primary", True)
        continue_btn.clicked.connect(self.accept)
        bottom.addWidget(continue_btn)
        exit_btn = QPushButton("Exit / 退出")
        exit_btn.clicked.connect(self.reject)
        bottom.addWidget(exit_btn)
        layout.addLayout(bottom)

        tips = QLabel("Tips: Obsidian & OpenClaw are optional.\n提示：Obsidian 和 OpenClaw 是可选的。")
        tips.setStyleSheet("color: #888; font-size: 10px;")
        tips.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tips)

    def _install_voice(self):
        """安装语音依赖。"""
        progress = QProgressDialog("正在安装语音依赖…", "取消", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        result = {"v": None}
        def run():
            try:
                result["v"] = voice_mood.auto_install_deps()
            except Exception as e:
                result["v"] = (False, False, ["安装异常：{}".format(e)])

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        # 轮询
        def poll():
            if result["v"] is None:
                QTimer.singleShot(200, poll)
                return
            progress.close()
            f_ok, s_ok, notes = result["v"]
            if f_ok and s_ok:
                QMessageBox.information(self, "安装完成",
                    "语音依赖已安装，可前往「心情」页点击 🎤 使用。")
            else:
                detail = "安装失败:\n" + "\n".join(notes) if notes else "安装失败"
                QMessageBox.critical(self, "安装失败", detail)

        QTimer.singleShot(200, poll)


# ==================== MAIN ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 应用 QSS 样式
    apply_qss(app, MODE)

    # 设置应用图标
    if ICON_PATH and os.path.exists(ICON_PATH):
        try:
            app.setWindowIcon(QIcon(ICON_PATH))
        except Exception:
            pass

    window = WikiApp()
    window.show()

    # 首次运行显示欢迎框（非模态，不影响主窗口）
    if os.environ.get("MYWIKI_SKIP_WELCOME") != "1":
        QTimer.singleShot(200, lambda: WelcomeDialog(window).show())

    sys.exit(app.exec())
