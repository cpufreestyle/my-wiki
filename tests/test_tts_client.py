#!/usr/bin/env python3
"""tests/test_tts_client.py — TTS 三后端客户端的请求形状与降级链

只允许标准库：本地 http.server 桩替代真实 Gemini / StepFun 端点，播放与 `say`
执行打桩，测试全程不触网、不读本机密钥。bare CI（未装第三方库）可直接跑。
"""
import base64
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _StubServer:
    """记录请求、按 responder 返回响应的一次性 HTTP 桩。"""

    def __init__(self):
        outer = self
        self.requests = []
        self.responder = lambda path, body: (500, "text/plain", b"unset")

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                outer.requests.append({
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": body,
                })
                status, ctype, payload = outer.responder(self.path, body)
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):  # 保持测试输出干净
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self):
        host, port = self.httpd.server_address[:2]
        return "http://{}:{}".format(host, port)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


def _env(**values):
    """清空 TTS 相关变量后注入测试值，避免读到本机真实配置。"""
    base = {k: v for k, v in os.environ.items()
            if not k.startswith(("GEMINI_", "STEPFUN_", "MYWIKI_TTS_"))
            and not k.upper().endswith("_PROXY")}
    base["GEMINI_TTS_CONFIG"] = "/nonexistent/gemini_tts_config.json"
    base.update(values)
    return mock.patch.dict(os.environ, base, clear=True)


def _gemini_payload(pcm):
    return json.dumps({
        "candidates": [{"content": {"parts": [{
            "inlineData": {
                "mimeType": "audio/L16;codec=pcm;rate=24000",
                "data": base64.b64encode(pcm).decode("ascii"),
            }
        }]}}]
    }).encode("utf-8")


class TTSClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stub = _StubServer()

    @classmethod
    def tearDownClass(cls):
        cls.stub.close()

    def setUp(self):
        import tts_client  # 延迟到用例内 import，便于 RED 阶段报出明确失败
        self.tts = tts_client
        self.logs = []
        patcher = mock.patch.object(tts_client, "_log", self.logs.append)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, True))
        self.stub.requests.clear()
        self.stub.responder = lambda path, body: (500, "text/plain", b"unset")

    def test_gemini_request_shape_and_wav_output(self):
        pcm = b"\x01\x02" * 480
        self.stub.responder = lambda path, body: (
            200, "application/json", _gemini_payload(pcm))
        with _env(GEMINI_API_KEY="g-key",
                  GEMINI_TTS_BASE_URL=self.stub.base + "/gemini",
                  GEMINI_TTS_MODEL="gemini-test-tts",
                  GEMINI_TTS_VOICE="algenib"):
            result = self.tts.speak("你好", providers=("gemini",),
                                    out_dir=self.tmp, play=False)

        request = self.stub.requests[-1]
        self.assertTrue(request["path"].startswith(
            "/gemini/models/gemini-test-tts:generateContent"))
        self.assertNotIn("key=", request["path"])
        self.assertEqual(request["headers"].get("X-Goog-Api-Key"), "g-key")
        body = json.loads(request["body"])
        self.assertEqual(body["contents"][0]["parts"][0]["text"], "你好")
        self.assertEqual(body["generationConfig"]["responseModalities"], ["AUDIO"])
        voice = body["generationConfig"]["speechConfig"]["voice_config"]
        self.assertEqual(voice["prebuilt_voice_config"]["voice_name"], "algenib")

        self.assertEqual(result.provider, "gemini")
        audio = Path(result.path).read_bytes()
        self.assertEqual(audio[:4], b"RIFF")
        self.assertEqual(len(audio), 44 + len(pcm))

    def test_stepfun_request_shape_and_audio_saved(self):
        audio = b"RIFF-stepfun-audio"
        self.stub.responder = lambda path, body: (200, "audio/wav", audio)
        with _env(STEPFUN_API_KEY="s-key",
                  STEPFUN_TTS_BASE_URL=self.stub.base + "/stepfun"):
            result = self.tts.speak("你好", providers=("stepfun",),
                                    out_dir=self.tmp, play=False)

        request = self.stub.requests[-1]
        self.assertEqual(request["path"], "/stepfun/audio/speech")
        self.assertEqual(request["headers"].get("Authorization"), "Bearer s-key")
        body = json.loads(request["body"])
        self.assertEqual(body["model"], "step-tts-mini")
        self.assertEqual(body["input"], "你好")
        self.assertEqual(body["voice"], "wenrounvsheng")
        self.assertEqual(body["response_format"], "wav")

        self.assertEqual(result.provider, "stepfun")
        self.assertEqual(Path(result.path).read_bytes(), audio)

    def test_provider_order_can_be_overridden_by_env(self):
        audio = b"RIFF-env-order"

        def responder(path, body):
            if path.startswith("/gemini/"):
                return (200, "application/json", _gemini_payload(b"\x00\x01" * 10))
            return (200, "audio/wav", audio)

        self.stub.responder = responder
        with _env(GEMINI_API_KEY="g-key", STEPFUN_API_KEY="s-key",
                  MYWIKI_TTS_PROVIDERS="stepfun",
                  GEMINI_TTS_BASE_URL=self.stub.base + "/gemini",
                  STEPFUN_TTS_BASE_URL=self.stub.base + "/stepfun"):
            result = self.tts.speak("你好", out_dir=self.tmp, play=False)

        self.assertEqual(result.provider, "stepfun")
        self.assertEqual(len(self.stub.requests), 1)
        self.assertTrue(self.stub.requests[0]["path"].startswith("/stepfun/"))

    def test_falls_back_to_stepfun_when_gemini_fails(self):
        audio = b"RIFF-fallback"

        def responder(path, body):
            if path.startswith("/gemini/"):
                return (500, "text/plain", b"boom")
            return (200, "audio/wav", audio)

        self.stub.responder = responder
        with _env(GEMINI_API_KEY="g-key", STEPFUN_API_KEY="s-key",
                  GEMINI_TTS_BASE_URL=self.stub.base + "/gemini",
                  STEPFUN_TTS_BASE_URL=self.stub.base + "/stepfun"):
            result = self.tts.speak("你好", out_dir=self.tmp, play=False)

        self.assertEqual(result.provider, "stepfun")
        self.assertEqual(len(self.stub.requests), 2)
        self.assertEqual(Path(result.path).read_bytes(), audio)

    def test_provider_without_key_is_skipped(self):
        audio = b"RIFF-no-gemini-key"
        self.stub.responder = lambda path, body: (200, "audio/wav", audio)
        with _env(STEPFUN_API_KEY="s-key",
                  STEPFUN_TTS_BASE_URL=self.stub.base + "/stepfun"):
            result = self.tts.speak("你好", providers=("gemini", "stepfun"),
                                    out_dir=self.tmp, play=False)

        self.assertEqual(result.provider, "stepfun")
        self.assertEqual(len(self.stub.requests), 1)
        self.assertTrue(self.stub.requests[0]["path"].startswith("/stepfun/"))

    def test_falls_back_to_say_when_remote_unconfigured(self):
        def fake_say(text, out_path, voice=None):
            Path(out_path).write_bytes(b"AIFF-say")

        with _env(), mock.patch.object(self.tts, "_run_say", side_effect=fake_say):
            result = self.tts.speak("你好", out_dir=self.tmp, play=False)

        self.assertEqual(result.provider, "say")
        self.assertEqual(Path(result.path).read_bytes(), b"AIFF-say")

    def test_remote_only_chain_raises_instead_of_falling_back_silently(self):
        with _env():
            with self.assertRaises(self.tts.TTSError):
                self.tts.speak("你好", providers=("gemini",), out_dir=self.tmp)

    def test_error_message_does_not_leak_api_key(self):
        self.stub.responder = lambda path, body: (500, "text/plain", b"boom")
        with _env(GEMINI_API_KEY="sk-SECRET-should-not-leak",
                  GEMINI_TTS_BASE_URL=self.stub.base + "/gemini"):
            with self.assertRaises(self.tts.TTSError) as ctx:
                self.tts.speak("你好", providers=("gemini",), out_dir=self.tmp)
        self.assertNotIn("sk-SECRET-should-not-leak", str(ctx.exception))

    def test_empty_text_is_rejected(self):
        with _env():
            with self.assertRaises(ValueError):
                self.tts.speak("   ", providers=("say",), out_dir=self.tmp)

    def test_wrap_wav_adds_header_but_preserves_existing_riff(self):
        pcm = b"\x00\x01" * 10
        wrapped = self.tts._wrap_wav(pcm)
        self.assertEqual(wrapped[:4], b"RIFF")
        self.assertEqual(len(wrapped), 44 + len(pcm))
        self.assertEqual(wrapped[24:28], b"\xc0\x5d\x00\x00")  # 24000 Hz 小端
        self.assertEqual(self.tts._wrap_wav(wrapped), wrapped)

    def test_play_audio_uses_afplay(self):
        with mock.patch.object(self.tts.subprocess, "run") as run:
            self.tts.play_audio("/tmp/example.wav")
        self.assertEqual(run.call_args[0][0], ["afplay", "/tmp/example.wav"])


if __name__ == "__main__":
    unittest.main()
