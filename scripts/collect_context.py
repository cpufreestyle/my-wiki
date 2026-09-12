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
import shutil
import subprocess
import sys
import time
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

# 单次 CLI 调用超时（秒）
CLI_TIMEOUT = 120

# 授权失效的特征串：命中即判为确定性错误，快速失败而不做无意义重试
_AUTH_MARKERS = ("need_user_authorization", "token_missing", "invalid_access_token",
                 "invalid_token", "token expired", "authentication")


def _looks_like_auth_error(text: str) -> bool:
    """判断 CLI 报错是否为授权失效（而非网络抖动 / 服务瞬时故障）。"""
    low = (text or "").lower()
    return any(m in low for m in _AUTH_MARKERS)


def _auth_alert_text(cli: Path) -> str:
    """按 CLI 类型给出可直接执行的重新授权指引。"""
    path = str(cli).lower()
    if "lark" in path:
        return "请执行 lark-cli auth login 重新授权（Device Flow，需人工交互）"
    if "wecom" in path:
        return "请确认企业微信 CLI 登录态是否失效"
    return "请重新登录对应 CLI 账号后重跑"


# 媒体类消息：正文为空时给占位提示，避免整条消息被静默丢弃
_MEDIA_TYPES = ("image", "file", "audio", "media", "video", "sticker")

# ---- 增量 / 状态辅助 -------------------------------------------------------

STATE_FILE = REPO / "config" / ".collect_backoff.json"
# dedup 索引（dedup_key -> 文件名）：避免每轮对 vault 做 O(n) 全目录全文扫描
INDEX_FILE = REPO / "config" / ".collect_index.json"
# 结构化运行日志（每轮一行 JSON）：供趋势分析与告警，替代靠人肉读 stdout
LOG_FILE = REPO / "config" / ".collect_log.jsonl"


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


# ---- 结果计数 --------------------------------------------------------------

# save_note 的动作 -> 统计键
_ACTION_KEYS = {"write": "created", "append": "appended",
                "update": "updated", "skip": "skipped"}


def _new_counts() -> dict:
    """各类来源统一的计数容器。"""
    return {"created": 0, "appended": 0, "updated": 0, "skipped": 0, "errors": 0}


def _count_action(counts: dict, report: dict) -> None:
    """按 save_note 回报的 action 累加计数。"""
    key = _ACTION_KEYS.get(str(report.get("action", "")), "skipped")
    counts[key] = counts.get(key, 0) + 1


def _set_action(report: dict | None, action: str) -> None:
    """把本次写入动作回填给调用方（report 为 None 时静默跳过）。"""
    if isinstance(report, dict):
        report["action"] = action


def _touched(counts: dict) -> int:
    """实际产生写入（新建 / 追加 / 更新）的条目数，不含 skip。"""
    return counts.get("created", 0) + counts.get("appended", 0) + counts.get("updated", 0)


# ---- dedup 索引（替代 O(n) 全目录全文扫描）----------------------------------

_INDEX_CACHE: dict | None = None
_INDEX_DIRTY = False


def _load_index() -> dict:
    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:  # noqa: BLE001
        pass
    return {}


def _reset_index_cache() -> None:
    """清空内存索引缓存（供测试与 main 收尾使用）。"""
    global _INDEX_CACHE, _INDEX_DIRTY
    _INDEX_CACHE = None
    _INDEX_DIRTY = False


def _index_map(category: str) -> dict:
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        _INDEX_CACHE = _load_index()
    m = _INDEX_CACHE.get(category)
    if not isinstance(m, dict):
        m = {}
        _INDEX_CACHE[category] = m
    return m


def _index_put(category: str, dedup_key: str, path: Path) -> None:
    """记录 dedup_key -> 文件名，并标记索引待落盘。"""
    global _INDEX_DIRTY
    m = _index_map(category)
    if m.get(dedup_key) != path.name:
        m[dedup_key] = path.name
        _INDEX_DIRTY = True


def _flush_index() -> None:
    """把内存索引写回磁盘（无变更则跳过）。"""
    global _INDEX_DIRTY
    if _INDEX_DIRTY and _INDEX_CACHE is not None:
        try:
            INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
            INDEX_FILE.write_text(
                json.dumps(_INDEX_CACHE, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        _INDEX_DIRTY = False


def _note_has_key(path: Path, dedup_key: str) -> bool:
    """仅在前言（frontmatter）区间匹配 dedup_key，避免误命中正文里的同名字样。"""
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return False
    if not txt.startswith("---"):
        return False
    end = txt.find("\n---", 3)
    if end < 0:
        return False
    return dedup_key in txt[3:end]


def _find_existing(vault: Path, category: str, dedup_key: str) -> Path | None:
    """按 dedup_key 找同一条已有笔记，返回路径或 None。

    先查 dedup 索引（O(1)）；索引缺失/失效时回退全目录扫描并回填索引，
    因此首次运行或索引被删也能自愈。
    """
    cat_dir = vault / category
    if not cat_dir.exists():
        return None
    mapped = _index_map(category).get(dedup_key)
    if mapped:
        cand = cat_dir / mapped
        if cand.exists() and _note_has_key(cand, dedup_key):
            return cand
        _index_map(category).pop(dedup_key, None)  # 索引失效，回退扫描
    for existing in sorted(cat_dir.glob("*.md")):
        if _note_has_key(existing, dedup_key):
            _index_put(category, dedup_key, existing)
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


def _wecom_should_skip(state: dict) -> tuple[bool, str]:
    """连续失败 / 连续无数据且今日已尝试过 -> (是否退避, 原因)。

    注意：调用失败（登录态 / 授权失效）与「确实没有消息」是两回事，
    两者分开计数，避免真故障被当成"最近没消息"而静默掩盖。
    """
    today = datetime.now(CST).strftime("%Y-%m-%d")
    if state.get("wecom_last_attempt_date") != today:
        return False, ""
    er = state.get("wecom_consecutive_error", 0)
    if er >= 3:
        return True, f"调用失败连续 {er} 次"
    ce = state.get("wecom_consecutive_empty", 0)
    if ce >= 3:
        return True, f"无数据连续 {ce} 次"
    return False, ""


def _wecom_record(state: dict, had_data: bool, error: bool = False) -> None:
    """记录企微本轮结果，更新连续计数与退避状态。

    error=True 表示 CLI 调用失败（可能未登录 / 授权过期 / 网络异常），
    只累加 wecom_consecutive_error，不污染 wecom_consecutive_empty。
    """
    today = datetime.now(CST).strftime("%Y-%m-%d")
    if had_data:
        state["wecom_consecutive_empty"] = 0
        state["wecom_consecutive_error"] = 0
    elif error:
        ce = state.get("wecom_consecutive_error", 0) + 1
        state["wecom_consecutive_error"] = min(ce, 999)
        print(f"[error] 企业微信调用失败（非「无消息」），已连续 {ce} 次", file=sys.stderr)
        if ce >= 3:
            print(f"[alert] 企业微信连续 {ce} 次调用失败，疑似登录态 / 授权失效，"
                  f"请手动跑 get_msg_chat_list 验证", file=sys.stderr)
    else:
        ce = state.get("wecom_consecutive_empty", 0) + 1
        state["wecom_consecutive_empty"] = min(ce, 999)
        if ce >= 3:
            print(f"[warn] 企业微信连续 {ce} 次无数据，进入每日退避，今日不再重试",
                  file=sys.stderr)
    state["wecom_last_attempt_date"] = today
    _save_state(state)


def _effective_days(state: dict, days: int) -> int:
    """按上次运行时间放大拉取窗口，避免长时间未运行时静默丢消息。

    _narrow_start 取 max(last_synced, now-days)：若两轮间隔超过 days，
    窗口外的未同步消息将永远追不回来，因此这里把 days 放大到实际间隔。
    """
    last = state.get("last_run_at")
    if not last:
        return days
    try:
        last_dt = datetime.fromisoformat(str(last))
    except Exception:  # noqa: BLE001
        return days
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=CST)
    gap_days = (datetime.now(CST) - last_dt).total_seconds() / 86400
    if gap_days > days:
        eff = int(gap_days) + 1
        print(f"[warn] 距上轮运行 {gap_days:.1f} 天 > 拉取窗口 {days} 天，"
              f"本轮回退到 {eff} 天以补齐空档（避免丢消息）", file=sys.stderr)
        return eff
    return days


def _record_run(state: dict) -> None:
    """记录本次运行时间，供下一轮计算空档。"""
    state["last_run_at"] = datetime.now(CST).isoformat(timespec="seconds")
    _save_state(state)


def _append_run_log(record: dict) -> None:
    """把本轮结果追加到 JSONL 运行日志（失败不影响主流程）。"""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


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

def _run_cli(cli: Path, *args: str, dry_run: bool = False,
             retries: int = 1, cwd: Path | None = None) -> dict | None:
    """运行 QClaw 内置 CLI，返回解析后的 JSON（失败返回 None）。

    可靠性约定：
    - 失败（超时 / 非 0 退出且无 stdout）按指数退避重试 `retries` 次（1s、2s…），
      避免一次网络抖动就静默丢一整轮采集。
    - 授权失效（need_user_authorization / token_missing）是确定性错误，
      直接快速失败并升级为 [alert]，不做无意义重试。
    - cwd 用于替代 os.chdir，避免污染进程全局工作目录。
    """
    if not QCLOW_NODE.exists() or not cli.exists():
        print(f"[skip] 缺少 QClaw 运行时：node={QCLOW_NODE} cli={cli}", file=sys.stderr)
        return None
    cmd = [str(QCLOW_NODE), str(cli), *args]
    print(f"[run] {' '.join(cmd)}", file=sys.stderr)
    if dry_run:
        return None
    attempt = 0
    while True:
        err = ""
        fatal = False
        stdout: str | None = None
        try:
            out = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=CLI_TIMEOUT, cwd=cwd)
        except subprocess.TimeoutExpired:
            err = f"超时（{CLI_TIMEOUT}s）"
        except OSError as e:
            err = f"无法执行：{e}"
        else:
            if out.returncode != 0 and not out.stdout.strip():
                err = f"失败: {out.stderr[:300]}"
                fatal = _looks_like_auth_error(out.stderr)
            else:
                stdout = out.stdout
        if stdout is not None:
            return _parse_cli_json(stdout)
        if fatal or attempt >= retries:
            if fatal:
                print(f"[alert] {cli.name} 授权失效（确定性错误，不重试）："
                      f"{_auth_alert_text(cli)}", file=sys.stderr)
            print(f"[error] {cli.name} {err}", file=sys.stderr)
            return None
        attempt += 1
        delay = 2 ** (attempt - 1)
        print(f"[warn] {cli.name} {err}；{delay}s 后重试（第 {attempt}/{retries} 次）",
              file=sys.stderr)
        time.sleep(delay)


def _parse_cli_json(raw: str) -> dict | None:
    """解析 CLI 输出的 JSON（可能多行，或前面混有日志行）。"""
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 退一步：取第一个 "{" 开始的 JSON 片段
        start = raw.find("{")
        if start >= 0:
            try:
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
              dedup_key: str | None = None, append: bool = False,
              report: dict | None = None) -> Path:
    """写入一条分源笔记（frontmatter + 正文）。返回文件路径。

    dedup_key: 若提供，则在 cat_dir 下查找 frontmatter 含该 key 的已有笔记，
               找到则原地更新（不新增），避免重复累积。
    meta: 额外写入 frontmatter 的键值（如 minute_token / last_synced）。
    append: 命中已有笔记时，仅追加正文中「不在旧文件里」的新行，避免边界重复；
            配合 dedup_key 实现增量更新。
    report: 若提供 dict，回填本次动作 action ∈ {write, append, update, skip}，
            供调用方统计「真实新增量」而非被 frontmatter 更新刷高的数字。
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
            _set_action(report, "skip")
            return path
        path.write_text(new_text, encoding="utf-8")
        print((f"[append] {path}" if add_lines else f"[update] {path}"), file=sys.stderr)
        _set_action(report, "append" if add_lines else "update")
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
        _set_action(report, "skip")
        return path
    path.write_text(new_text, encoding="utf-8")
    print(f"[write] {path}", file=sys.stderr)
    # 仅当 dedup_key 真的落进前言时才登记索引：否则索引指向一个查不到的 key，
    # 下轮会命中失败再回退全目录扫描（并污染索引）。
    if dedup_key and _note_has_key(path, dedup_key):
        _index_put(category, dedup_key, path)
    _set_action(report, "write")
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

def _fetch_lark_messages(cid: str, start_iso: str, cfg: dict,
                         dry_run: bool) -> tuple[list[dict], bool, bool]:
    """分页拉取单个会话的消息。

    返回 (消息列表, 是否被页数上限截断, 是否调用失败)。
    截断时调用方不应推进 last_synced，否则未拉取区间的消息会被永久跳过。
    """
    fs = cfg.get("feishu", {})
    page_size = int(fs.get("page_size", 50))
    max_pages = int(fs.get("max_pages", 20))
    items: list[dict] = []
    token: str | None = None
    for _ in range(max_pages):
        args = ["im", "+chat-messages-list", "--chat-id", cid,
                "--start", start_iso, "--order", "asc",
                "--page-size", str(page_size), "--as", "user"]
        if token:
            args += ["--page-token", token]
        resp = _run_cli(LARK_CLI, *args, dry_run=dry_run)
        if dry_run:
            return items, False, False
        first_page = not items
        if resp is None:
            # 首页失败才算调用失败；后续页失败则保留已拉到的部分
            return items, False, first_page
        data = resp.get("data")
        if not isinstance(data, dict):
            return items, False, first_page
        if first_page and "messages" not in data:
            print(f"[warn] 会话消息返回结构异常：{cid}", file=sys.stderr)
            return items, False, True
        batch = data.get("messages") or []
        items.extend(batch)
        token = data.get("page_token") or data.get("next_page_token")
        if not token or len(batch) < page_size:
            return items, False, False
    # 达到页数上限仍有更多 -> 截断
    return items, True, False


def _fetch_lark_chats(cfg: dict, dry_run: bool) -> tuple[list[dict], bool]:
    """分页拉取飞书会话列表，返回 (会话列表, 是否调用失败)。

    旧实现写死 --page-size 20：活跃会话超过 20 个时，排序靠后的会话
    永远进不了采集范围。这里改为翻页拉全，再由 max_chats 显式限量。
    """
    fs = cfg.get("feishu", {})
    page_size = int(fs.get("chat_page_size", 50))
    max_pages = int(fs.get("chat_max_pages", 3))
    chats: list[dict] = []
    token: str | None = None
    for _ in range(max_pages):
        args = ["im", "+chat-list", "--types", "group,p2p",
                "--sort", "active_time", "--page-size", str(page_size),
                "--as", "user"]
        if token:
            args += ["--page-token", token]
        resp = _run_cli(LARK_CLI, *args, dry_run=dry_run)
        if dry_run:
            return chats, False
        first_page = not chats
        if resp is None:
            return chats, first_page
        data = resp.get("data")
        if not isinstance(data, dict):
            return chats, first_page
        if first_page and "chats" not in data:
            print("[warn] 会话列表返回结构异常", file=sys.stderr)
            return chats, True
        batch = data.get("chats") or []
        chats.extend(batch)
        token = data.get("page_token") or data.get("next_page_token")
        if not token or len(batch) < page_size:
            return chats, False
    print(f"[warn] 会话列表超过 {max_pages} 页，仅取前 {len(chats)} 个",
          file=sys.stderr)
    return chats, False


def collect_feishu(cfg: dict, days: int, dry_run: bool, vault: Path) -> dict:
    counts = _new_counts()
    if not (cfg.get("enabled", {}).get("feishu", False)):
        print("[skip] feishu 未启用", file=sys.stderr)
        return counts
    # 1) 拉会话列表（分页，避免写死 page-size 造成的硬截断）
    chats, failed = _fetch_lark_chats(cfg, dry_run)
    if dry_run:
        return counts
    if failed:
        print("[error] 飞书 chat-list 调用失败（可能未登录 / 授权过期 / 网络异常）",
              file=sys.stderr)
        counts["errors"] += 1
        return counts
    if not chats:
        print("[info] 飞书无会话", file=sys.stderr)
        return counts
    max_chats = int(cfg.get("feishu", {}).get("max_chats", 20))
    if len(chats) > max_chats:
        print(f"[warn] 活跃会话 {len(chats)} 个 > max_chats={max_chats}，"
              f"本轮仅处理前 {max_chats} 个（其余轮次靠 active_time 排序轮到）",
              file=sys.stderr)
    for ch in chats[:max_chats]:
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
        # 2) 拉消息（分页拉全）
        items, truncated, failed = _fetch_lark_messages(cid, start_iso, cfg, dry_run)
        if dry_run:
            continue
        if failed:
            print(f"[error] 拉取会话消息失败：{name}（{cid}）", file=sys.stderr)
            counts["errors"] += 1
            continue
        if not items:
            continue
        if truncated:
            print(f"[warn] 会话「{name}」消息超过 max_pages 页，本轮未拉全："
                  f"last_synced 不推进，下轮继续（避免跳过未同步区间）",
                  file=sys.stderr)
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
            # 仅在本轮完整拉取时才推进 last_synced
            if max_ts and not truncated:
                meta["last_synced"] = max_ts
            body = "\n".join(lines)
            report: dict = {}
            save_note("chat", date, "feishu", name, body,
                      extra_tags=["lark", ch.get("chat_mode", "group")],
                      meta=meta,
                      dedup_key=f"chat_id: {cid}",
                      append=True,
                      vault=vault,
                      report=report)
            _count_action(counts, report)
    return counts


def _strip_html(text: str) -> str:
    """去掉 HTML 标签与常见转义字符（<b> &lt;b&gt; 等），保留可读文本。"""
    import re
    t = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _parse_json_lenient(s: str):
    """容错解析 JSON 字符串；失败返回 None。"""
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        return None


def _render_post(post: dict) -> str:
    """把飞书 post（富文本）JSON 渲染成可读文本。

    结构形如 {"title": "...", "content": [[{"tag": "text", "text": "..."}], ...]}，
    外层数组每项是一个段落，段落内按 tag 取文本 / 链接 / @ / 媒体占位。
    """
    lines: list[str] = []
    for row in post.get("content") or []:
        if not isinstance(row, list):
            continue
        seg: list[str] = []
        for node in row:
            if not isinstance(node, dict):
                continue
            tag = node.get("tag")
            if tag == "text":
                seg.append(str(node.get("text") or ""))
            elif tag == "a":
                seg.append(str(node.get("text") or node.get("href") or ""))
            elif tag == "at":
                seg.append("@" + str(node.get("user_name") or node.get("user_id") or ""))
            elif tag in ("img", "media", "file", "emotion"):
                seg.append(f"[{tag}]")
        line = "".join(seg).strip()
        if line:
            lines.append(line)
    title = str(post.get("title") or "").strip()
    if title and lines:
        return f"{title}：" + " / ".join(lines)
    return title or " / ".join(lines)


def _extract_lark_content(m: dict) -> str:
    """从 lark 消息结构里尽量抽出可读文本。

    lark-cli 返回的 content 通常是已渲染的字符串（纯文本或含 <card ...> 标签的
    markdown 片段）；post / merge_forward 则可能是原始 JSON，需要展开后再取用。
    媒体类消息返回占位提示，避免整条消息被静默丢弃。
    """
    c = m.get("content")
    mt = str(m.get("message_type") or m.get("msg_type") or "").lower()

    # post（富文本）/ merge_forward（合并转发）：content 可能是 JSON
    if mt in ("post", "merge_forward") and isinstance(c, str):
        parsed = _parse_json_lenient(c)
        if isinstance(parsed, dict):
            if mt == "merge_forward":
                title = str(parsed.get("title") or "").strip()
                return f"[合并转发] {title}".strip()
            rendered = _render_post(parsed)
            if rendered:
                return rendered
    if mt == "merge_forward":
        return "[合并转发]"  # 子消息需另拉，至少留占位不丢上下文

    if not isinstance(c, str):
        return f"[{mt}]" if mt in _MEDIA_TYPES else ""
    # 去掉 <card title="..."> 包裹标签，保留内部 markdown 文本
    txt = c.strip()
    if txt.startswith("<card"):
        end = txt.find(">")
        if end >= 0:
            txt = txt[end + 1:]
        if txt.endswith("</card>"):
            txt = txt[:-len("</card>")]
    txt = txt.strip()
    if not txt and mt in _MEDIA_TYPES:
        return f"[{mt}]"
    return txt


# ---- 企业微信采集 ----------------------------------------------------------

def collect_wecom(cfg: dict, days: int, dry_run: bool, vault: Path) -> dict:
    counts = _new_counts()
    if not (cfg.get("enabled", {}).get("wecom", False)):
        print("[skip] wecom 未启用", file=sys.stderr)
        return counts
    state = _load_state()
    skip, reason = _wecom_should_skip(state)
    if skip:
        print(f"[skip] 企业微信退避中（{reason}，今日已重试过），跳过本轮", file=sys.stderr)
        return counts
    start_iso = (datetime.now(CST) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    end_iso = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    # 1) 会话列表（企微仅支持 7 天，参数走 --json）
    lst = _run_cli(WECOM_CLI, "msg", "get_msg_chat_list", "--json",
                   json.dumps({"begin_time": start_iso, "end_time": end_iso}),
                   dry_run=dry_run)
    if dry_run:
        return counts
    if lst is None:
        print("[error] 企业微信 CLI 调用失败（可能未登录 / 授权过期 / 网络异常）",
              file=sys.stderr)
        _wecom_record(state, had_data=False, error=True)
        counts["errors"] += 1
        return counts
    # 企微返回包一层 MCP jsonrpc，真正数据在 result.content[].text（字符串）
    chats = _unwrap_mcp_text(lst).get("chats", []) if lst else []
    if not chats:
        print("[info] 企业微信无会话", file=sys.stderr)
        _wecom_record(state, had_data=False)
        return counts
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
            report: dict = {}
            save_note("chat", date, "wecom", name, "\n".join(lines),
                      extra_tags=["wecom"],
                      meta=meta,
                      dedup_key=f"conversation_id: {cid}",
                      append=True,
                      vault=vault,
                      report=report)
            _count_action(counts, report)
    _wecom_record(state, had_data=_touched(counts) > 0)
    return counts


# ---- 飞书会议妙记 ----------------------------------------------------------

def collect_feishu_meeting(cfg: dict, dry_run: bool, vault: Path) -> dict:
    counts = _new_counts()
    if not (cfg.get("enabled", {}).get("feishu_meeting", False)):
        print("[skip] feishu_meeting 未启用", file=sys.stderr)
        return counts
    days = int(cfg.get("feishu_meeting", {}).get("days", 14))
    start = (datetime.now(CST) - timedelta(days=days)).strftime("%Y-%m-%d")
    # 1) 搜索最近妙记（lark-cli minutes +search）
    lst = _run_cli(LARK_CLI, "minutes", "+search", "--start", start,
                   "--as", "user", "--page-size", "15", dry_run=dry_run)
    if dry_run:
        return counts
    if lst is None:
        print("[error] 妙记搜索失败（可能未登录 / 缺少 minutes:minutes.basic:read 授权）",
              file=sys.stderr)
        counts["errors"] += 1
        return counts
    items = (lst.get("data") or {}).get("items", []) or []
    if not items:
        print(f"[info] 飞书会议无妙记（最近 {days} 天搜索窗口内为空）", file=sys.stderr)
        return counts
    # +detail --transcript 要求 --output-dir 为「相对路径」，故把子进程 cwd 设为
    # vault/meetings（用 subprocess 的 cwd 参数，不再 os.chdir 污染全局工作目录）。
    meetings_dir = _ensure_dir(vault / "meetings")
    rel_tmp = Path(".minutes_tmp")
    tmp_path = meetings_dir / rel_tmp
    try:
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
                              "--output-dir", str(rel_tmp), dry_run=dry_run,
                              cwd=meetings_dir)
            if dry_run:
                continue
            # 转录落盘为 artifact-<标题>-<token>/transcript.txt
            transcript_files = sorted(tmp_path.glob("**/transcript.txt")) if tmp_path.exists() else []
            transcript = ""
            if transcript_files:
                transcript = transcript_files[0].read_text(encoding="utf-8", errors="ignore")
            elif detail:
                transcript = (detail or {}).get("data", {}).get("transcript", "")
            transcript = _strip_html(transcript)
            if not transcript.strip():
                if detail is None and not transcript_files:
                    print(f"[error] 获取妙记转录失败：{title}（{token}）", file=sys.stderr)
                    counts["errors"] += 1
                continue
            date = datetime.now(CST).strftime("%Y-%m-%d")
            report: dict = {}
            save_note("meetings", date, "feishu_meeting", title, transcript,
                      extra_tags=["meeting", "lark"],
                      meta={"minute_token": token},
                      dedup_key=f"minute_token: {token}",
                      vault=vault,
                      report=report)
            _count_action(counts, report)
    finally:
        # 清理临时转录目录（无需再恢复 cwd：已改用 subprocess 的 cwd 参数）
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)
    return counts


# ---- 本机录音（whisper） ---------------------------------------------------

def collect_recordings(cfg: dict, dry_run: bool, vault: Path) -> dict:
    counts = _new_counts()
    if not (cfg.get("enabled", {}).get("recordings", False)):
        print("[skip] recordings 未启用", file=sys.stderr)
        return counts
    rc = cfg.get("recordings", {})
    dirs = [Path(os.path.expanduser(d)) for d in rc.get("dirs", [])]
    model = rc.get("model", "base")
    language = rc.get("language", "zh")
    exts = (".mp3", ".m4a", ".wav", ".ogg", ".flac")
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
                counts["errors"] += 1
                return counts
            except subprocess.TimeoutExpired:
                print(f"[error] whisper 超时：{f}", file=sys.stderr)
                counts["errors"] += 1
                continue
            txt = d / f"{f.stem}.txt"
            if txt.exists():
                body = txt.read_text(encoding="utf-8")
                date = datetime.fromtimestamp(f.stat().st_mtime, CST).strftime("%Y-%m-%d")
                report: dict = {}
                save_note("recordings", date, "recording", f.stem, body,
                          extra_tags=["whisper"], vault=vault, report=report)
                f.with_suffix(".done").touch()
                _count_action(counts, report)
            else:
                print(f"[error] whisper 未产出转写文本：{f}", file=sys.stderr)
                counts["errors"] += 1
    return counts


# ---- 主流程 ----------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="多源上下文采集器（驱动 QClaw 联动）")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--only", choices=["chat", "meetings", "recordings"],
                    help="只跑某一类来源")
    ap.add_argument("--days", type=int, default=7, help="聊天/企微拉取最近 N 天")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要执行的命令")
    args = ap.parse_args()

    t0 = time.time()
    cfg = load_config(args.config)
    vault = vault_root(cfg)
    print(f"[info] vault={vault}", file=sys.stderr)

    # 距上轮间隔超过窗口时自动放大，避免静默丢消息
    days = _effective_days(_load_state(), args.days)

    totals: dict = {}
    if args.only in (None, "chat"):
        totals["feishu"] = collect_feishu(cfg, days, args.dry_run, vault)
        totals["wecom"] = collect_wecom(cfg, days, args.dry_run, vault)
    if args.only in (None, "meetings"):
        totals["feishu_meeting"] = collect_feishu_meeting(cfg, args.dry_run, vault)
    if args.only in (None, "recordings"):
        totals["recordings"] = collect_recordings(cfg, args.dry_run, vault)

    # 摘要：touched = 实际产生写入的条目（created + appended + updated）
    summary = {k: dict(v, touched=_touched(v)) for k, v in totals.items()}
    print("[done]", json.dumps(summary, ensure_ascii=False), file=sys.stderr)

    if not args.dry_run:
        _flush_index()
        _record_run(_load_state())  # 重新读取以合并采集过程中写入的企微状态
        _append_run_log({
            "ts": datetime.now(CST).isoformat(timespec="seconds"),
            "days": days,
            "duration_s": round(time.time() - t0, 1),
            "result": summary,
        })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
