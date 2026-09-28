"""test_web_server.py — web_server.py 接口层测试（不真正监听端口）。

覆盖：/api/health 一键自检的响应结构、核心/降级状态归类、路由分发。
用 Handler 子类 + 假 _send_json 直接调用 handler 方法，避免起服务。
"""
import json
import os
import sys
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
            self.assertEqual(body["status"], "ok")


class RoutingTests(unittest.TestCase):
    """API 路由静态检查：确保 /api/health 已注册。"""

    def test_health_route_registered(self):
        with open(os.path.join(ROOT, "web_server.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('"/api/health"', src)


if __name__ == "__main__":
    unittest.main()
