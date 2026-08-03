#!/usr/bin/env python3
"""
collect_context.py — 多源上下文采集器（驱动 QClaw / OpenClaw 联动）

设计思路
--------
不再自己用 curl 直连飞书/微信开放平台，而是直接调用本机 QClaw 已经接好并登录的
飞书 / 企业微信 集成（lark-cli / wecom-cli）。QClaw 进程常驻，账号态就绪，
因此无需自己管理 token / 权限，也不会遇到"机器人未进群"之类问题。

采集来源
--------
- 飞书（lark-cli，user 身份）：群聊 + 单聊最近消息
- 企业微信（wecom-cli）：最近 7 天会话 + 消息
- 飞书会议妙记（lark-cli minutes）：可选
- 本地录音（whisper CLI）：mp3/m4a/wav 转写

所有上下文写入"共享 Obsidian vault"（与 QClaw workspace 同源），按来源分目录：
  chat/        飞书 + 企微 聊天
  meetings/    飞书会议妙记
  recordings/  本机录音转写

这样 QClaw 的自动记忆系统与 Obsidian 双向联动（写入 .md 即进入两者上下文）。

用法
----
  python3 scripts/collect_context.py                 # 跑全部启用来源
  python3 scripts/collect_context.py --only chat     # 只跑飞书+企微
  python3 scripts/collect_context.py --only meetings
  python3 scripts/collect_context.py --only recordings
  python3 scripts/collect_context.py --dry-run       # 只打印将要执行的命令
  python3 scripts/collect_context.py --days 3        # 拉取最近 N 天（默认 7）
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---- 路径定位 --------------------------------------------------------------

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO / "config" / "collect_context.json"
EXAMPLE_CONFIG = REPO / "config" / "examples" / "collect_context.example.json"

# 共享 Obsidian vault（与 QClaw workspace 同源）
SHARED_VAULT = Path("/Users/a1-6/AI Shared/wiki")

# QClaw 自带 node + 已登录的 lark-cli / wecom-cli
QCLOW_DIR = Path.home() / "Library" / "Application Support" / "QClaw"
QCLOW_NODE = Path("/Applications/QClaw.app/Contents/Resources/node/node")
QCLOW_NPM = QCLOW_DIR / "npm-global" / "lib" / "node_modules"
LARK_CLI = QCLOW_NPM / "@larksuite" / "cli" / "scripts" / "run.js"
WECOM_CLI = QCLOW_NPM / "@wecom" / "cli" / "bin" / "wecom.js"

CST = timezone(timedelta(hours=8))

# ---- 增量 / 状态辅助 -------------------------------------------------------

STATE_FILE = REPO / "config" / ".collect_backoff.json"


def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _find_existing(vault: Path, category: str, dedup_key: str) -> Path | None:
    """按 dedup_key 在已有笔记里找同一条，返回路径或 None。"""
    cat_dir = vault / category
    if not cat_dir.exists():
        return None
    for existing in sorted(cat_dir.glob("*.md")):
        try:
            txt = existing.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        if f"{dedup_key}" in txt and "---" in txt:
            return existing
    return None


def _parse_frontmatter(path: Path) -> dict:
    """极简 frontmatter 解析，返回键值字典。"""
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return {}
    if not txt.startswith("---"):
        return {}
    end = txt.find("\n---", 3)
    if end < 0:
        return {}
    meta = {}
    for line in txt[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def _merge_frontmatter(txt: str, meta: dict) -> str:
    """更新已有笔记 frontmatter 中 meta 指定的字段，正文保持不变，返回新文本。

    用于 append 模式在追加新行后仍能持久化 last_synced 等增量标记，
    否则增量拉取会在下一轮丢失上次同步时间而退化为全量拉取。
    """
    if not meta:
        return txt
    if not txt.startswith("---"):
        return txt
    end = txt.find("\n---", 3)
    if end < 0:
        return txt
    fm_block = txt[3:end]
    body = txt[end + 4:]
    out_lines: list[str] = []
    seen: set[str] = set()
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, _ = line.partition(":")
            key = k.strip()
            if key in meta:
                out_lines.append(f"{key}: {meta[key]}")
                seen.add(key)
                continue
        out_lines.append(line)
    for key, val in meta.items():
        if key not in seen:
            out_lines.append(f"{key}: {val}")
    return "---\n" + "\n".join(out_lines) + "\n---\n" + body.lstrip("\n")


def _narrow_start(days: int, last_synced_iso: str | None, iso: bool = True):
    """计算拉取起点：取 max(上次同步时间, now-days)。返回 (start_str, last_synced_dt)。"""
    now = datetime.now(CST)
    start_dt = now - timedelta(days=days)
    ls_dt = None
    if last_synced_iso:
        try:
            ls_dt = datetime.fromisoformat(last_synced_iso)
            if ls_dt.tzinfo is None:
                ls_dt = ls_dt.replace(tzinfo=CST)
            if ls_dt > start_dt:
                start_dt = ls_dt
        except Exception:  # noqa: BLE001
            ls_dt = None
    if iso:
        return start_dt.isoformat(timespec="seconds"), ls_dt
    return start_dt.strftime("%Y-%m-%d %H:%M:%S"), ls_dt


def _to_iso(ts) -> str | None:
    """把消息时间戳尽量转成 ISO（支持 ISO 串 / epoch 秒·毫秒）。失败返回 None。"""
    if not ts:
        return None
    s = str(ts).strip()
    try:
        return datetime.fromisoformat(s).astimezone(CST).isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001
        pass
    try:
        f = float(s)
        if f > 1e12:
            f /= 1000
        return datetime.fromtimestamp(f, CST).isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001
        return None


def _wecom_should_skip(state: dict) -> bool:
    """连续无数据且今日已尝试过 -> 退避跳过。"""
    today = datetime.now(CST).strftime("%Y-%m-%d")
    ce = state.get("wecom_consecutive_empty", 0)
    return ce >= 3 and state.get("wecom_last_attempt_date") == today


def _wecom_record(state: dict, had_data: bool) -> None:
    """记录企微本轮结果，更新连续无数据计数与退避状态。"""
    today = datetime.now(CST).strftime("%Y-%m-%d")
    if had_data:
        state["wecom_consecutive_empty"] = 0
    else:
        ce = state.get("wecom_consecutive_empty", 0) + 1
        state["wecom_consecutive_empty"] = min(ce, 999)
        if ce >= 3:
            print(f"[warn] 企业微信连续 {ce} 次无数据（可能授权过期 / 无消息），"
                  f"进入每日退避，今日不再重试", file=sys.stderr)
    state["wecom_last_attempt_date"] = today
    _save_state(state)


# ---- 配置 ------------------------------------------------------------------

def load_config(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 读取配置失败 {path}: {e}", file=sys.stderr)
    if EXAMPLE_CONFIG.exists():
        return json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    return {"enabled": {}}


def vault_root(cfg: dict) -> Path:
    """允许配置覆盖 vault 路径，否则用默认共享 vault。"""
    v = cfg.get("vault")
    if v:
        return Path(os.path.expanduser(v))
    return SHARED_VAULT


# ---- QClaw CLI 封装 ---------------------------------------------------------

def _run_cli(cli: Path, *args: str, dry_run: bool = False) -> dict | None:
    """运行 QClaw 内置 CLI，返回解析后的 JSON（失败返回 None）。"""
    if not QCLOW_NODE.exists() or not cli.exists():
        print(f"[skip] 缺少 QClaw 运行时：node={QCLOW_NODE} cli={cli}", file=sys.stderr)
        return None
    cmd = [str(QCLOW_NODE), str(cli), *args]
    print(f"[run] {' '.join(cmd)}", file=sys.stderr)
    if dry_run:
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print(f"[error] 超时：{' '.join(cmd)}", file=sys.stderr)
        return None
    if out.returncode != 0 and not out.stdout.strip():
        print(f"[error] {cli.name} 失败: {out.stderr[:300]}", file=sys.stderr)
        return None
    # lark-cli/wecom-cli 输出纯 JSON（可能多行）；尝试解析
    raw = (out.stdout or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 退一步：取第一行开始的 JSON 片段
        try:
            start = raw.find("{")
            if start >= 0:
                return json.loads(raw[start:])
        except Exception:  # noqa: BLE001
            pass
        print(f"[warn] 无法解析 JSON 输出：{raw[:200]}", file=sys.stderr)
        return None


def _unwrap_mcp_text(payload: dict | None) -> dict:
    """企微 wecom-cli 返回包在 MCP jsonrpc 里：result.content[].text 是 JSON 字符串。

    尝试剥掉这一层，拿到内部业务 JSON；失败则返回原对象。
    """
    if not isinstance(payload, dict):
        return {}
    if "result" in payload and isinstance(payload["result"], dict):
        content = payload["result"].get("content")
        if isinstance(content, list) and content and isinstance(content[0], dict):
            text = content[0].get("text")
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {}
    return payload


# ---- 笔记写入 --------------------------------------------------------------

def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_note(category: str, date: str, source: str, title: str, body: str,
              participants: list[str] | None = None, extra_tags: list[str] | None = None,
              vault: Path | None = None, meta: dict | None = None,
              dedup_key: str | None = None, append: bool = False) -> Path:
    """写入一条分源笔记（frontmatter + 正文）。返回文件路径。

    dedup_key: 若提供，则在 cat_dir 下查找 frontmatter 含该 key 的已有笔记，
               找到则原地更新（不新增），避免重复累积。
    meta: 额外写入 frontmatter 的键值（如 minute_token / last_synced）。
    append: 命中已有笔记时，仅追加正文中「不在旧文件里」的新行，避免边界重复；
            配合 dedup_key 实现增量更新。
    无变化时（内容一致）直接跳过写入，避免每轮刷新 mtime 触发无谓同步。
    """
    vault = vault or SHARED_VAULT
    cat_dir = _ensure_dir(vault / category)
    path = _find_existing(vault, category, dedup_key) if dedup_key else None
    new_body = body.strip()

    # ---- 追加模式：仅补入新增行，并持久化 meta（如 last_synced）----
    if path is not None and append and path.exists():
        try:
            old_txt = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            old_txt = ""
        old_lines = set(old_txt.splitlines())
        add_lines = [ln for ln in new_body.splitlines() if ln and ln not in old_lines]
        if add_lines:
            base = old_txt.rstrip("\n")
            new_text = base + "\n\n" + "\n".join(add_lines) + "\n"
        else:
            new_text = old_txt  # 无新增，原样保留
        # 把 last_synced 等增量标记写回 frontmatter，否则下轮会丢失
        if meta:
            new_text = _merge_frontmatter(new_text, meta)
        if _unchanged(path, new_text):
            print(f"[skip] 无变化：{path}", file=sys.stderr)
            return path
        path.write_text(new_text, encoding="utf-8")
        print((f"[append] {path}" if add_lines else f"[update] {path}"), file=sys.stderr)
        return path

    # ---- 普通模式（覆盖写 / 首次创建）----
    if path is None:
        safe_title = "".join(c if c.isalnum() or c in " -_（）()" else "_" for c in title)[:60]
        fname = f"{date}-{safe_title}.md"
        path = cat_dir / fname
        # 避免同天同名覆盖：编号
        n = 1
        while path.exists():
            n += 1
            path = cat_dir / f"{date}-{safe_title}-{n}.md"
    tags = [category, source] + (extra_tags or [])
    fm = [
        "---",
        f"source: {source}",
        f"category: {category}",
        f"date: {date}",
        f"title: {title}",
    ]
    if meta:
        for k, v in meta.items():
            fm.append(f"{k}: {v}")
    if participants:
        fm.append(f"participants: {', '.join(participants)}")
    fm.append(f"tags: [{' '.join(tags)}]")
    fm.append("---")
    fm.append("")
    fm.append(f"# {title}")
    fm.append("")
    fm.append(new_body)
    fm.append("")
    new_text = "\n".join(fm)
    if _unchanged(path, new_text):
        print(f"[skip] 无变化：{path}", file=sys.stderr)
        return path
    path.write_text(new_text, encoding="utf-8")
    print(f"[write] {path}", file=sys.stderr)
    return path


def _unchanged(path: Path, new_text: str) -> bool:
    """文件已存在且内容（忽略首尾空白）一致时返回 True。"""
    if not path.exists():
        return False
    try:
        old = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return False
    return old.strip() == new_text.strip()


# ---- 飞书采集 --------------------------------------------------------------

def collect_feishu(cfg: dict, days: int, dry_run: bool, vault: Path) -> int:
    if not (cfg.get("enabled", {}).get("feishu", False)):
        print("[skip] feishu 未启用", file=sys.stderr)
        return 0
    # 1) 拉会话列表
    lst = _run_cli(LARK_CLI, "im", "+chat-list", "--types", "group,p2p",
                   "--sort", "active_time", "--page-size", "20", "--as", "user",
                   dry_run=dry_run)
    if dry_run:
        return 0
    chats = (lst or {}).get("data", {}).get("chats", []) if lst else []
    if not chats:
        print("[info] 飞书无会话", file=sys.stderr)
        return 0
    count = 0
    for ch in chats[:int(cfg.get("feishu", {}).get("max_chats", 20))]:
        cid = ch.get("chat_id")
        name = ch.get("name") or cid or "未命名会话"
        if not cid:
            continue
        # 增量：从上次同步时间之后拉取，缩小传输窗口
        last_synced = None
        existing = _find_existing(vault, "chat", f"chat_id: {cid}")
        if existing:
            last_synced = _parse_frontmatter(existing).get("last_synced")
        start_iso, _ = _narrow_start(days, last_synced, iso=True)
        # 2) 拉消息
        msg = _run_cli(LARK_CLI, "im", "+chat-messages-list", "--chat-id", cid,
                       "--start", start_iso, "--order", "asc", "--page-size", "50",
                       "--as", "user", dry_run=dry_run)
        if dry_run:
            continue
        items = (msg or {}).get("data", {}).get("messages", []) if msg else []
        if not items:
            continue
        lines = []
        max_ts = None
        for m in items:
            sender = (m.get("sender") or {}).get("name") or m.get("sender_id") or "unknown"
            ts = m.get("create_time") or m.get("timestamp", "")
            content = _extract_lark_content(m)
            if content:
                lines.append(f"- **{ts}** ({sender}): {content}")
                iso = _to_iso(ts)
                if iso and (max_ts is None or iso > max_ts):
                    max_ts = iso
        if lines:
            date = datetime.now(CST).strftime("%Y-%m-%d")
            meta = {"chat_id": cid}
            if max_ts:
                meta["last_synced"] = max_ts
            body = "\n".join(lines)
            save_note("chat", date, "feishu", name, body,
                      extra_tags=["lark", ch.get("chat_mode", "group")],
                      meta=meta,
                      dedup_key=f"chat_id: {cid}",
                      append=True,
                      vault=vault)
            count += 1
    return count


def _strip_html(text: str) -> str:
    """去掉 HTML 标签与常见转义字符（<b> &lt;b&gt; 等），保留可读文本。"""
    import re
    t = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _extract_lark_content(m: dict) -> str:
    """从 lark 消息结构里尽量抽出可读文本。

    lark-cli 返回的 content 通常是已渲染的字符串（纯文本或含 <card ...> 标签的
    markdown 片段）。图片/文件/音频等媒体返回占位提示。
    """
    c = m.get("content")
    if not isinstance(c, str):
        return ""
    # 去掉 <card title="..."> 包裹标签，保留内部 markdown 文本
    txt = c.strip()
    if txt.startswith("<card"):
        end = txt.find(">")
        if end >= 0:
            txt = txt[end + 1:]
        if txt.endswith("</card>"):
            txt = txt[:-len("</card>")]
    txt = txt.strip()
    if not txt:
        mt = m.get("message_type") or m.get("msg_type") or ""
        if mt in ("image", "file", "audio", "media", "video", "sticker"):
            return f"[{mt}]"
    return txt


# ---- 企业微信采集 ----------------------------------------------------------

def collect_wecom(cfg: dict, days: int, dry_run: bool, vault: Path) -> int:
    if not (cfg.get("enabled", {}).get("wecom", False)):
        print("[skip] wecom 未启用", file=sys.stderr)
        return 0
    state = _load_state()
    if _wecom_should_skip(state):
        print("[skip] 企业微信退避中（连续无数据，今日已重试过），跳过本轮", file=sys.stderr)
        return 0
    start_iso = (datetime.now(CST) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    end_iso = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    # 1) 会话列表（企微仅支持 7 天，参数走 --json）
    lst = _run_cli(WECOM_CLI, "msg", "get_msg_chat_list", "--json",
                   json.dumps({"begin_time": start_iso, "end_time": end_iso}),
                   dry_run=dry_run)
    if dry_run:
        return 0
    if lst is None:
        print("[warn] 企业微信 CLI 调用失败（可能未登录 / 授权过期 / 网络异常），本轮跳过",
              file=sys.stderr)
        _wecom_record(state, had_data=False)
        return 0
    # 企微返回包一层 MCP jsonrpc，真正数据在 result.content[].text（字符串）
    chats = _unwrap_mcp_text(lst).get("chats", []) if lst else []
    if not chats:
        print("[info] 企业微信无会话", file=sys.stderr)
        _wecom_record(state, had_data=False)
        return 0
    count = 0
    for ch in chats[:int(cfg.get("wecom", {}).get("max_chats", 20))]:
        cid = ch.get("conversation_id") or ch.get("chat_id")
        ctype = ch.get("chat_type") or 2
        name = ch.get("name") or ch.get("conversation_name") or cid or "未命名会话"
        if not cid:
            continue
        msg = _run_cli(WECOM_CLI, "msg", "get_message", "--json",
                       json.dumps({"chatid": cid, "chat_type": ctype,
                                   "begin_time": start_iso, "end_time": end_iso}),
                       dry_run=dry_run)
        if dry_run:
            continue
        items = _unwrap_mcp_text(msg).get("msg_list", []) if msg else []
        if not items:
            continue
        lines = []
        max_ts = None
        for m in items:
            sender = m.get("sender") or m.get("from", "")
            ts = m.get("msgtime") or m.get("time", "")
            text = m.get("msg_content") or m.get("content") or ""
            if text:
                lines.append(f"- **{ts}** ({sender}): {text}")
                iso = _to_iso(ts)
                if iso and (max_ts is None or iso > max_ts):
                    max_ts = iso
        if lines:
            date = datetime.now(CST).strftime("%Y-%m-%d")
            meta = {"conversation_id": cid}
            if max_ts:
                meta["last_synced"] = max_ts
            save_note("chat", date, "wecom", name, "\n".join(lines),
                      extra_tags=["wecom"],
                      meta=meta,
                      dedup_key=f"conversation_id: {cid}",
                      append=True,
                      vault=vault)
            count += 1
    _wecom_record(state, had_data=count > 0)
    return count


# ---- 飞书会议妙记 ----------------------------------------------------------

def collect_feishu_meeting(cfg: dict, dry_run: bool, vault: Path) -> int:
    if not (cfg.get("enabled", {}).get("feishu_meeting", False)):
        print("[skip] feishu_meeting 未启用", file=sys.stderr)
        return 0
    days = int(cfg.get("feishu_meeting", {}).get("days", 14))
    start = (datetime.now(CST) - timedelta(days=days)).strftime("%Y-%m-%d")
    # 1) 搜索最近妙记（lark-cli minutes +search）
    lst = _run_cli(LARK_CLI, "minutes", "+search", "--start", start,
                   "--as", "user", "--page-size", "15", dry_run=dry_run)
    if dry_run:
        return 0
    items = (lst or {}).get("data", {}).get("items", []) if lst else []
    if not items:
        print("[info] 飞书会议无妙记（或缺少 minutes:minutes.basic:read 授权）", file=sys.stderr)
        return 0
    count = 0
    # +detail --transcript 要求 --output-dir 为「当前目录下的相对路径」，
    # 因此临时切到 vault/meetings 目录执行，跑完读回内容再恢复 cwd。
    meetings_dir = _ensure_dir(vault / "meetings")
    rel_tmp = Path(".minutes_tmp")
    prev_cwd = Path.cwd()
    try:
        os.chdir(meetings_dir)
        for it in items[:int(cfg.get("feishu_meeting", {}).get("max", 10))]:
            token = it.get("token")
            display = it.get("display_info") or ""
            # 从 display_info 提取标题（第一段为标题），去掉 HTML 标签/转义
            raw_title = display.split("\\n")[0].strip() or "会议妙记"
            title = _strip_html(raw_title) or "会议妙记"
            if not token:
                continue
            # 2) 取转录（落盘到相对目录，再读回）
            detail = _run_cli(LARK_CLI, "minutes", "+detail", "--minute-tokens", token,
                              "--transcript", "--as", "user",
                              "--output-dir", str(rel_tmp), dry_run=dry_run)
            if dry_run:
                continue
            # 转录落盘为 artifact-<标题>-<token>/transcript.txt
            transcript_files = sorted(rel_tmp.glob("**/transcript.txt")) if rel_tmp.exists() else []
            transcript = ""
            if transcript_files:
                transcript = transcript_files[0].read_text(encoding="utf-8", errors="ignore")
            elif detail:
                transcript = (detail or {}).get("data", {}).get("transcript", "")
            transcript = _strip_html(transcript)
            if transcript.strip():
                date = datetime.now(CST).strftime("%Y-%m-%d")
                save_note("meetings", date, "feishu_meeting", title, transcript,
                          extra_tags=["meeting", "lark"],
                          meta={"minute_token": token},
                          dedup_key=f"minute_token: {token}",
                          vault=vault)
                count += 1
    finally:
        # 清理临时转录目录并恢复 cwd
        import shutil
        tmp_path = meetings_dir / rel_tmp
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)
        os.chdir(prev_cwd)
    return count


# ---- 本机录音（whisper） ---------------------------------------------------

def collect_recordings(cfg: dict, dry_run: bool, vault: Path) -> int:
    if not (cfg.get("enabled", {}).get("recordings", False)):
        print("[skip] recordings 未启用", file=sys.stderr)
        return 0
    rc = cfg.get("recordings", {})
    dirs = [Path(os.path.expanduser(d)) for d in rc.get("dirs", [])]
    model = rc.get("model", "base")
    language = rc.get("language", "zh")
    exts = (".mp3", ".m4a", ".wav", ".ogg", ".flac")
    count = 0
    for d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.rglob("*")):
            if f.suffix.lower() not in exts:
                continue
            if f.with_suffix(".done").exists():
                continue
            print(f"[whisper] {f}", file=sys.stderr)
            if dry_run:
                continue
            try:
                out = subprocess.run(
                    ["whisper", str(f), "--model", model, "--language", language,
                     "--output_format", "txt", "--output_dir", str(d)],
                    capture_output=True, text=True, timeout=600,
                )
            except FileNotFoundError:
                print("[error] 未安装 whisper CLI（pip install openai-whisper）", file=sys.stderr)
                return count
            except subprocess.TimeoutExpired:
                print(f"[error] whisper 超时：{f}", file=sys.stderr)
                continue
            txt = d / f"{f.stem}.txt"
            if txt.exists():
                body = txt.read_text(encoding="utf-8")
                date = datetime.fromtimestamp(f.stat().st_mtime, CST).strftime("%Y-%m-%d")
                save_note("recordings", date, "recording", f.stem, body,
                          extra_tags=["whisper"], vault=vault)
                f.with_suffix(".done").touch()
                count += 1
    return count


# ---- 主流程 ----------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="多源上下文采集器（驱动 QClaw 联动）")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--only", choices=["chat", "meetings", "recordings"],
                    help="只跑某一类来源")
    ap.add_argument("--days", type=int, default=7, help="聊天/企微拉取最近 N 天")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要执行的命令")
    args = ap.parse_args()

    cfg = load_config(args.config)
    vault = vault_root(cfg)
    print(f"[info] vault={vault}", file=sys.stderr)

    totals = {}
    if args.only in (None, "chat"):
        totals["feishu"] = collect_feishu(cfg, args.days, args.dry_run, vault)
        totals["wecom"] = collect_wecom(cfg, args.days, args.dry_run, vault)
    if args.only in (None, "meetings"):
        totals["feishu_meeting"] = collect_feishu_meeting(cfg, args.dry_run, vault)
    if args.only in (None, "recordings"):
        totals["recordings"] = collect_recordings(cfg, args.dry_run, vault)

    print("[done]", json.dumps({k: v for k, v in totals.items() if v is not None}),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
