#!/usr/bin/env python3
"""
obsidian_bridge.py — MyWiki ⇄ Obsidian 双向桥接

Obsidian 是共享 Wiki 的「可视化编辑面」：它直接读写 wiki 文件夹里的 .md。
本模块负责:
  1. discover_vaults()   自动发现本机已配置的 Obsidian Vault（含 my-wiki）
  2. open_note()         通过 obsidian:// URI 在 Obsidian 中打开任意笔记
  3. watch()             监听 wiki 文件夹变化，触发回调（Agent 可据此刷新/广播）
  4. vault_name()        读取当前 wiki 对应的 vault 名称

跨平台: macOS / Windows / Linux 均支持。
"""
import json
import sys
import platform
import subprocess
from pathlib import Path
from datetime import datetime


def _obsidian_config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "obsidian"
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Roaming" / "obsidian"
    return Path.home() / ".config" / "obsidian"


def discover_vaults() -> list:
    """
    从 Obsidian 的 obsidian.json 中读取已配置的 vault 列表。
    返回 [ {name, path} ]
    """
    cfg = _obsidian_config_dir() / "obsidian.json"
    vaults = []
    if not cfg.exists():
        return vaults
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except Exception:
        return vaults

    # 新版格式: {"vaults": {"<id>": {"path": ..., "name": ...}}}
    vaults_obj = data.get("vaults", {})
    for vid, v in vaults_obj.items():
        vaults.append({"name": v.get("name", vid), "path": v.get("path", "")})
    return vaults


def _obsidian_cfg_path() -> Path:
    """config/obsidian.json：用户本地的 vault 映射配置。"""
    return Path(__file__).parent.parent.parent / "config" / "obsidian.json"


def _load_obsidian_cfg() -> dict:
    p = _obsidian_cfg_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _vault_for_path(target: str):
    """在已发现 vault 中按路径匹配，返回 {"name", "path"} 或 None。"""
    try:
        tp = Path(target).resolve()
    except Exception:
        return None
    for v in discover_vaults():
        try:
            if Path(v["path"]).resolve() == tp:
                return v
        except Exception:
            continue
    return None


def detect_wiki_vault() -> dict:
    """
    判断当前 wiki 根目录是否已被 Obsidian 作为 vault 打开。
    返回 {"name", "path"} 或 None。
    """
    wiki_root = str(Path(__file__).parent.parent.parent.resolve())
    for v in discover_vaults():
        if Path(v["path"]).resolve() == Path(wiki_root).resolve():
            return v
    return None


def vault_name() -> str:
    """
    返回 wiki 对应的 vault 名称（供 obsidian:// URI 使用）。

    解析优先级：
      1. 环境变量 OBSIDIAN_VAULT_NAME
      2. config/obsidian.json 的 vault_name
      3. config/obsidian.json 的 vault_path -> 反查 vault id/name
      4. 自动检测：代码根目录是否就是某个已打开的 vault
      5. fallback "my-wiki"（并打印警告，不再静默瞎猜）
    """
    import os
    env = os.environ.get("OBSIDIAN_VAULT_NAME")
    if env:
        return env

    cfg = _load_obsidian_cfg()
    name = (cfg.get("vault_name") or "").strip()
    if name:
        return name

    vp = (cfg.get("vault_path") or "").strip()
    if vp:
        v = _vault_for_path(vp)
        if v:
            # obsidian.json 无 name 字段时 name 即 vault id，Obsidian 接受
            return v["name"]
        print(f"[WARN] config vault_path={vp} 不在 Obsidian 已打开的 vault 列表中")

    v = detect_wiki_vault()
    if v:
        return v["name"]

    print("[WARN] 无法确定 Obsidian vault，回退为 'my-wiki'。"
          "请在 config/obsidian.json 配置 vault_name 或 vault_path")
    return "my-wiki"


def open_note(rel_path: str, vault: str = None, line: int = None):
    """
    通过 obsidian:// URI 在 Obsidian 中打开笔记。
    rel_path: 例如 daily/2026-07-12
    line: 可选行号
    返回执行的命令字符串（便于日志）。
    """
    import urllib.parse
    v = vault or vault_name()
    encoded = urllib.parse.quote(rel_path, safe="/")
    uri = f"obsidian://open?vault={urllib.parse.quote(v, safe='')}&file={encoded}"
    if line is not None:
        uri += f"&line={line}"

    if sys.platform == "darwin":
        cmd = ["open", uri]
    elif sys.platform == "win32":
        cmd = ["cmd", "/c", "start", "", uri]
    else:
        cmd = ["xdg-open", uri]

    try:
        subprocess.run(cmd, check=False)
    except Exception as e:
        return f"[WARN] 无法打开 Obsidian: {e}"
    return " ".join(cmd)


def watch(callback, debounce: float = 1.0):
    """
    监听 wiki 文件夹变化，文件变动后调用 callback(event, path)。
    适合 Agent 在后台运行，实时感知 Obsidian 的编辑。

    依赖: 标准库 watchdog（可选）。未安装时退化为轮询。
    用法:
        watch(lambda ev, p: print("changed", p))
    """
    wiki_root = Path(__file__).parent.parent.parent

    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class Handler(FileSystemEventHandler):
            def __init__(self):
                self._last = {}

            def on_any_event(self, event):
                if event.is_directory:
                    return
                if not str(event.src_path).endswith(".md"):
                    return
                if ".obsidian" in str(event.src_path):
                    return
                callback(event.event_type, event.src_path)

        observer = Observer()
        observer.schedule(Handler(), str(wiki_root), recursive=True)
        observer.start()
        print(f"[WATCH] 正在监听 {wiki_root} (watchdog) ... Ctrl+C 退出")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    except ImportError:
        # 退化为轮询
        print("[WATCH] watchdog 未安装，使用轮询模式 (pip install watchdog 体验更佳)")
        _poll(wiki_root, callback, debounce)


def _poll(wiki_root, callback, debounce):
    import time
    seen = {}
    while True:
        for f in wiki_root.rglob("*.md"):
            if ".obsidian" in str(f):
                continue
            mtime = f.stat().st_mtime
            if f not in seen or seen[f] != mtime:
                seen[f] = mtime
                callback("modified", str(f))
        time.sleep(max(0.2, debounce))


if __name__ == "__main__":
    print("=== Obsidian Vault 发现 ===")
    for v in discover_vaults():
        print(f"  📓 {v['name']}  ->  {v['path']}")
    print(f"\n🔗 URI 将使用的 vault 名称: {vault_name()}")
    wiki_v = detect_wiki_vault()
    if wiki_v:
        print(f"✅ 当前 wiki 已被 Obsidian 作为 vault 打开: {wiki_v['name']}")
    else:
        print("\n⚠️  当前 wiki 目录未被 Obsidian 作为 vault 打开。")
        print("   若 vault 是另一个目录（如 AI Shared/wiki），请在")
        print("   config/obsidian.json 配置 vault_name 或 vault_path。")
