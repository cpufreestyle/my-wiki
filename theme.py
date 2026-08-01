# MyWiki UI 统一设计 token —— Apple 风（浅色 / 深色）
# 三个界面（reminder_web.html / reminder_ui.py / daily_ui.py）共用同一套值。
# 修改这里即可整体换肤。

import os
import json

# ---------- 字体 ----------
FONT = "Helvetica Neue"  # macOS 下中文回退到系统字体

# ---------- 浅色主题 ----------
LIGHT = {
    "BG": "#F5F5F7",          # 页面/窗口背景（浅灰）
    "SURFACE": "#FFFFFF",     # 卡片/表面（纯白）
    "TEXT": "#1D1D1F",        # 主文字
    "TEXT2": "#86868B",       # 次要文字
    "ACCENT": "#0A84FF",      # 主强调（Apple 蓝）
    "ACCENT_H": "#0070E0",    # 主强调 hover
    "ORANGE": "#FF9F0A",      # 自定义提醒（橙）
    "ORANGE_H": "#E88E00",    # 自定义 hover
    "GREEN": "#34C759",       # 查看/成功（绿）
    "GREEN_H": "#2BB04E",     # 绿 hover
    "BORDER": "#E5E5EA",      # 描边/分隔线
    "BTN_HOVER": "#ECECEF",   # 次级按钮 hover
}

# ---------- 深色主题 ----------
DARK = {
    "BG": "#1C1C1E",          # 窗口背景（接近黑）
    "SURFACE": "#2C2C2E",     # 卡片/表面
    "TEXT": "#F5F5F7",        # 主文字（近白）
    "TEXT2": "#98989D",       # 次要文字
    "ACCENT": "#0A84FF",      # 主强调（Apple 蓝，深浅一致）
    "ACCENT_H": "#409CFF",    # 主强调 hover（提亮）
    "ORANGE": "#FF9F0A",      # 自定义提醒（橙）
    "ORANGE_H": "#FFB340",    # 自定义 hover（对齐网页深色）
    "GREEN": "#30D158",       # 查看/成功（深底提亮绿）
    "GREEN_H": "#40D969",     # 绿 hover（对齐网页深色）
    "BORDER": "#3A3A3C",      # 描边/分隔线
    "BTN_HOVER": "#3A3A3C",   # 次级按钮 hover
}

# ---------- 预设提醒提示文案（仅桌面/网页提醒用） ----------
HINTS = {
    "1小时后": "快速稍后提醒",
    "2小时后": "午间 / 会议",
    "3小时后": "下午安排",
    "明天9点": "晨间待办",
    "明天18点": "下班提醒",
    "下周9点": "周计划",
}

# ---------- 偏好持久化（桌面两 App 共用，互相「同步」） ----------
DEFAULT_MODE = "light"
_PREF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
PREF_FILE = os.path.join(_PREF_DIR, "theme_pref.txt")

# UI 偏好文件（行间距、卡片内边距等可调参数）
UI_PREF_FILE = os.path.join(_PREF_DIR, "ui_pref.json")

# UI 偏好默认值
DEFAULT_UI_PREFS = {
    "card_line_spacing": 12,      # 卡片内标题行与副文案之间的间距(px)
    "card_padding_v": 16,         # 卡片上下内边距(px)
    "card_padding_h": 18,         # 卡片左右内边距(px)
    "card_gap": 12,               # 卡片之间的间距(px)
    "card_min_height": 80,        # 卡片最小高度(px)，可手动拖拽调整
    "title_font_size": 15,        # 标题字号(px)
    "hint_font_size": 12,         # 副文案字号(px)
    "title_line_padding": 2,      # 标题上下额外 padding(px)
    "mood_card_height": 52,       # 心情卡片高度(px)，对齐网页端 --card-h 默认 52px
}


def load_theme_pref() -> str:
    """读取用户主题偏好（light / dark），读不到则回退默认浅色。"""
    try:
        if os.path.exists(PREF_FILE):
            with open(PREF_FILE, "r", encoding="utf-8") as f:
                m = f.read().strip()
            if m in ("light", "dark"):
                return m
    except Exception:
        pass
    return DEFAULT_MODE


def save_theme_pref(mode: str) -> None:
    """写入用户主题偏好，供另一桌面 App 读取（实现偏好同步）。"""
    try:
        os.makedirs(_PREF_DIR, exist_ok=True)
        with open(PREF_FILE, "w", encoding="utf-8") as f:
            f.write(mode)
    except Exception:
        pass


def get_tokens(mode: str | None = None) -> dict[str, str]:
    """返回指定主题的 token 字典；mode 缺省时读用户偏好。"""
    if mode is None:
        mode = load_theme_pref()
    return DARK if mode == "dark" else LIGHT


def load_ui_prefs() -> dict:
    """读取 UI 偏好（行间距等），读不到则回退默认值。"""
    prefs = dict(DEFAULT_UI_PREFS)
    try:
        if os.path.exists(UI_PREF_FILE):
            with open(UI_PREF_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # 只合并已知键，保证新字段有默认值
                for k in DEFAULT_UI_PREFS:
                    if k in data:
                        try:
                            prefs[k] = type(DEFAULT_UI_PREFS[k])(data[k])
                        except (TypeError, ValueError):
                            pass
    except Exception:
        pass
    return prefs


def save_ui_prefs(prefs: dict) -> None:
    """写入 UI 偏好，供下次启动读取。"""
    try:
        os.makedirs(_PREF_DIR, exist_ok=True)
        # 只存已知键
        clean = {k: prefs.get(k, DEFAULT_UI_PREFS[k]) for k in DEFAULT_UI_PREFS}
        with open(UI_PREF_FILE, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
