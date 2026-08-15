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
import sys
import threading
import tempfile
import subprocess
import time
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# 语音模块（ffmpeg / SpeechRecognition）缺失时仅语音接口降级，不阻断整个服务器
try:
    import voice_mood
except Exception:  # noqa: BLE001
    voice_mood = None

# 网页端 RAG 检索 / 知识图谱所需模块（缺失时接口优雅降级）
try:
    from rag import RAGEngine
except Exception:
    RAGEngine = None

VOICE_WAV = os.path.join(tempfile.gettempdir(), "mywiki_voice_server.wav")
DEFAULT_DURATION = 8
MAX_DURATION = 30

# ---- 录音状态（全局锁，保证同一时刻只录一次） ----
_voice_lock = threading.Lock()
_voice_proc = None
_voice_running = False
_voice_result = None  # dict

# ---- RAG 引擎单例 ----
# 索引构建需扫描整个知识库（O(corpus)），此前每个请求都新建引擎并重建索引；
# 单例化后仅首次构建，之后按 TTL 周期性刷新以纳入新笔记。
_RAG_TTL = 60.0
_rag_engine = None
_rag_indexed_at = 0.0
_rag_lock = threading.Lock()


def _get_rag_engine():
    """获取 RAGEngine 单例（线程安全），刷新失败时沿用旧索引。"""
    global _rag_engine, _rag_indexed_at
    if RAGEngine is None:
        return None
    with _rag_lock:
        if _rag_engine is None:
            eng = RAGEngine()
            eng.index()
            _rag_engine = eng
            _rag_indexed_at = time.time()
        elif time.time() - _rag_indexed_at > _RAG_TTL:
            try:
                _rag_engine.index()
            except Exception:
                pass  # 刷新失败沿用旧索引
            _rag_indexed_at = time.time()
    return _rag_engine

# ---- 知识图谱响应缓存（文件 mtime 未变则直接复用上次结果） ----
_graph_cache = {"path": None, "mtime": None, "payload": None}


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
        return super().do_GET()

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
        {"id": "face_mood", "file": "face_mood_web.html", "label": "面部情绪",
         "hint": "摄像头 + MediaPipe 人脸情绪识别", "emoji": "😊", "color": "pink"},
        {"id": "rag", "file": "rag_web.html", "label": "语义检索",
         "hint": "本地知识库问答", "emoji": "🔍", "color": "accent"},
        {"id": "graph", "file": "graph_web.html", "label": "知识图谱",
         "hint": "笔记关联网络", "emoji": "🕸️", "color": "green"},
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
        else:
            self.send_error(404)

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
        # 等待识别完成（最多 ~30s）
        waited = 0.0
        while _voice_running and waited < 30:
            time.sleep(0.2)
            waited += 0.2
        self._send_json(_voice_result or {"ok": False, "error": "未获取到识别结果。"})

    @staticmethod
    def _append_mood_record(date, record):
        """向 mood/<date>.json 追加一条记录（文件不存在或损坏时重建列表）。"""
        mood_dir = os.path.join(ROOT, "mood")
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

    def log_message(self, fmt, *args):
        pass  # 静默


def make_server(port=8080):
    """构造但未启动服务器（供 GUI 在同一进程内线程启动，避免 chdir 影响主程序）。"""
    return ThreadingHTTPServer(("0.0.0.0", port), Handler)


def run_server(port=8080):
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
    print("（首次使用请允许终端/应用的麦克风权限；语音识别需联网）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


def main():
    p = 8080
    if len(sys.argv) > 1:
        try:
            p = int(sys.argv[1])
        except Exception:
            pass
    run_server(p)


if __name__ == "__main__":
    main()
