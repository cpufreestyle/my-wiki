# MyWiki UI 统一设计 token —— Apple 风（浅色 / 深色）
# 三个界面（reminder_web.html / reminder_ui.py / daily_ui.py）共用同一套值。
# 修改这里即可整体换肤。

import os

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
