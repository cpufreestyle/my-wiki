#!/usr/bin/env python3
"""wiki_paths.py — MyWiki 桌面版路径常量

统一维护 wiki 数据根目录、图标与各业务子目录的解析逻辑。
优先级: 环境变量 MYWIKI_ROOT > config/obsidian.json 的 vault_path > 仓库根目录。
"""
import json
import os
import sys
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
            # 用 with 确保文件句柄关闭（本函数会被多处调用，裸 open() 会持续泄漏句柄）
            with open(cfg, encoding="utf-8") as _f:
                vp = json.load(_f).get("vault_path", "")
            if vp and os.path.isdir(os.path.expanduser(vp)):
                return os.path.expanduser(vp)
        except Exception:
            pass
    return str(_SCRIPT_DIR)


def _resolve_app_icon():
    """定位应用图标（优先 macOS .icns）。"""
    cands = []
    if sys.platform == "darwin":
        cands.append(os.path.join(_SCRIPT_DIR, "assets", "AppIcon.icns"))
    cands.append(os.path.join(_SCRIPT_DIR, "icon.ico"))
    cands.append(os.path.join(_SCRIPT_DIR, "icon.png"))
    for c in cands:
        if os.path.exists(c):
            return c
    return ""


WIKI_DIR = _resolve_wiki_dir()
ICON_PATH = _resolve_app_icon()
DAILY_DIR = os.path.join(WIKI_DIR, "daily")
MOOD_DIR = os.path.join(WIKI_DIR, "mood")
REMINDER_DIR = os.path.join(WIKI_DIR, "reminders")
REMINDER_FILE = os.path.join(REMINDER_DIR, "reminders.json")
