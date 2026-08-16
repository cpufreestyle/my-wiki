#!/usr/bin/env python3
"""wiki_theme.py — MyWiki 桌面版主题、QSS 样式与字体

MODE / UI_PREFS 是运行时可切换的全局状态（主题切换、设置面板实时调参），
外部统一通过 get_mode()/set_mode()/is_dark()/get_ui_pref()/set_ui_pref() 访问，
避免 `from wiki_theme import MODE` 拿到导入时的快照。
"""
import sys

from PySide6.QtGui import QFont

from theme import (
    get_tokens, load_theme_pref, save_theme_pref,
    load_ui_prefs, save_ui_prefs, DEFAULT_UI_PREFS,
)

MODE = load_theme_pref()
UI_PREFS = load_ui_prefs()  # 行间距等可调 UI 偏好


def get_mode():
    """读取当前主题模式（'light' / 'dark'）。"""
    return MODE


def set_mode(mode):
    """切换主题模式并持久化。"""
    global MODE
    MODE = mode
    save_theme_pref(MODE)


def is_dark():
    """当前是否为深色模式。"""
    return MODE == "dark"


def get_ui_pref(key, default=None):
    """读取单个 UI 偏好值。"""
    return UI_PREFS.get(key, DEFAULT_UI_PREFS.get(key, default))


def set_ui_pref(key, value):
    """设置单个 UI 偏好值（同步内存与磁盘）。"""
    UI_PREFS[key] = value
    save_ui_prefs(UI_PREFS)


def reload_ui_prefs():
    """放弃内存中的偏好修改，重新从磁盘加载。"""
    global UI_PREFS
    UI_PREFS = load_ui_prefs()


def get_theme_colors(mode=None):
    """返回主题色 dict，供 QSS 样式表使用。"""
    return get_tokens(mode or MODE)


def apply_qss(app, mode=None):
    """生成并应用 QSS 全局样式表，对齐网页版 Apple 风设计系统。

    设计要点（与 mood_web.html / daily_web.html / reminder_web.html 一致）：
      - 卡片：圆角 14px + 阴影分层，无边框（靠阴影区分层次）
      - 按钮：圆角 10px；primary 蓝底白字；tool 描边
      - 输入框：透明背景融入卡片
      - section-title：13px 次要色、大写、字间距
      - 正文 14-15px，行高 1.6
    """
    T = get_theme_colors(mode)
    bg = T["BG"]
    surface = T["SURFACE"]
    text = T["TEXT"]
    text2 = T["TEXT2"]
    accent = T["ACCENT"]
    accent_h = T["ACCENT_H"]
    border = T["BORDER"]
    btn_hover = T["BTN_HOVER"]
    is_dark_mode = (mode or MODE) == "dark"
    # 阴影：深色模式用更浓的黑色，浅色模式用淡灰
    shadow_rgb = "rgba(0,0,0,0.45)" if is_dark_mode else "rgba(0,0,0,0.08)"
    shadow_md_rgb = "rgba(0,0,0,0.5)" if is_dark_mode else "rgba(0,0,0,0.06)"

    qss = f"""
    QMainWindow, QWidget {{
        background-color: {bg};
        color: {text};
        font-family: {UI_FONT};
        font-size: 14px;
    }}
    /* ---------- 标签页（对齐网页 header，更宽松） ---------- */
    QTabWidget::pane {{
        border: none;
        background: transparent;
        top: -2px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {text2};
        padding: 10px 22px;
        margin: 0 2px;
        border: none;
        border-bottom: 3px solid transparent;
        font-size: 14px;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        color: {accent};
        border-bottom: 3px solid {accent};
    }}
    QTabBar::tab:hover:!selected {{
        color: {text};
        border-bottom: 3px solid {border};
    }}
    /* ---------- 按钮（对齐网页 .tool-btn / .analyze-btn） ---------- */
    QPushButton {{
        background-color: {surface};
        color: {text};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 9px 16px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        border-color: {accent};
        background-color: {surface};
    }}
    QPushButton:pressed {{
        background-color: {btn_hover};
    }}
    QPushButton[primary="true"] {{
        background-color: {accent};
        color: #ffffff;
        border: 1px solid {accent};
        border-radius: 10px;
        font-weight: 700;
        font-size: 15px;
        padding: 12px 18px;
    }}
    QPushButton[primary="true"]:hover {{
        background-color: {accent_h};
        border-color: {accent_h};
    }}
    QPushButton[card="true"] {{
        background-color: {surface};
        border: none;
        border-radius: 14px;
        text-align: left;
        padding: 0px;
        font-weight: 500;
    }}
    QPushButton[card="true"]:hover {{
        background-color: {surface};
        border: 1px solid {accent};
    }}
    /* ---------- 输入框（透明背景融入卡片，对齐网页 textarea） ---------- */
    QPlainTextEdit, QLineEdit {{
        background-color: transparent;
        color: {text};
        border: none;
        border-radius: 4px;
        padding: 4px 6px;
        font-size: 14px;
        line-height: 1.6;
        selection-background-color: {accent};
        selection-color: #ffffff;
    }}
    QPlainTextEdit:focus, QLineEdit:focus {{
        border: none;
    }}
    /* ---------- 卡片容器（对齐网页 .card：阴影无边框） ---------- */
    QFrame[card="true"] {{
        background-color: {surface};
        border: none;
        border-radius: 14px;
    }}
    QFrame[card="true"] > QLabel {{
        color: {text};
        background: transparent;
    }}
    /* ---------- 复选框 ---------- */
    QCheckBox {{
        color: {text2};
        font-size: 12px;
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid {border};
        background: {surface};
    }}
    QCheckBox::indicator:checked {{
        background: {accent};
        border-color: {accent};
    }}
    /* ---------- 标签默认透明 ---------- */
    QLabel {{
        color: {text};
        background: transparent;
    }}
    /* ---------- section-title（对齐网页 .section-title） ---------- */
    QLabel[section="true"] {{
        color: {text2};
        font-size: 13px;
        font-weight: 600;
        padding: 22px 4px 12px;
    }}
    /* ---------- 滚动区域 ---------- */
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        border: none;
        margin: 4px;
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
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: transparent;
    }}
    /* ---------- 分隔条 ---------- */
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
    """按缩放系数构造界面字体。"""
    sz = int(round(size * FONT_SCALE))
    f = QFont(UI_FONT, sz)
    f.setBold(bold)
    return f


def mono_font(size):
    """按缩放系数构造等宽字体。"""
    return QFont(MONO_FONT, int(round(size * FONT_SCALE)))
