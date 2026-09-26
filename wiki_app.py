#!/usr/bin/env python3
"""
My Wiki - All-in-One Personal Knowledge Tool
日记 | 心情 | 提醒 | 标签

PySide6 版本 —— 替代原 Tkinter 实现。
PySide6 的信号槽机制天然线程安全，子线程可通过信号把结果投递到主线程，
不再需要手动轮询队列。

模块结构（由原单文件拆分而来）：
  wiki_paths           路径常量与解析
  wiki_theme           主题 / QSS / 字体 / UI 偏好
  wiki_i18n            中英文案
  wiki_core            业务逻辑（日记 / 心情 / 提醒 CRUD）
  wiki_tabs_daily      日记标签页（Mixin）
  wiki_tabs_mood       心情标签页 + 语音（Mixin）
  wiki_tabs_reminder   提醒标签页（Mixin）
  wiki_tabs_share      共享标签页（Mixin）
  wiki_app             主窗口 / 对话框 / 入口（本文件）
"""
import os
import shutil
import signal
import subprocess
import sys
import threading
import urllib.request

from PySide6.QtCore import Qt, QObject, QTimer, Signal
from PySide6.QtGui import QIcon, QShortcut, QKeySequence, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QProgressDialog, QPlainTextEdit, QPushButton, QSpinBox,
    QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget,
    QGraphicsDropShadowEffect,
)

# ==================== DEPENDENCY CHECK ====================
try:
    import PySide6  # noqa: F401  （上面的 import 已隐含，这里仅触发统一错误提示）
except ModuleNotFoundError as e:
    dep = e.name or "PySide6"
    sys.stderr.write(
        f"\n❌ 缺少依赖：{dep}\n"
        "桌面版 GUI 需要 PySide6，且只在项目的 .venv 虚拟环境中安装。\n"
        "请用以下方式启动：\n\n"
        "    source .venv/bin/activate\n"
        "    python wiki_app.py\n\n"
        "或等价地： ./.venv/bin/python wiki_app.py\n"
        "（打包后的 MyWiki.app 无需 .venv，双击即开。）\n\n"
    )
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: F811
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None, "MyWiki 启动失败",
            f"缺少依赖：{dep}\n\n"
            "请用项目自带的虚拟环境启动：\n"
            "source .venv/bin/activate\npython wiki_app.py\n\n"
            "（双击 MyWiki.app 打包版无需此步骤。）",
        )
    except Exception:
        pass
    sys.exit(1)
import voice_mood
from backup_snapshots import create_snapshot
from wiki_paths import ICON_PATH, WIKI_DIR, _SCRIPT_DIR
from wiki_theme import (
    FONT_SCALE, apply_card_shadow, apply_qss, get_mode, get_theme_colors, get_ui_pref,
    is_dark, reload_ui_prefs, set_mode, set_ui_pref,
)
from wiki_i18n import get_lang, set_lang, t
from wiki_data import get_now, get_today, load_daily, save_daily
from wiki_tabs_daily import DailyTabMixin
from wiki_tabs_mood import MoodTabMixin
from wiki_tabs_reminder import ReminderTabMixin
from wiki_tabs_share import ShareTabMixin
from wiki_tabs_todo import TodoTabMixin
from wiki_tabs_search import SearchTabMixin
from wiki_tabs_tags import TagsTabMixin
from wiki_tabs_report import ReportTabMixin


def _proc_running(name):
    """检查某进程镜像名是否正在运行（用于识别已安装程序，即使 exe 路径异常）。"""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq {}".format(name), "/NH", "/FO", "CSV"],
            capture_output=True, text=True, timeout=10,
        )
        return name.lower() in out.stdout.lower()
    except Exception:
        return False


def _find_exe(root, name):
    """在 root 下递归查找名为 name 的可执行文件，返回首个命中路径或 None。"""
    if not os.path.isdir(root):
        return None
    try:
        for dirpath, _dirs, files in os.walk(root, onerror=lambda e: None):
            for fn in files:
                if fn.lower() == name:
                    return os.path.join(dirpath, fn)
    except Exception:
        pass
    return None


def check_obsidian():
    """检测 Obsidian 是否安装/已配置（跨平台）。返回 (bool, path)。"""
    if sys.platform == "darwin":
        if os.path.exists("/Applications/Obsidian.app"):
            return True, "/Applications/Obsidian.app"
        return False, None
    if sys.platform == "win32":
        import winreg

        # 1) 反查 obsidian:// 处理程序，拿到真实 exe（最可靠，跨任意安装路径）
        def _proto_exe():
            try:
                for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    try:
                        with winreg.OpenKey(root, r"Software\Classes\obsidian\shell\open\command") as k:
                            val = winreg.QueryValue(k, "")
                            if val:
                                return val.split('"')[1] if '"' in val else val.split()[0]
                    except OSError:
                        continue
            except Exception:
                pass
            return None

        exe = _proto_exe()
        if exe and os.path.exists(exe):
            return True, exe
        # 2) 正在运行（即使 exe 路径异常也能识别）
        if _proc_running("Obsidian.exe"):
            return True, exe
        # 3) 常见安装路径 + 商店版 stub（expanduser 兼容 C:/D: 盘）
        base = os.path.expanduser("~")
        for p in [
            os.path.join(base, "AppData", "Local", "Programs", "Obsidian", "Obsidian.exe"),
            os.path.join(base, "AppData", "Local", "Obsidian", "Obsidian.exe"),
            os.path.join(base, "AppData", "Local", "Microsoft", "WindowsApps", "Obsidian.exe"),
            r"C:\Program Files\Obsidian\Obsidian.exe",
            r"C:\Program Files (x86)\Obsidian\Obsidian.exe",
        ]:
            if os.path.exists(p):
                return True, p
        # 4) 递归兜底：在常用根目录里找 Obsidian.exe
        for root in (
            os.path.join(base, "AppData", "Local", "Programs"),
            os.path.join(base, "AppData", "Local"),
            r"C:\Program Files",
            r"C:\Program Files (x86)",
        ):
            hit = _find_exe(root, "obsidian.exe")
            if hit:
                return True, hit
        # 5) 协议已注册：说明系统认识 Obsidian（即使 exe 暂时缺失，也视为已配置）
        if exe:
            return True, None
    return False, None


def check_openclaw():
    """检测 QClaw / OpenClaw 是否安装。

    用户实际安装的是 QClaw 桌面端（Electron 应用），其真实 exe 位于
    ``D:\\Program Files\\QClaw\\vX.Y.Z\\QClaw.exe``，注册了 ``qclaw://`` 协议。
    因此检测优先级：协议注册表反查真实 exe → 常见路径 → 运行中进程兜底。
    """
    candidates = []

    # 1) 从 qclaw:// 协议注册表反查真实 exe 路径（最可靠）
    if sys.platform == "win32":
        try:
            import winreg
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    key = winreg.OpenKey(root, r"Software\Classes\qclaw\shell\open\command")
                    val, _ = winreg.QueryValueEx(key, "")
                    winreg.CloseKey(key)
                    # 值形如: "D:\Program Files\QClaw\v0.2.35\QClaw.exe" "%1"
                    exe = val.split('"')[1] if '"' in val else val.split()[0]
                    if exe:
                        candidates.append(exe)
                except OSError:
                    continue
        except Exception:
            pass

    if sys.platform == "darwin":
        candidates += [
            "/Applications/OpenClaw.app",
            "/Applications/QClaw.app",
            "/usr/local/bin/openclaw",
            "/opt/homebrew/bin/openclaw",
            os.path.expanduser("~/.local/bin/openclaw"),
            os.path.expanduser("~/.npm-global/bin/openclaw"),
            os.path.expanduser("~/.cargo/bin/openclaw"),
            os.path.expanduser("~/Library/Application Support/QClaw/openclaw"),
        ]
    elif sys.platform == "win32":
        base = os.path.expanduser("~")
        # QClaw 桌面端常见安装路径（含 D: 盘等非常规盘符由上方协议反查覆盖）
        candidates += [
            os.path.join(base, "AppData", "Local", "Programs", "QClaw", "QClaw.exe"),
            r"C:\Program Files\QClaw\QClaw.exe",
            r"C:\Program Files (x86)\QClaw\QClaw.exe",
            r"D:\Program Files\QClaw\QClaw.exe",
        ]
        # npm 全局安装（openclaw 实为 npm 全局包）
        npm_root = os.path.join(base, "AppData", "Roaming", "npm")
        candidates.append(os.path.join(npm_root, "node_modules", "openclaw"))  # 包目录即证明已装
        for ext in ("", ".cmd", ".ps1"):
            candidates.append(os.path.join(npm_root, "openclaw" + ext))
    try:
        out = subprocess.run(["npm", "prefix", "-g"], capture_output=True, text=True, timeout=3)
        if out.returncode == 0:
            g = out.stdout.strip()
            candidates.append(os.path.join(g, "bin", "openclaw"))
            candidates.append(os.path.join(g, "node_modules", "openclaw"))
    except Exception:
        pass
    found = shutil.which("openclaw") or shutil.which("qclaw")
    if found:
        candidates.insert(0, found)
    for c in candidates:
        if c.endswith(".app"):
            if os.path.exists(c):
                return True, c
            continue
        if os.path.isdir(c):  # npm 包目录也算已安装
            return True, c
        if os.path.exists(c):
            return True, c
    # 6) 运行中（QClaw 桌面端以 Electron 运行，按镜像名兜底）
    for name in ("openclaw.exe", "qclaw.exe", "QClaw.exe"):
        if _proc_running(name):
            return True, None
    return False, None


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
class WikiApp(QMainWindow, DailyTabMixin, MoodTabMixin, ReminderTabMixin, ShareTabMixin,
              TodoTabMixin, SearchTabMixin, TagsTabMixin, ReportTabMixin):
    """主窗口：组合各标签页 Mixin，负责顶栏、状态栏与生命周期。"""

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

        # 自动拉起网页版服务器（知识图谱 / 语义检索），关闭 App 时自动停止
        self._web_proc = None
        QTimer.singleShot(300, self._start_web_server)

        # 自动备份快照：启动后 30s 一次 + 每 24h 一次（后台线程，不卡 UI）
        QTimer.singleShot(30_000, self._run_backup)
        self._backup_timer = QTimer(self)
        self._backup_timer.setInterval(24 * 3600 * 1000)
        self._backup_timer.timeout.connect(self._run_backup)
        self._backup_timer.start()

        # 菜单栏常驻（macOS 状态栏 / Win 托盘）：速记 + 显示主窗 + 退出
        self._build_tray()

    # ==================== 菜单栏速记 ====================
    def _build_tray(self):
        """系统托盘/菜单栏图标：快速速记、显示主窗口、退出。"""
        from PySide6.QtWidgets import QSystemTrayIcon, QMenu
        self._tray = QSystemTrayIcon(QIcon(ICON_PATH) if ICON_PATH else QIcon(), self)
        menu = QMenu()
        act_quick = menu.addAction("✍️ 快速速记")
        act_show = menu.addAction("窗 显示主窗口")
        menu.addSeparator()
        act_quit = menu.addAction("退出")
        act_quick.triggered.connect(self.show_quick_note)
        act_show.triggered.connect(self._show_main_window)
        act_quit.triggered.connect(QApplication.instance().quit)
        self._tray.setContextMenu(menu)
        self._tray.setToolTip("MyWiki — 点击图标速记")
        self._tray.activated.connect(
            lambda reason: self.show_quick_note()
            if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self._tray.show()

    def show_quick_note(self):
        """弹出无边框速记窗：一句话写入今日日记末尾，Enter 保存 / Esc 关闭。"""
        from PySide6.QtCore import Qt as _Qt
        if getattr(self, "_quick_win", None) is not None:
            self._quick_win.activateWindow()
            self._quick_win.raise_()
            return
        win = QDialog(self, _Qt.WindowType.FramelessWindowHint | _Qt.WindowType.WindowStaysOnTopHint)
        win.setFixedSize(420, 130)
        win.setStyleSheet(f"""
            QDialog {{ background: {get_theme_colors()['SURFACE']};
                       border-radius: 12px; border: 1px solid {get_theme_colors()['BORDER']}; }}
        """)
        layout = QVBoxLayout(win)
        layout.setContentsMargins(14, 12, 14, 12)
        hint = QLabel("✍️ 速记一句话（Enter 保存 → 今日日记）")
        hint.setStyleSheet(f"color: {get_theme_colors()['TEXT2']}; font-size: 12px;")
        layout.addWidget(hint)
        edit = QPlainTextEdit()
        edit.setPlaceholderText("想到什么写什么…")
        edit.setStyleSheet(
            f"background: {get_theme_colors()['BG']}; color: {get_theme_colors()['TEXT']};"
            "border-radius: 8px; padding: 8px; font-size: 14px;")
        layout.addWidget(edit)

        def save_and_close():
            text = edit.toPlainText().strip()
            if text:
                content = load_daily(get_today())
                stamp = get_now()
                save_daily(get_today(), content.rstrip() + f"\n\n> 💭 {stamp} {text}\n")
                self.daily_text.setPlainText(load_daily(get_today()))
                self._notify("MyWiki 速记", "已写入今日日记 ✅")
            win.deleteLater()
            if self._quick_win is win:
                self._quick_win = None

        def key_filter(obj, ev):
            from PySide6.QtGui import QKeyEvent
            if isinstance(ev, QKeyEvent):
                if ev.key() == _Qt.Key.Key_Return and not ev.modifiers():
                    save_and_close(); return True
                if ev.key() == _Qt.Key.Key_Escape:
                    win.deleteLater()
                    if self._quick_win is win:
                        self._quick_win = None
                    return True
            return False

        edit.installEventFilter(win)
        win.eventFilter = key_filter  # 简易按键处理（QDialog 子类化省略）
        # 屏幕顶部居中弹出
        screen = QApplication.primaryScreen().availableGeometry()
        win.move((screen.width() - win.width()) // 2, 80)
        self._quick_win = win
        win.show()
        edit.setFocus()

    def _notify(self, title, msg):
        """macOS 通知中心推送；其他平台走托盘气泡。"""
        if sys.platform == "darwin":
            try:
                subprocess.run([
                    "osascript", "-e",
                    'display notification "{}" with title "{}"'.format(
                        msg.replace('"', '\\"'), title.replace('"', '\\"')),
                ], check=False, timeout=5)
                return
            except Exception:
                pass
        try:
            self._tray.showMessage(title, msg,
                                   QSystemTrayIcon.MessageIcon.Information, 3000)
        except Exception:
            pass

    def _show_main_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _run_backup(self):
        """执行一次自动备份（后台线程，异常静默不打扰用户）。"""
        def work():
            try:
                create_snapshot()
            except Exception as e:
                print(f"[backup] 快照失败: {e}", file=sys.stderr)
        threading.Thread(target=work, daemon=True).start()

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
        self._build_todo_tab()
        self._build_search_tab()
        self._build_tags_tab()
        self._build_report_tab()
        self._build_share_tab()

        # 标签页包进滚动区：内容超高时可滚动，防止布局挤压导致卡片叠放
        self._wrap_tabs_scrollable()

        # 状态栏
        self.status_label = QLabel(t("ready"))
        self.status_label.setStyleSheet(f"color: {get_theme_colors()['TEXT2']}; font-size: 13px; padding: 4px 20px 8px; text-align: center;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

    def _wrap_tabs_scrollable(self):
        """把每个标签页内容包进无边框滚动区。

        窗口较小（如 1147x745 笔记本屏）或用户在设置面板调大卡片高度时，
        标签页内容高度可能超出可视区。不包裹时外层 QVBoxLayout 会向下挤压
        固定高度的网格卡片：行距被压到小于卡片高度，卡片视觉上互相叠放
        （心情 / 提醒页已复现）。包裹后超出部分改为滚动，根除挤压叠放。
        """
        from PySide6.QtWidgets import QScrollArea
        if self.nb.count() == 0:
            return
        pages = [(self.nb.tabText(i), self.nb.widget(i))
                 for i in range(self.nb.count())]
        for text, page in pages:
            if page is None:
                continue
            idx = self.nb.indexOf(page)
            if idx >= 0:
                self.nb.removeTab(idx)
            scroll = QScrollArea()
            scroll.setWidget(page)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.nb.addTab(scroll, text)

    def _build_topbar(self, parent_layout):
        """顶部工具条（对齐网页 .app-header：居中标题 + 右上角圆形主题按钮）。"""
        T = get_theme_colors()
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(4, 8, 4, 4)
        bar_layout.setSpacing(8)

        # 左侧占位（与右侧按钮对称，让标题居中）
        bar_layout.addStretch()

        # 居中标题（对齐网页 h1：600 字重、紧凑字间距）
        title = QLabel("📝 " + t("app_title"))
        title.setStyleSheet(f"color: {T['TEXT']}; font-weight: 600; font-size: 18px; letter-spacing: -0.01em;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar_layout.addWidget(title)

        bar_layout.addStretch()

        # 右上角主题切换（对齐网页 .theme-toggle：圆形按钮）
        theme_icon = "🌙" if get_mode() == "light" else "☀️"
        self.theme_btn = QPushButton(theme_icon)
        self.theme_btn.setFixedSize(38, 38)
        self.theme_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['SURFACE']};
                border: none;
                border-radius: 19px;
                font-size: 17px;
            }}
            QPushButton:hover {{ background-color: {T['BTN_HOVER']}; }}
        """)
        self.theme_btn.clicked.connect(self.toggle_theme)
        bar_layout.addWidget(self.theme_btn)

        # 语言切换
        self.lang_btn = QPushButton(t("lang_btn"))
        self.lang_btn.setFixedSize(44, 38)
        self.lang_btn.clicked.connect(self.toggle_language)
        bar_layout.addWidget(self.lang_btn)

        # 界面设置按钮（行间距等）
        self.settings_btn = QPushButton(t("settings_btn"))
        self.settings_btn.setFixedSize(38, 38)
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['SURFACE']};
                border: none;
                border-radius: 19px;
                font-size: 18px;
            }}
            QPushButton:hover {{ background-color: {T['BTN_HOVER']}; }}
        """)
        self.settings_btn.clicked.connect(self.open_ui_settings)
        bar_layout.addWidget(self.settings_btn)

        # 打开网页版（复用 web_server.py 的图谱 / 检索页）
        self.web_btn = QPushButton("🌐 网页版")
        self.web_btn.setFixedSize(84, 38)
        self.web_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['SURFACE']};
                border: none;
                border-radius: 19px;
                font-size: 13px;
                font-weight: 600;
                color: {T['ACCENT']};
            }}
            QPushButton:hover {{ background-color: {T['BTN_HOVER']}; }}
        """)
        self.web_btn.clicked.connect(self.open_web_version)
        bar_layout.addWidget(self.web_btn)

        parent_layout.addWidget(bar)

    def _section_label(self, parent_layout, text):
        """小标题（对齐网页 .section-title：13px 次要色、600 字重）。"""
        lbl = QLabel(text)
        lbl.setProperty("section", True)
        parent_layout.addWidget(lbl)

    def _card_frame(self):
        """卡片容器（对齐网页 .card：圆角 14px + 阴影，无边框）。
        QSS 无法直接设阴影，用 QGraphicsDropShadowEffect 补上。
        """
        card = QFrame()
        card.setProperty("card", True)
        apply_card_shadow(card)  # QSS 不支持 box-shadow，用 effect 替代
        return card

    def _primary_btn(self, text, callback):
        """主操作按钮（蓝底白字）。"""
        btn = QPushButton(text)
        btn.setProperty("primary", True)
        btn.clicked.connect(callback)
        return btn

    # ==================== 语言/主题切换 ====================
    def toggle_language(self):
        """中英文切换并重建 UI。"""
        self._stop_voice_if_running()
        set_lang("en" if get_lang() == "zh" else "zh")
        self._rebuild_ui()

    def toggle_theme(self):
        """深浅主题切换并重建 UI。"""
        self._stop_voice_if_running()
        set_mode("dark" if get_mode() == "light" else "light")
        self._rebuild_ui()

    def open_ui_settings(self):
        """打开界面设置对话框，可调整行间距、内边距等。"""
        dlg = UISettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # 用户点确定后，重建 UI 应用新参数
            self._rebuild_ui()

    def open_web_version(self):
        """打开网页版门户（知识图谱 / RAG 语义检索），复用已运行的 web_server.py。

        若服务未运行（桌面端打开时本应已自动拉起），则先尝试启动再打开。
        """
        import webbrowser
        port = getattr(self, "_web_port", 8082)
        url = f"http://localhost:{port}/"
        try:
            urllib.request.urlopen(url, timeout=1.5)
        except Exception:
            # 服务未起：尝试自动拉起（用完即弃，不强制用户手动跑脚本）
            if not getattr(self, "_web_started", False):
                self._start_web_server(port)
                # 给子进程 / 线程一点启动时间。
                # 在等待循环里让出事件循环，避免主线程 sleep 期间界面假死。
                for _ in range(10):
                    try:
                        urllib.request.urlopen(url, timeout=1.0)
                        break
                    except Exception:
                        from PySide6.QtWidgets import QApplication
                        QApplication.instance().processEvents()
                        import time as _t
                        _t.sleep(0.4)
            try:
                urllib.request.urlopen(url, timeout=1.5)
            except Exception:
                QMessageBox.information(
                    self, "网页版未启动",
                    "网页版服务器（web_server.py）启动失败。\n\n"
                    "可尝试在项目目录手动运行：\n  python web_server.py\n\n"
                    "然后点击此按钮在浏览器中打开知识图谱与语义检索页面。",
                )
                return
        webbrowser.open(url)

    def _rebuild_ui(self):
        """重建整个 UI（语言/主题切换后）。"""
        # 移除中央控件
        central = self.takeCentralWidget()
        if central:
            central.deleteLater()
        # 重新设置
        self.setWindowTitle(t("app_title"))
        apply_qss(QApplication.instance(), get_mode())
        self._build_ui()

    # ==================== 网页版子进程管理 ====================
    def _resolve_web_server_script(self):
        """定位 web_server.py：优先打包后的 _MEIPASS，回退到源码目录。"""
        candidates = []
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "web_server.py"))
        here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(here, "web_server.py"))
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def _start_web_server(self, port=8082):
        """拉起本地网页服务器，使『网页版』按钮开箱即用。

        - 源码/未打包模式：以子进程方式运行 web_server.py（用项目 .venv 的 python）。
        - 打包(.app)模式：在同一进程内用守护线程启动，避免再用打包可执行文件
          当解释器而递归拉起 GUI，也无需外部 python。
        """
        if getattr(self, "_web_started", False):
            return
        self._web_started = True
        self._web_port = port

        if getattr(sys, "frozen", False):
            # 打包模式：线程内嵌启动（web_server 已随 app 打包进资源目录）
            try:
                import web_server  # 资源目录已在 sys.path
            except Exception as e:  # noqa: BLE001
                print(f"[web] 内嵌 web_server 导入失败：{e}", file=sys.stderr)
                self._web_started = False
                return
            # 端口被占用（如残留的 http.server）时，自动选用下一个可用端口
            for try_port in range(port, port + 11):
                try:
                    srv = web_server.make_server(try_port)
                except Exception as e:  # noqa: BLE001
                    print(f"[web] 端口 {try_port} 占用，尝试下一端口：{e}", file=sys.stderr)
                    continue
                self._web_port = try_port
                self._web_server = srv
                threading.Thread(target=srv.serve_forever, daemon=True).start()
                if try_port != port:
                    print(f"[web] 已改用端口 {try_port} 提供网页版", file=sys.stderr)
                return
            # 所有候选端口都失败
            self._web_started = False
            return

        # 未打包模式：子进程
        script = self._resolve_web_server_script()
        if not script:
            self._web_started = False
            return
        try:
            py = sys.executable
            # 若当前是系统 python 但存在 .venv，则优先用 .venv 解释器（含 rag/voice_mood 依赖）
            venv_py = os.path.join(os.path.dirname(os.path.dirname(script)), ".venv", "bin", "python")
            if not os.path.exists(venv_py):
                venv_py = os.path.join(os.path.dirname(script), ".venv", "bin", "python")
            if os.path.exists(venv_py):
                py = venv_py
            self._web_proc = subprocess.Popen(
                [py, script, str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            self._web_proc = None
            self._web_started = False

    def _stop_web_server(self):
        """退出时清理 web_server（线程内嵌或子进程）。"""
        srv = getattr(self, "_web_server", None)
        if srv is not None:
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:
                pass
            self._web_server = None
        proc = getattr(self, "_web_proc", None)
        if proc is None:
            return
        try:
            if proc.poll() is None:
                if hasattr(os, "killpg"):
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=3)
                except Exception:
                    proc.kill()
        except Exception:
            pass
        self._web_proc = None

    def closeEvent(self, event):
        """主窗口关闭时一并停止网页版子进程。"""
        self._stop_web_server()
        super().closeEvent(event)


# ==================== UI SETTINGS DIALOG ====================
class UISettingsDialog(QDialog):
    """界面设置对话框：可调整卡片行间距、内边距、字号等。
    设置实时预览，点确定后保存并重建 UI。"""

    # 可调参数定义: (key, label_zh, label_en, min, max, step)
    FIELDS = [
        ("card_min_height", "卡片高度", "Card height", 60, 240, 1),
        ("mood_card_height", "心情卡片高度", "Mood card height", 44, 160, 2),
        ("card_line_spacing", "卡片行间距", "Card line spacing", 0, 40, 1),
        ("card_padding_v", "卡片上下内边距", "Card padding (vertical)", 4, 40, 1),
        ("card_padding_h", "卡片左右内边距", "Card padding (horizontal)", 4, 40, 1),
        ("card_gap", "卡片之间间距", "Card gap", 0, 30, 1),
        ("title_font_size", "标题字号", "Title font size", 10, 24, 1),
        ("hint_font_size", "副文案字号", "Hint font size", 8, 20, 1),
        ("title_line_padding", "标题行额外间距", "Title line padding", 0, 16, 1),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("settings_title"))
        self.setMinimumSize(420, 360)
        self._spinboxes = {}
        T = get_theme_colors()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        # 提示文字
        hint = QLabel("调整后点「确定」立即应用。设置会自动保存。"
                      if get_lang() == "zh"
                      else "Click OK to apply. Settings auto-save.")
        hint.setStyleSheet(f"color: {T['TEXT2']}; font-size: 12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 参数行
        for key, lbl_zh, lbl_en, mn, mx, step in self.FIELDS:
            row = QHBoxLayout()
            label_text = lbl_zh if get_lang() == "zh" else lbl_en
            lbl = QLabel(label_text)
            lbl.setMinimumWidth(140)
            lbl.setStyleSheet(f"color: {T['TEXT']}; font-size: 13px;")
            row.addWidget(lbl)

            spin = QSpinBox()
            spin.setRange(mn, mx)
            spin.setSingleStep(step)
            spin.setValue(get_ui_pref(key, 0))
            spin.setSuffix(" px")
            spin.setMinimumWidth(100)
            spin.setStyleSheet(f"""
                QSpinBox {{
                    background-color: {T['SURFACE']};
                    color: {T['TEXT']};
                    border: 1px solid {T['BORDER']};
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 13px;
                }}
            """)
            # 实时预览：值变化时立即保存
            spin.valueChanged.connect(lambda v, k=key: self._on_changed(k, v))
            self._spinboxes[key] = spin
            row.addWidget(spin)
            row.addStretch()
            layout.addLayout(row)

        # 预览卡片
        layout.addWidget(self._preview_separator())
        preview_lbl = QLabel("📋 预览" if get_lang() == "zh" else "📋 Preview")
        preview_lbl.setStyleSheet(f"color: {T['TEXT2']}; font-size: 12px; font-weight: 600;")
        layout.addWidget(preview_lbl)
        self.preview_container = QVBoxLayout()
        self.preview_container.setSpacing(get_ui_pref("card_gap", 12))
        layout.addLayout(self.preview_container)
        self._refresh_preview()

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        reset_btn = QPushButton("恢复默认" if get_lang() == "zh" else "Reset")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)

        ok_btn = QPushButton("确定" if get_lang() == "zh" else "OK")
        ok_btn.setProperty("primary", True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)

        cancel_btn = QPushButton("取消" if get_lang() == "zh" else "Cancel")
        cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self._cancelled = False

    def _preview_separator(self):
        """预览区分隔线。"""
        T = get_theme_colors()
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {T['BORDER']}; background-color: {T['BORDER']}; max-height: 1px;")
        return sep

    def _on_changed(self, key, value):
        """值变化时立即保存到偏好（实时预览）。"""
        set_ui_pref(key, value)
        self._refresh_preview()

    def _refresh_preview(self):
        """刷新预览卡片。"""
        # 清除旧预览
        while self.preview_container.count():
            item = self.preview_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        parent = self.parent()
        # 心情卡片预览：即时反映「心情卡片高度」调节（对齐网页端 .mood-card）
        if parent and hasattr(parent, "_mood_card"):
            mood_preview = parent._mood_card(
                "开心" if get_lang() == "zh" else "Happy", lambda: None
            )
            mood_preview.setEnabled(False)  # 预览状态不可点击
            self.preview_container.addWidget(mood_preview)
        # 提醒卡片预览（复用主窗口的卡片样式）
        if parent and hasattr(parent, "_reminder_card"):
            card = parent._reminder_card("+1h", "快速稍后提醒" if get_lang() == "zh" else "Quick reminder", lambda: None)
            card.setEnabled(False)  # 预览状态不可点击
            self.preview_container.addWidget(card)
        self.preview_container.addStretch()

    def _reset_defaults(self):
        """恢复所有参数为默认值。"""
        from theme import DEFAULT_UI_PREFS
        for key, _, _, _, _, _ in self.FIELDS:
            default_val = DEFAULT_UI_PREFS.get(key, 0)
            set_ui_pref(key, default_val)
            if key in self._spinboxes:
                self._spinboxes[key].setValue(default_val)
        self._refresh_preview()

    def _cancel(self):
        """取消：恢复到对话框打开前的偏好状态。"""
        self._cancelled = True
        # 重新从磁盘加载（丢弃实时预览中的修改）
        reload_ui_prefs()
        self.reject()

    def closeEvent(self, event):
        """关闭按钮(×)也视为取消，恢复之前状态。"""
        if not self._cancelled:
            # 通过 closeEvent 关闭，恢复
            reload_ui_prefs()
        super().closeEvent(event)


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
def main():
    app = QApplication(sys.argv)

    # 应用 QSS 样式
    apply_qss(app, get_mode())

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


if __name__ == "__main__":
    main()
