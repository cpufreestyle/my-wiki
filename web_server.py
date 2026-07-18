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
import voice_mood

VOICE_WAV = os.path.join(tempfile.gettempdir(), "mywiki_voice_server.wav")
DEFAULT_DURATION = 8
MAX_DURATION = 30

# ---- 录音状态（全局锁，保证同一时刻只录一次） ----
_voice_lock = threading.Lock()
_voice_proc = None
_voice_running = False
_voice_result = None  # dict


def _record_worker(duration):
    """后台线程：ffmpeg 录音 → 声学分析 → 文字识别，结果存入 _voice_result。"""
    global _voice_result, _voice_running, _voice_proc
    result = {"ok": False}
    try:
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

    def _handle_mood(self):
        try:
            data = json.loads(self._read_body() or b"{}")
        except Exception:
            self._send_json({"ok": False, "error": "无效 JSON"}, status=400)
            return
        date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
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
        records.append({k: data.get(k) for k in ("time", "mood", "text", "confidence", "reason")})
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def log_message(self, fmt, *args):
        pass  # 静默


def run_server(port=8080):
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("MyWiki 本地服务器已启动：")
    print("  心情页:   <INTERNAL_LINK_REMOVED>")
    print("  日记页:   <INTERNAL_LINK_REMOVED>")
    print("  提醒页:   <INTERNAL_LINK_REMOVED>")
    print("语音接口:   POST /api/voice/start  |  POST /api/voice/stop")
    print("（首次使用请允许终端/应用的麦克风权限；语音识别需联网）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    p = 8080
    if len(sys.argv) > 1:
        try:
            p = int(sys.argv[1])
        except Exception:
            pass
    run_server(p)
