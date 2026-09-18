#!/usr/bin/env python3
"""
web_server.py - MyWiki 统一本地服务器

同时提供:
  - 静态文件托管（mood_web.html / daily_web.html / reminder_web.html / voice-controller.js 等）
  - POST /api/voice/start   开始录音（后端用 ffmpeg 录系统麦克风）
  - POST /api/voice/stop    停止录音并识别，返回 { text, acoustics }
  - POST /api/mood          保存心情（与 mood_web.html 的 fetch 对应）
  - GET  /api/reminders/pending  兼容原 reminder_server

适用场景：
  在缺少浏览器 Web Speech API 的运行时（如 InkView / QuickJS），或想用
  Chrome 访问本地版网页时，让语音经「后端 ffmpeg + SpeechRecognition」工作。
  网页只需经本服务器加载（同域），voice-controller.js 会自动降级走后端。

依赖：ffmpeg（录音）+ SpeechRecognition（识别，需联网走 Google Web Speech）。
"""
import json
import os
import re
import sys
import functools
import threading
import tempfile
import subprocess
import time
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# 数据根目录（mood 等）跟随统一解析：环境变量 MYWIKI_ROOT > config/obsidian.json
# vault > 仓库根。静态文件仍托管在 ROOT（仓库根），仅数据目录用 WIKI_DIR，
# 避免配置 vault 后网页端把 mood 写到/读到错误位置（此前一直读 ROOT/mood）。
try:
    from wiki_paths import _resolve_wiki_dir
    WIKI_DIR = _resolve_wiki_dir()
except Exception:  # noqa: BLE001
    WIKI_DIR = ROOT

# 语音模块（ffmpeg / SpeechRecognition）缺失时仅语音接口降级，不阻断整个服务器
try:
    import voice_mood
except Exception:  # noqa: BLE001
    voice_mood = None

# 面部情绪识别（face_mood：MediaPipe）；缺失时 /api/face* 接口优雅降级
try:
    import face_mood
except Exception:  # noqa: BLE001
    face_mood = None

# 待办数据层（与桌面端共用同一份 vault/todos.json）
try:
    import wiki_data
except Exception:  # noqa: BLE001
    wiki_data = None

# 网页端 RAG 检索 / 知识图谱所需模块（缺失时接口优雅降级）
try:
    from rag import RAGEngine
except Exception:
    RAGEngine = None

# macOS Vision 人物分割（Apple 官方虚化同款；不可用时前端降级 MediaPipe）
try:
    from vision_segment import is_available as _vision_available, VisionSegmenter
except Exception:
    _vision_available = lambda: False
    VisionSegmenter = None

VOICE_WAV = os.path.join(tempfile.gettempdir(), "mywiki_voice_server.wav")
DEFAULT_DURATION = 8
MAX_DURATION = 30

# ---- 录音状态（全局锁，保证同一时刻只录一次） ----
_voice_lock = threading.Lock()
_voice_proc = None
_voice_running = False
_voice_result = None  # dict
# 录音/识别完成信号：stop 接口靠它等待，避免 sleep 轮询忙等（原实现最多阻塞 30s）
_voice_done = threading.Event()

# ---- RAG 引擎单例 ----
# 索引构建需扫描整个知识库（O(corpus)），此前每个请求都新建引擎并重建索引；
# 单例化后仅首次构建，之后按 TTL 周期性刷新以纳入新笔记。
_RAG_TTL = 60.0
_rag_engine = None
_rag_indexed_at = 0.0
_rag_lock = threading.Lock()
_rag_sig = None


def _vault_signature():
    """知识库变更签名：(.md 文件数, 最新 mtime)。

    只走 os.stat 不读文件内容，成本远低于全量重建（后者要读完所有笔记并分词）。
    """
    count = 0
    latest = 0.0
    skip = {".git", ".obsidian", "__pycache__", "node_modules", ".trash", "attachments"}
    for dirpath, dirnames, filenames in os.walk(WIKI_DIR):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            count += 1
            try:
                m = os.stat(os.path.join(dirpath, fn)).st_mtime
            except OSError:
                continue
            if m > latest:
                latest = m
    return count, latest


def _get_rag_engine():
    """获取 RAGEngine 单例（线程安全）；知识库无变化时跳过全量重建。"""
    global _rag_engine, _rag_indexed_at, _rag_sig
    if RAGEngine is None:
        return None
    with _rag_lock:
        if _rag_engine is None:
            eng = RAGEngine()
            eng.index()
            _rag_engine = eng
            _rag_indexed_at = time.time()
            _rag_sig = _vault_signature()
        elif time.time() - _rag_indexed_at > _RAG_TTL:
            try:
                # TTL 到期先比对签名，笔记没动就不重建（此前每 60s 无条件全量重建）
                sig = _vault_signature()
                if sig != _rag_sig:
                    _rag_engine.index()
                    _rag_sig = sig
            except Exception:
                pass  # 刷新失败沿用旧索引
            _rag_indexed_at = time.time()
    return _rag_engine

# ---- 知识图谱响应缓存（文件 mtime 未变则直接复用上次结果） ----
_graph_cache = {"path": None, "mtime": None, "payload": None}

# ---- mood 按日聚合缓存（签名 = mood/ 目录 mtime；写入新记录即失效） ----
_mood_cache = {"sig": None, "days_data": []}


def _mood_range_cache_get():
    """返回全量按日聚合（按日期升序）。签名未变直接命中，避免每次全量 IO。"""
    global _mood_cache
    mood_dir = os.path.join(WIKI_DIR, "mood")
    try:
        sig = os.stat(mood_dir).st_mtime if os.path.isdir(mood_dir) else None
    except OSError:
        sig = None
    if _mood_cache["sig"] == sig:
        return _mood_cache["days_data"]
    by_day = {}
    if sig is not None:
        for fn in os.listdir(mood_dir):
            if not fn.endswith(".json"):
                continue
            day = fn[:-5]
            try:
                with open(os.path.join(mood_dir, fn), "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                continue
            agg = by_day.setdefault(day, {"date": day, "count": 0, "moods": {}})
            for r in records if isinstance(records, list) else []:
                mood = str(r.get("mood") or "未知")
                agg["moods"][mood] = agg["moods"].get(mood, 0) + 1
                agg["count"] += 1
    days_data = [by_day[k] for k in sorted(by_day)]
    _mood_cache = {"sig": sig, "days_data": days_data}
    return days_data

# ---- macOS Vision 人物分割器（懒加载单例 + 锁串行化） ----
_vision_seg = None
_vision_lock = threading.Lock()


def _get_vision_segmenter():
    """获取 VisionSegmenter 单例；环境不支持时返回 None。"""
    global _vision_seg
    if VisionSegmenter is None or not _vision_available():
        return None
    if _vision_seg is None:
        with _vision_lock:
            if _vision_seg is None:
                try:
                    _vision_seg = VisionSegmenter()
                except Exception:
                    return None
    return _vision_seg

# ---- 摄像头状态（全局锁，保证同一时刻只采样一次；采样约 2 秒阻塞请求） ----
_face_lock = threading.Lock()


def _record_worker(duration):
    """后台线程：ffmpeg 录音 → 声学分析 → 文字识别，结果存入 _voice_result。"""
    global _voice_result, _voice_running, _voice_proc
    result = {"ok": False}
    try:
        if voice_mood is None:
            _voice_result = {"ok": False, "error": "语音模块未加载（缺少 ffmpeg/SpeechRecognition），仅图谱/检索可用。"}
            return
        ffmpeg = voice_mood.get_ffmpeg_path()
        if not ffmpeg:
            result = {"ok": False, "error": "未找到 ffmpeg，无法录音。"}
            return
        args = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                *voice_mood._ffmpeg_input_args(),
                "-t", str(duration), "-ar", "16000", "-ac", "1",
                "-c:a", "pcm_s16le", VOICE_WAV]
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _voice_proc = proc
        stdout, stderr = proc.communicate()  # 阻塞直到 -t 结束或被 terminate
        _voice_proc = None

        if not os.path.exists(VOICE_WAV) or os.path.getsize(VOICE_WAV) < 44:
            err = stderr.decode("utf-8", errors="replace").strip() if stderr else ""
            low = err.lower()
            if any(k in low for k in ("operation not permitted", "denied",
                                      "authorization", "microphone", "avcapture")):
                result = {"ok": False, "error": "麦克风权限被拒绝。请到「系统设置 › 隐私与安全性 "
                                                 "› 麦克风」，给运行本服务器的终端/应用开启权限后重试。"}
            elif err:
                result = {"ok": False, "error": "录音失败：" + err[:200]}
            else:
                result = {"ok": False, "error": "录音为空，请重试。"}
            return

        # 1) 声学分析（纯本地，先于文字识别）
        acoustics = voice_mood.analyze_voice_acoustics(VOICE_WAV)
        mood_hint = None
        if acoustics:
            m, conf, detail = voice_mood.acoustics_to_mood(acoustics)
            mood_hint = {"mood": m, "conf": conf, "detail": detail}

        # 2) 文字识别（Google Web Speech，需联网）
        text = None
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            recognizer.operation_timeout = 10
            with sr.AudioFile(VOICE_WAV) as source:
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="zh-CN")
        except Exception:
            text = None  # 识别失败仍可返回声学分析

        result = {"ok": True, "text": (text or "").strip(), "acoustics": mood_hint}
    except Exception as e:
        result = {"ok": False, "error": "语音处理失败：" + str(e)}
    finally:
        _voice_result = result
        _voice_running = False
        _voice_done.set()


class Handler(SimpleHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def end_headers(self):
        # 允许跨域（部分运行时以不同 origin 加载本页）
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        # 根路径 / 明确返回门户页 index.html（避免某些运行时回退到目录列表）
        if self.path in ("/", "/index.html"):
            self.path = "/index.html"
            return super().do_GET()
        # 浏览器自动请求的图标：返回 204 空响应，消除无谓 404
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        # API 路由
        if self.path.startswith("/api/rag"):
            self._handle_rag()
            return
        if self.path.startswith("/api/graph"):
            self._handle_graph()
            return
        if self.path == "/api/modules" or self.path.startswith("/api/modules?"):
            self._handle_modules()
            return
        if self.path.startswith("/api/mood/range"):
            self._handle_mood_range()
            return
        if self.path.startswith("/api/vision/status"):
            self._handle_vision_status()
            return
        if self.path.split("?")[0] == "/api/face/deps":
            self._handle_face_deps()
            return
        if self.path.split("?")[0] == "/api/todos":
            self._handle_todos_get()
            return
        return super().do_GET()

    def _handle_mood_range(self):
        """情绪历史聚合：GET /api/mood/range?days=30

        按日聚合 mood/<date>.json，返回 [{date, count, moods:{情绪:次数}}]，
        供情绪报表页绘制周/月曲线。
        数据层缓存：目录 mtime 签名未变时直接复用上次的按日聚合（当天的
        mood/<date>.json 写入会改变目录 mtime，自动失效）。
        """
        from urllib.parse import urlparse, parse_qs
        from datetime import datetime, timedelta
        qs = parse_qs(urlparse(self.path).query)
        try:
            days = max(1, min(int((qs.get("days") or ["30"])[0]), 365))
        except Exception:
            days = 30
        by_day = _mood_range_cache_get()
        start = datetime.now() - timedelta(days=days)
        result = [row for row in by_day if row["date"] >= start.strftime("%Y-%m-%d")]
        self._send_json({"ok": True, "days": days, "days_data": result})

    def _handle_vision_status(self):
        """报告 macOS Vision 人物分割是否可用（前端据此选择抠图引擎）。"""
        seg = _get_vision_segmenter()
        self._send_json({"ok": True, "available": seg is not None})

    # ---- 可用网页模块清单（供 index.html 动态渲染导航） ----
    # 每个模块：file=对应网页文件名；仅当该文件实际存在时才返回，
    # 因此新增/删除 *_web.html 页面后，入口会自动更新，无需改 HTML。
    MODULE_REGISTRY = [
        {"id": "reminder", "file": "reminder_web.html", "label": "快速提醒",
         "hint": "设置常用 / 自定义提醒", "emoji": "⏰", "color": "accent"},
        {"id": "daily", "file": "daily_web.html", "label": "每日日记",
         "hint": "记录当日随笔与心情", "emoji": "📝", "color": "green"},
        {"id": "mood", "file": "mood_web.html", "label": "心情记录",
         "hint": "语音 / 文字记录情绪", "emoji": "💡", "color": "orange"},
        {"id": "mood_report", "file": "mood_report_web.html", "label": "情绪报表",
         "hint": "周 / 月情绪曲线与统计", "emoji": "📈", "color": "green"},
        {"id": "face_mood", "file": "face_mood_web.html", "label": "面部情绪",
         "hint": "摄像头 + MediaPipe 人脸情绪识别", "emoji": "😊", "color": "pink"},
        {"id": "rag", "file": "rag_web.html", "label": "语义检索",
         "hint": "本地知识库问答", "emoji": "🔍", "color": "accent"},
        {"id": "graph", "file": "graph_web.html", "label": "知识图谱",
         "hint": "笔记关联网络", "emoji": "🕸️", "color": "green"},
        {"id": "todo", "file": "todo_web.html", "label": "待办清单",
         "hint": "任务优先级与截止日期", "emoji": "✅", "color": "accent"},
    ]

    def _handle_modules(self):
        modules = []
        for m in self.MODULE_REGISTRY:
            path = os.path.join(ROOT, m["file"])
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                modules.append({
                    "id": m["id"],
                    "file": m["file"],
                    "label": m["label"],
                    "hint": m["hint"],
                    "emoji": m["emoji"],
                    "color": m["color"],
                })
        self._send_json({"ok": True, "modules": modules})

    # ---- 语义检索（复用 rag.py 的 RAGEngine） ----
    def _handle_rag(self):
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        query = (qs.get("q") or [""])[0].strip()
        try:
            limit = int((qs.get("limit") or ["10"])[0])
        except Exception:
            limit = 10
        limit = max(1, min(limit, 30))
        if not query:
            self._send_json({"ok": True, "query": "", "hits": []})
            return
        if RAGEngine is None:
            self._send_json({"ok": False, "error": "rag 模块不可用"}, status=500)
            return
        try:
            eng = _get_rag_engine()
            if eng is None:
                self._send_json({"ok": False, "error": "rag 模块不可用"}, status=500)
                return
            hits = eng.search(query, limit)
            self._send_json({"ok": True, "query": query, "hits": hits})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    # ---- 知识图谱（读取 knowledge_graph.json，归一化 link 的 .md 后缀） ----
    def _graph_path(self):
        """定位 knowledge_graph.json 的可写副本。

        打包(.app)模式下签名包内文件不可改写（否则会破坏代码签名），
        因此优先使用用户目录里的副本；首次运行时从打包资源拷贝过去。
        """
        # 1) 包外可写副本（用户级 / 项目级可写目录）
        candidates = []
        app_support = os.path.expanduser("~/Library/Application Support/MyWiki")
        if sys.platform == "win32":
            app_support = os.path.expanduser("~/AppData/Local/MyWiki")
        candidates.append(os.path.join(app_support, "knowledge_graph.json"))
        # 源码/未打包模式：直接用仓库根目录的版本（可写）
        candidates.append(os.path.join(ROOT, "knowledge_graph.json"))
        for p in candidates:
            if os.path.exists(p):
                return p
        # 2) 都不存在：从打包资源(ROOT)拷贝到用户目录再返回
        src = os.path.join(ROOT, "knowledge_graph.json")
        if os.path.exists(src):
            try:
                os.makedirs(app_support, exist_ok=True)
                import shutil
                shutil.copyfile(src, candidates[0])
                return candidates[0]
            except Exception:
                pass
        return src  # 退化为只读资源路径

    def _handle_graph(self):
        gpath = self._graph_path()
        if not os.path.exists(gpath):
            self._send_json({"ok": False, "error": "未找到 knowledge_graph.json"}, status=404)
            return
        try:
            mtime = os.path.getmtime(gpath)
            if (_graph_cache["path"] == gpath and _graph_cache["mtime"] == mtime
                    and _graph_cache["payload"] is not None):
                self._send_json(_graph_cache["payload"])
                return
            with open(gpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            nodes = data.get("nodes", [])
            links = data.get("links", [])
            # 归一化：link 的 source/target 去掉 .md 后缀，与 node id 对齐
            norm = {n["id"] for n in nodes}
            clean_links = []
            for lk in links:
                s = (lk.get("source") or "").replace(".md", "")
                t = (lk.get("target") or "").replace(".md", "")
                if s in norm and t in norm:
                    clean_links.append({"source": s, "target": t})
            payload = {
                "ok": True,
                "stats": data.get("stats", {}),
                "nodes": nodes,
                "links": clean_links,
            }
            _graph_cache.update(path=gpath, mtime=mtime, payload=payload)
            self._send_json(payload)
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def do_POST(self):
        path = self.path.rstrip("/")
        if path == "/api/voice/start":
            self._handle_voice_start()
        elif path == "/api/voice/stop":
            self._handle_voice_stop()
        elif path == "/api/mood":
            self._handle_mood()
        elif path == "/api/face_mood":
            self._handle_face_mood()
        elif path == "/api/vision/segment":
            self._handle_vision_segment()
        elif path == "/api/vision/cutout":
            self._handle_vision_cutout()
        elif path == "/api/face/mood":
            self._handle_face_mood_capture()
        elif path == "/api/todos":
            self._handle_todos_post()
        else:
            self.send_error(404)

    def _handle_vision_segment(self):
        """接收一帧 JPEG，返回 macOS Vision 人像 alpha mask（RGBA PNG）。

        请求体为原始 JPEG 字节；响应 Content-Type 为 image/png。
        Vision 不可用时返回 503，前端自动降级浏览器端 MediaPipe。
        """
        body = self._read_body()
        if not body:
            self._send_json({"ok": False, "error": "缺少 JPEG 帧"}, status=400)
            return
        seg = _get_vision_segmenter()
        if seg is None:
            self._send_json({"ok": False, "error": "Vision 不可用"}, status=503)
            return
        try:
            with _vision_lock:
                png = seg.segment_jpeg_to_png(body)
            payload = png
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def _handle_voice_start(self):
        global _voice_running, _voice_result
        if _voice_running:
            self._send_json({"ok": False, "error": "正在录音中，请先停止。"})
            return
        try:
            data = json.loads(self._read_body() or b"{}")
            duration = int(data.get("duration", DEFAULT_DURATION))
        except Exception:
            duration = DEFAULT_DURATION
        duration = max(1, min(duration, MAX_DURATION))
        with _voice_lock:
            _voice_result = None
            _voice_running = True
            _voice_done.clear()
            threading.Thread(target=_record_worker, args=(duration,), daemon=True).start()
        self._send_json({"ok": True, "started": True, "duration": duration})

    def _handle_voice_stop(self):
        if not _voice_running:
            self._send_json({"ok": False, "error": "当前没有进行中的录音。"}, status=400)
            return
        # 终止 ffmpeg，促使后台线程结束并开始识别
        proc = _voice_proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        # 等待识别完成（最多 30s）。用事件等待替代 sleep 轮询，避免忙等占着请求线程。
        _voice_done.wait(timeout=30)
        self._send_json(_voice_result or {"ok": False, "error": "未获取到识别结果。"})

    @staticmethod
    def _append_mood_record(date, record):
        """向 mood/<date>.json 追加一条记录（文件不存在或损坏时重建列表）。"""
        mood_dir = os.path.join(WIKI_DIR, "mood")
        os.makedirs(mood_dir, exist_ok=True)
        fpath = os.path.join(mood_dir, date + ".json")
        records = []
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []
        records.append(record)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def _handle_vision_cutout(self):
        """接收一帧 JPEG，返回「人像透明背景」PNG（Accurate 档，原分辨率）。"""
        body = self._read_body()
        if not body:
            self._send_json({"ok": False, "error": "缺少 JPEG 帧"}, status=400)
            return
        seg = _get_vision_segmenter()
        if seg is None:
            self._send_json({"ok": False, "error": "Vision 不可用"}, status=503)
            return
        try:
            with _vision_lock:
                png = seg.cutout_jpeg_to_png(body)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(png)
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def _handle_mood(self):
        try:
            data = json.loads(self._read_body() or b"{}")
        except Exception:
            self._send_json({"ok": False, "error": "无效 JSON"}, status=400)
            return
        date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
        record = {k: data.get(k) for k in ("time", "mood", "text", "confidence", "reason")}
        try:
            self._append_mood_record(date, record)
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def _handle_face_mood(self):
        """接收浏览器端 MediaPipe FaceLandmarker 的人脸情绪识别结果并落盘到 mood/。

        请求体字段：date, time, emotion(情绪标签), confidence(0-1),
        note(可选备注), features(可选：关键 blendshape 字典，用于可解释性)。
        与文本/语音情绪共用 mood/<date>.json，追加一条 source='face' 记录。
        """
        try:
            data = json.loads(self._read_body() or b"{}")
        except Exception:
            self._send_json({"ok": False, "error": "无效 JSON"}, status=400)
            return
        if not data.get("emotion"):
            self._send_json({"ok": False, "error": "缺少 emotion 字段"}, status=400)
            return
        date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
        # features 可能较大，仅保留数值类便于回看，多余的忽略
        features = data.get("features") or {}
        if isinstance(features, dict):
            features = {k: round(float(v), 3) for k, v in features.items() if isinstance(v, (int, float))}
        else:
            features = {}
        record = {
            "time": data.get("time") or datetime.now().strftime("%H:%M:%S"),
            "mood": data.get("emotion"),
            "text": data.get("note") or "",
            "confidence": data.get("confidence"),
            "reason": data.get("reason") or (", ".join(f"{k}={v}" for k, v in features.items()) if features else ""),
            "source": "face",
            "features": features,
        }
        try:
            self._append_mood_record(date, record)
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    # ---- 面部情绪识别（服务端采样版：face_mood 模块 + 摄像头） ----
    # 与上面的 /api/face_mood（浏览器端识别后落盘）是两条独立路径；
    # 两者若同名会互相覆盖，故此处命名为 _capture。
    def _handle_face_deps(self):
        """GET /api/face/deps：反馈 mediapipe / cv2 依赖是否可用。"""
        if face_mood is None:
            self._send_json({"ok": False, "error": "face_mood 模块不可用"}, status=503)
            return
        mp_ok, cv_ok = face_mood.deps_status()
        self._send_json({"ok": True, "mediapipe": mp_ok, "cv2": cv_ok})

    def _handle_face_mood_capture(self):
        """POST /api/face/mood：服务端摄像头采样约 2 秒 → 返回面部情绪。

        同一时刻只允许一次采样。
        """
        if face_mood is None:
            self._send_json({"ok": False, "error": "face_mood 模块不可用"}, status=503)
            return
        if not _face_lock.acquire(blocking=False):
            self._send_json({"ok": False, "error": "正在识别中，请稍候。"}, status=400)
            return
        try:
            result = face_mood.capture_and_analyze()
        finally:
            _face_lock.release()
        if "error" in result:
            self._send_json({"ok": False, "error": result["error"]}, status=400)
            return
        self._send_json({"ok": True, "face": result})

    # ---- 待办清单（复用桌面端 wiki_data，落盘同一份 vault/todos.json） ----
    def _handle_todos_get(self):
        """GET /api/todos：返回排序后的全部待办。"""
        if wiki_data is None:
            self._send_json({"ok": False, "error": "wiki_data 不可用"}, status=503)
            return
        self._send_json({"ok": True, "todos": wiki_data.sort_todos(wiki_data.load_todos())})

    def _handle_todos_post(self):
        """POST /api/todos：action = add / toggle / delete。"""
        if wiki_data is None:
            self._send_json({"ok": False, "error": "wiki_data 不可用"}, status=503)
            return
        try:
            data = json.loads(self._read_body() or b"{}")
        except Exception:
            self._send_json({"ok": False, "error": "无效 JSON"}, status=400)
            return
        action = data.get("action")
        try:
            if action == "add":
                todo = wiki_data.add_todo(
                    data.get("text", ""), data.get("priority", "medium"), data.get("due", ""))
                self._send_json({"ok": True, "todo": todo})
            elif action == "toggle":
                todo = wiki_data.toggle_todo(int(data.get("id")))
                self._send_json({"ok": bool(todo), "todo": todo})
            elif action == "delete":
                self._send_json({"ok": wiki_data.delete_todo(int(data.get("id")))})
            else:
                self._send_json({"ok": False, "error": "未知 action"}, status=400)
        except (ValueError, TypeError) as e:
            self._send_json({"ok": False, "error": str(e)}, status=400)

    def log_message(self, fmt, *args):
        pass  # 静默


def make_server(port=8082, root=None):
    """构造但未启动服务器（供 GUI 在同一进程内线程启动，避免 chdir 影响主程序）。

    显式指定 directory：打包(.app)模式经 make_server+serve_forever 启动时
    不会执行 run_server 的 os.chdir，静态文件查找若依赖 CWD 将全部 404，
    且 open_web_version 的 urlopen 探测会误判「服务器未启动」。
    """
    handler = functools.partial(Handler, directory=root or ROOT)
    return ThreadingHTTPServer(("0.0.0.0", port), handler)


def run_server(port=8082):
    os.chdir(ROOT)
    server = make_server(port)
    print("MyWiki 本地服务器已启动：")
    print("  总入口:   <INTERNAL_LINK_REMOVED>")
    print("  心情页:   <INTERNAL_LINK_REMOVED>")
    print("  日记页:   <INTERNAL_LINK_REMOVED>")
    print("  提醒页:   <INTERNAL_LINK_REMOVED>")
    print("  检索页:   <INTERNAL_LINK_REMOVED>")
    print("  图谱页:   <INTERNAL_LINK_REMOVED>")
    print("接口:     GET /api/rag?q=...   |   GET /api/graph")
    print("语音接口:   POST /api/voice/start  |  POST /api/voice/stop")
    print("面部接口:   GET  /api/face/deps    |  POST /api/face/mood（需安装 mediapipe + opencv-python）")
    print("（首次使用请允许终端/应用的麦克风权限；语音识别需联网）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


def main():
    p = 8082
    if len(sys.argv) > 1:
        try:
            p = int(sys.argv[1])
        except Exception:
            pass
    run_server(p)


if __name__ == "__main__":
    main()
