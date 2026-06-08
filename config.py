#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
My Wiki - 配置模块
所有路径和配置集中管理
"""
import os
from pathlib import Path

# ===== 动态路径 =====
WIKI_DIR = Path(__file__).parent.resolve()

# 相对于 WIKI_DIR 的子目录
DAILY_DIR    = WIKI_DIR / "daily"
MOOD_DIR     = WIKI_DIR / "mood"
REMIND_DIR   = WIKI_DIR / "reminders"
ATTACH_DIR   = WIKI_DIR / "attachments"
SCRIPTS_DIR  = WIKI_DIR / "scripts"

# 数据文件
REMINDER_FILE = REMIND_DIR / "reminders.json"
PENDING_FILE  = REMIND_DIR / "pending_notifications.json"

# 资源文件
ICON_ICO = WIKI_DIR / "icon.ico"
ICON_PNG = WIKI_DIR / "icon.png"

# ===== Obsidian 检测 =====
def find_obsidian():
    """检测 Obsidian 安装路径（支持新版路径）"""
    import winreg
    
    # 新版路径（winget 安装）
    paths_new = [
        Path(os.getenv("LOCALAPPDATA", "")) / "Obsidian" / "Obsidian.exe",
        Path(os.getenv("PROGRAMFILES", "C:\\Program Files")) / "Obsidian" / "Obsidian.exe",
        Path(os.getenv("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Obsidian" / "Obsidian.exe",
    ]
    
    # 旧版路径（installer）
    paths_old = [
        Path(os.getenv("APPDATA", "")) / "..\\Local\\Obsidian\\Obsidian.exe",
    ]
    
    for p in paths_new + paths_old:
        if p.exists():
            return str(p)
    
    # 注册表检测
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Obsidian")
        path, _ = winreg.QueryValueEx(key, "InstallLocation")
        winreg.CloseKey(key)
        p = Path(path) / "Obsidian.exe"
        if p.exists():
            return str(p)
    except Exception:
        pass
    
    return None

OBSIDIAN_PATH = find_obsidian()

# ===== 主题 =====
THEME = {
    "bg":        "#1e1e1e",
    "bg2":       "#252526",
    "fg":        "#d4d4d4",
    "accent":    "#569cd6",
    "accent2":   "#4ec9b0",
    "btn_bg":    "#333333",
    "btn_active":"#3c3c3c",
}

# ===== 确保目录存在 =====
def ensure_dirs():
    for d in [DAILY_DIR, MOOD_DIR, REMIND_DIR, ATTACH_DIR, SCRIPTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

ensure_dirs()
