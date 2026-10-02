"""test_web_server.py — web_server.py 接口层测试（不真正监听端口）。

覆盖：/api/health 一键自检的响应结构、核心/降级状态归类、路由分发。
用 Handler 子类 + 假 _send_json 直接调用 handler 方法，避免起服务。
"""
import json
import os
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import web_server  # noqa: E402


class _FakeHandler(web_server.Handler):
    """不绑定 socket 的 Handler，只记录 _send_json 的输出。"""

    def __init__(self):  # noqa: D107
        self.responses = []

    def _send_json(self, obj, status=200):  # noqa: D102
        self.responses.append({"status": status, "body": obj})


class HealthCheckTests(unittest.TestCase):
    """GET /api/health 的结构化自检。"""

    def setUp(self):
        self.h = _FakeHandler()

    def test_health_check_returns_structured_payload(self):
        self.h._handle_health_check()
        self.assertEqual(len(self.h.responses), 1)
        resp = self.h.responses[0]
        self.assertEqual(resp["status"], 200)
        body = resp["body"]
        for key in ("ok", "status", "checks"):
            self.assertIn(key, body)
        self.assertIsInstance(body["checks"], list)
        self.assertTrue(body["checks"], "checks 不应为空")
        for c in body["checks"]:
            self.assertIn("name", c)
            self.assertIn("ok", c)
            self.assertIn("detail", c)

    def test_health_check_covers_required_categories(self):
        self.h._handle_health_check()
        names = {c["name"] for c in self.h.responses[0]["body"]["checks"]}
        for required in ("mood_web.html", "face_mood_web.html",
                         "vision_face_mood", "mood_dir", "camera_device"):
            self.assertIn(required, names)

    def test_health_status_degraded_when_camera_fails(self):
        """摄像头失败时整体应降级而非报错（网页功能不受影响）。"""
        self.h._handle_health_check()
        body = self.h.responses[0]["body"]
        cam = next(c for c in body["checks"] if c["name"] == "camera_device")
        if not cam["ok"]:
            self.assertEqual(body["status"], "degraded")
            self.assertTrue(body["ok"], "摄像头故障不应把核心服务标记为不可用")
        else:
            # 摄像头正常但可选后端（macOS Vision）在非 macOS 平台不可用 → 允许 degraded
            self.assertIn(body["status"], ("ok", "degraded"))
            self.assertTrue(body["ok"], "摄像头正常时核心服务应可用")


class RoutingTests(unittest.TestCase):
    """API 路由静态检查：确保 /api/health 已注册。"""

    def test_health_route_registered(self):
        with open(os.path.join(ROOT, "web_server.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('"/api/health"', src)


class MoodCacheTests(unittest.TestCase):
    """/api/mood/range 的聚合缓存：向已存在的文件追加也必须让缓存失效。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mood_dir = os.path.join(self.tmp, "mood")
        os.makedirs(self.mood_dir)
        self._orig_wiki = web_server.WIKI_DIR
        web_server.WIKI_DIR = self.tmp
        web_server._mood_cache["sig"] = None
        web_server._mood_cache["days_data"] = []

    def tearDown(self):
        web_server.WIKI_DIR = self._orig_wiki
        web_server._mood_cache["sig"] = None
        web_server._mood_cache["days_data"] = []

    def _write(self, day, records):
        with open(os.path.join(self.mood_dir, day + ".json"), "w", encoding="utf-8") as f:
            json.dump(records, f)

    def test_append_to_existing_file_invalidates_cache(self):
        """当天已有记录后再追加必须能看到。

        回归：签名曾只用目录 mtime；而 POSIX 下向已存在文件追加只改文件 mtime，
        不改目录 mtime，于是当天第一条之后的所有记录都不会让缓存失效，
        情绪报表会整天停在旧数据。
        """
        self._write("2026-10-03", [{"mood": "开心"}])
        self.assertEqual(web_server._mood_range_cache_get()[0]["count"], 1)

        path = os.path.join(self.mood_dir, "2026-10-03.json")
        self._write("2026-10-03", [{"mood": "开心"}, {"mood": "平静"}])
        # 显式前移 mtime，确保可稳定检出（真实追加同样会更新文件 mtime）
        os.utime(path, (time.time() + 1, time.time() + 1))
        self.assertEqual(
            web_server._mood_range_cache_get()[0]["count"], 2,
            "向已存在文件追加后，缓存应失效并重新聚合")

    def test_new_day_file_creates_new_entry(self):
        self._write("2026-10-01", [{"mood": "开心"}])
        self.assertEqual(len(web_server._mood_range_cache_get()), 1)
        self._write("2026-10-02", [{"mood": "低落"}])
        self.assertEqual(len(web_server._mood_range_cache_get()), 2)

    def test_signature_changes_on_append(self):
        """签名本身应随文件更新而变化（只 stat，不读文件内容）。"""
        self._write("2026-10-03", [{"mood": "开心"}])
        sig1 = web_server._mood_signature(self.mood_dir)
        self._write("2026-10-03", [{"mood": "开心"}, {"mood": "平静"}])
        sig2 = web_server._mood_signature(self.mood_dir)
        self.assertNotEqual(sig1, sig2, "追加后签名必须变化")


if __name__ == "__main__":
    unittest.main()
