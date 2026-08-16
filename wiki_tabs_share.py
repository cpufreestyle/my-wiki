#!/usr/bin/env python3
"""wiki_tabs_share.py — 共享标签页（Mixin）

展示共享知识库状态（Obsidian Vault / Agent 发现 / 笔记统计），
并提供 MCP Server 启动、Obsidian 跳转与 Agent 广播，
由 WikiApp 通过多继承组合。
"""
import os
import shutil
import sys
import subprocess
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)

from wiki_paths import WIKI_DIR, _SCRIPT_DIR
from wiki_theme import get_theme_colors, mono_font
from wiki_i18n import t


def _resolve_shared_dir():
    """定位 shared-wiki 模块目录（wiki_core / agent_registry / obsidian_bridge）。

    查找顺序：
      1. 源码模式：仓库根 modules/shared-wiki（wiki_paths 所在目录）
      2. 环境变量 MYWIKI_SOURCE_DIR 指定的源码仓库
      3. 用户级可写副本：~/Library/Application Support/MyWiki/shared-wiki
         （打包 .app 模式下首次运行时从包内只读资源拷贝过去，
          避免 registry.json 等运行时写入破坏 .app 代码签名）
      4. 打包资源 sys._MEIPASS/modules/shared-wiki（只读，拷贝到 3 后使用）
      5. 常见开发机源码位置兜底
    找不到含 wiki_core.py 的目录时返回第一候选（供报错定位）。
    """
    def has_core(d):
        return os.path.isfile(os.path.join(d, "wiki_core.py"))

    if sys.platform == "win32":
        app_support = os.path.expanduser("~/AppData/Local/MyWiki")
    else:
        app_support = os.path.expanduser("~/Library/Application Support/MyWiki")
    user_copy = os.path.join(app_support, "shared-wiki")

    if getattr(sys, "frozen", False):
        # 打包模式：优先用户可写副本；没有则从包内只读资源拷贝一份，
        # 保证 registry.json 等运行时写入发生在包外（不破坏代码签名）。
        if has_core(user_copy):
            return user_copy
        meip = getattr(sys, "_MEIPASS", None)
        if meip:
            bundled = os.path.join(meip, "modules", "shared-wiki")
            if has_core(bundled):
                try:
                    shutil.copytree(bundled, user_copy, dirs_exist_ok=True)
                    return user_copy
                except Exception:
                    return bundled  # 拷贝失败退化为包内只读
        env_repo = os.environ.get("MYWIKI_SOURCE_DIR")
        if env_repo:
            cand = os.path.join(os.path.expanduser(env_repo), "modules", "shared-wiki")
            if has_core(cand):
                return cand
        dev_cand = os.path.expanduser("~/AI Shared/repo/my-wiki/modules/shared-wiki")
        if has_core(dev_cand):
            return dev_cand
        return os.path.join(getattr(sys, "_MEIPASS", _SCRIPT_DIR), "modules", "shared-wiki")

    # 源码模式：仓库根目录
    src = os.path.join(_SCRIPT_DIR, "modules", "shared-wiki")
    if has_core(src):
        return src
    # 环境变量指定源仓库
    env_repo = os.environ.get("MYWIKI_SOURCE_DIR")
    if env_repo:
        cand = os.path.join(os.path.expanduser(env_repo), "modules", "shared-wiki")
        if has_core(cand):
            return cand
    # 用户级可写副本
    if has_core(user_copy):
        return user_copy
    # 开发机常见源码位置兜底
    dev_cand = os.path.expanduser("~/AI Shared/repo/my-wiki/modules/shared-wiki")
    if has_core(dev_cand):
        return dev_cand
    return src


class ShareTabMixin:
    """共享标签页：状态总览 + MCP Server + Obsidian + Agent 广播。"""

    def _shared_modules(self):
        """惰性加载 shared-wiki 三件套（wiki_core / agent_registry / obsidian_bridge）。"""
        try:
            shared = _resolve_shared_dir()
            if shared not in sys.path:
                sys.path.insert(0, shared)
            import wiki_core as _wc
            import agent_registry as _ar
            import obsidian_bridge as _ob
            return _wc, _ar, _ob
        except Exception as e:
            QMessageBox.critical(self, "Shared module error",
                                 "无法加载共享 Wiki 模块:\n{}\n\n"
                                 "若在使用打包版 MyWiki.app：\n"
                                 "  · 终端执行 export MYWIKI_SOURCE_DIR=/path/to/my-wiki 后重启\n"
                                 "  · 或把仓库 modules/shared-wiki 拷贝到\n"
                                 "    ~/Library/Application Support/MyWiki/shared-wiki".format(e))
            return None

    def _build_share_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # 顶部
        top = QHBoxLayout()
        top.setSpacing(8)
        title = QLabel(t("share_title"))
        title.setStyleSheet(f"font-weight: 600; font-size: 15px; color: {get_theme_colors()['TEXT']};")
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
        self.share_status.setFont(mono_font(12))
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
        """设置共享状态文本。"""
        self.share_status.setPlainText(text)

    def share_refresh(self):
        """刷新 Obsidian / Agent / Wiki 状态总览。"""
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
        """后台启动 MCP Server 并提示配置方式。"""
        mods = self._shared_modules()
        if not mods:
            return
        server_py = os.path.join(_resolve_shared_dir(), "mcp_server.py")
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
        """在 Obsidian 中打开今日日记。"""
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
        """向所有已发现 Agent 广播今日日记更新事件。"""
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
