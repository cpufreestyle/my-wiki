#!/usr/bin/env python3
"""
agent_registry.py — 发现并管理「电脑里所有的 Agent」

让 MyWiki 成为一个共享中枢：不仅 Obsidian 能读写，电脑里运行的
各种 AI Agent（OpenClaw、A2A 网络节点、Claude Desktop、Cursor、Memo 等）
都能被自动发现，并接收 wiki 的知识更新广播。

功能:
  1. discover()     自动扫描 localhost 上常见的 Agent 端口 / 进程
  2. register()     手动登记一个 Agent (持久化到 registry.json)
  3. broadcast()    向所有在线 Agent 广播一条知识更新消息
  4. list_agents()  列出当前已知 Agent

Agent Card 约定 (兼容 Google A2A 协议):
  每个 Agent 在 /.well-known/agent-card.json 暴露自身元信息：
  { "name", "description", "url", "capabilities": ["wiki.read","wiki.write",...] }
"""
import json
import sys
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from datetime import datetime

REGISTRY_PATH = Path(__file__).parent / "registry.json"

# 已知 Agent 的默认探测配置
# (name, 探测 URL, 是否尝试读取 agent-card)
KNOWN_PROBES = [
    ("OpenClaw", "http://localhost:10005/.well-known/agent-card.json", True),
    ("A2A-Orchestrator", "http://localhost:10000/.well-known/agent-card.json", True),
    ("LM-Studio", "http://localhost:10001/.well-known/agent-card.json", True),
    ("Ollama", "http://localhost:10002/.well-known/agent-card.json", True),
    ("Blender3D", "http://localhost:10003/.well-known/agent-card.json", True),
    ("StepFun", "http://localhost:10004/.well-known/agent-card.json", True),
    # 通用工具端点
    ("Ollama-API", "http://localhost:11434/api/tags", False),
    ("LM-Studio-API", "http://localhost:1234/v1/models", False),
    ("Claude-Code", None, False),   # 通过进程发现
    ("Cursor", None, False),
]

# 通过进程名发现的 Agent
PROCESS_NAMES = {
    "OpenClaw": ["openclaw", "qclaw"],
    "Claude": ["claude"],
    "Cursor": ["cursor"],
    "Memo": ["Memo"],
    "Obsidian": ["Obsidian"],
}


def _http_get(url, timeout=0.6):
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def _read_agent_card(url):
    raw = _http_get(url)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _running_processes(names):
    """返回当前运行中的进程名集合 (macOS/linux 用 ps, windows 用 tasklist)。"""
    found = set()
    try:
        if sys.platform == "win32":
            out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=5).stdout
            for target in names:
                if target.lower() in out.lower():
                    found.add(target)
        else:
            out = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5).stdout
            for target in names:
                if target.lower() in out.lower():
                    found.add(target)
    except Exception:
        pass
    return found


def discover(auto_register: bool = True) -> list:
    """
    自动发现电脑里正在运行的 Agent。
    返回发现到的 agent 列表。
    """
    discovered = []

    # 1) HTTP 探测已知 Agent 端点
    for name, url, read_card in KNOWN_PROBES:
        if url is None:
            continue
        card = _read_agent_card(url) if read_card else None
        if card or _http_get(url):
            agent = {
                "name": card.get("name", name) if card else name,
                "url": url.rsplit("/.well-known", 1)[0] if "/.well-known" in url else url,
                "description": card.get("description", "") if card else "",
                "capabilities": card.get("capabilities", []) if card else [],
                "status": "online",
                "discovered_via": "http",
                # read_card=False 的端点（Ollama/LM-Studio 的 API）只是探测用，
                # 不支持接收广播，标记为非广播目标，避免广播时误报「失败」。
                "broadcastable": bool(read_card),
                "last_seen": datetime.now().isoformat(timespec="seconds"),
            }
            discovered.append(agent)

    # 2) 进程扫描
    for agent_name, procs in PROCESS_NAMES.items():
        running = _running_processes(procs)
        if running:
            discovered.append({
                "name": agent_name,
                "url": "",
                "description": f"{agent_name} (本地进程)",
                "capabilities": ["wiki.read", "wiki.write"] if agent_name != "Obsidian" else ["wiki.read"],
                "status": "online",
                "discovered_via": "process",
                "last_seen": datetime.now().isoformat(timespec="seconds"),
            })

    # 3) Obsidian 始终是共享方（通过文件系统）
    discovered.append({
        "name": "Obsidian",
        "url": "vault://my-wiki",
        "description": "Obsidian Vault — 通过共享文件夹直接读写 .md",
        "capabilities": ["wiki.read", "wiki.write"],
        "status": "always",
        "discovered_via": "filesystem",
        "last_seen": datetime.now().isoformat(timespec="seconds"),
    })

    # 去重（按 name）
    by_name = {}
    for a in discovered:
        by_name[a["name"]] = a

    if auto_register:
        _merge_registry(list(by_name.values()))

    return list(by_name.values())


def _load_registry() -> dict:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"agents": []}


def _merge_registry(discovered: list):
    reg = _load_registry()
    existing = {a["name"]: a for a in reg["agents"]}
    for a in discovered:
        existing[a["name"]] = a
    reg["agents"] = list(existing.values())
    reg["updated"] = datetime.now().isoformat(timespec="seconds")
    REGISTRY_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def register(name: str, url: str = "", description: str = "", capabilities: list = None):
    """手动登记一个 Agent 并持久化。"""
    reg = _load_registry()
    agent = {
        "name": name,
        "url": url,
        "description": description,
        "capabilities": capabilities or ["wiki.read"],
        "status": "registered",
        "last_seen": datetime.now().isoformat(timespec="seconds"),
    }
    found = False
    for i, a in enumerate(reg["agents"]):
        if a["name"] == name:
            reg["agents"][i] = agent
            found = True
            break
    if not found:
        reg["agents"].append(agent)
    REGISTRY_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    return agent


def list_agents() -> list:
    """列出所有已登记的 Agent。"""
    reg = _load_registry()
    return reg.get("agents", [])


def broadcast(event: str, payload: dict = None, only_capable: str = None) -> dict:
    """
    向所有在线、支持对应能力的 Agent 广播一条知识更新。
    event: 事件类型，例如 "wiki.updated" / "note.created"
    payload: 附带数据，例如 {"rel": "daily/2026-07-12.md"}
    only_capable: 仅发送给具备某能力的 agent，例如 "wiki.read"
    返回 {sent, failed, skipped}
    """
    agents = list_agents()
    sent, failed, skipped = [], [], []

    message = {
        "event": event,
        "payload": payload or {},
        "source": "mywiki",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")

    for a in agents:
        if a.get("status") not in ("online", "always", "registered"):
            skipped.append(a["name"])
            continue
        if only_capable and only_capable not in a.get("capabilities", []):
            skipped.append(a["name"])
            continue
        if a.get("broadcastable") is False:
            # 仅用于探测的 API 端点（如 Ollama/LM-Studio），不接收广播
            skipped.append(a["name"] + "(api)")
            continue
        url = a.get("url", "")
        if not url or url.startswith("vault://") or url.startswith("file://"):
            # Obsidian 等基于文件的 Agent 无需网络广播
            skipped.append(a["name"] + "(file-based)")
            continue
        # 尝试 POST 到 /webhook 或根
        for ep in (url.rstrip("/") + "/webhook", url):
            try:
                req = urllib.request.Request(
                    ep, data=body,
                    headers={"Content-Type": "application/json"}, method="POST"
                )
                with urllib.request.urlopen(req, timeout=1.0) as r:
                    if r.status < 400:
                        sent.append(a["name"])
                        break
            except Exception:
                continue
        else:
            failed.append(a["name"])

    return {"sent": sent, "failed": failed, "skipped": skipped}


if __name__ == "__main__":
    print("=== 发现电脑里的 Agent ===")
    found = discover()
    for a in found:
        print(f"  ✅ {a['name']}  [{a['status']}]  {a['url'] or a.get('discovered_via','')}")
    print(f"\n共发现 {len(found)} 个 Agent")
