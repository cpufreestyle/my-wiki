#!/usr/bin/env python3
"""
tests/test_vision_face_mood.py — macOS Vision 面部情绪后端单元测试

纯标准库实现（unittest），不需要 pyobjc / opencv / 摄像头，可在 CI 的 Linux
runner 上运行。守住三类回归：

1. vision_face_mood 模块的形状：导出 is_available / deps_status / extract_features /
   analyze_frames / capture_and_analyze，与 face_mood 同构（web_server 可按统一
   协议调用，且后端可互换）；
2. pyobjc 的 objc.varlist 陷阱：normalizedPoints 没有 __iter__，直接 for 迭代会
   SIGBUS，因此 _points 必须用 pointCount 索引取值，禁止写成 for p in val；
3. 子进程隔离约定：MediaPipe 的 Metal 委托失败时会 abort 整个进程，web_server
   不得在进程内调用 face_mood.capture_and_analyze，必须经 _run_face_worker 起
   子进程（否则一次失败会连带全部 HTTP 接口返回「面部识别请求失败」）。
"""
import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VISION_PATH = PROJECT_ROOT / "vision_face_mood.py"
FACE_MOOD_PATH = PROJECT_ROOT / "face_mood.py"
WEB_SERVER_PATH = PROJECT_ROOT / "web_server.py"

FEATURE_KEYS = ("smile", "mouth_open", "brow_eye", "brow_gap", "sad_brow",
                "eye_open")


def _load_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vision_face_mood_under_test",
                                                  VISION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class VisionModuleShapeTest(unittest.TestCase):
    """vision_face_mood.py 是否具备与 face_mood 对齐的接口。"""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_file_exists_with_docstring(self):
        self.assertTrue(VISION_PATH.exists(), "缺少 vision_face_mood.py")
        src = VISION_PATH.read_text(encoding="utf-8")
        self.assertIn("VNDetectFaceLandmarksRequest", src,
                      "Vision 后端应使用 Apple Vision 人脸关键点，而非 MediaPipe")
        self.assertNotIn("import mediapipe", src,
                         "Vision 后端不得依赖 MediaPipe（会 abort 进程）")

    def test_public_api(self):
        for name in ("is_available", "deps_status", "extract_features",
                     "analyze_frames", "capture_and_analyze", "main"):
            self.assertTrue(callable(getattr(self.mod, name, None)),
                            "缺少 {}()".format(name))

    def test_deps_status_shape(self):
        ok_v, ok_cv = self.mod.deps_status()
        self.assertIsInstance(ok_v, bool)
        self.assertIsInstance(ok_cv, bool)

    def test_analyze_frames_without_face_returns_error(self):
        # 空字节不是合法 JPEG，必须给出干净的 error 而不是抛异常
        out = self.mod.analyze_frames([b""])
        self.assertIn("error", out)
        self.assertNotIn("mood", out)

    def _run_main_with_stub(self, result):
        """打桩 capture_and_analyze，避免测试真的去开摄像头。"""
        import io
        import json
        import sys
        buf = io.StringIO()
        old = sys.stdout
        self.mod.capture_and_analyze = lambda *a, **k: dict(result)
        sys.stdout = buf
        try:
            rc = self.mod.main()
        finally:
            sys.stdout = old
        return rc, buf.getvalue()

    def test_main_emits_single_line_json_on_error(self):
        # 无法打开摄像头 / 缺依赖时应输出 {"ok": false, ...}，供 web_server 判定
        rc, out = self._run_main_with_stub({"error": "无法打开摄像头（设备被占用或不存在）"})
        self.assertEqual(rc, 1)
        self.assertNotIn("\n", out, "stdout 必须是单行 JSON，不能混入日志")
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload.get("error"))

    def test_main_emits_single_line_json_on_success(self):
        rc, out = self._run_main_with_stub({"mood": "开心", "confidence": 0.5,
                                            "detail": "嘴角上扬", "features": {},
                                            "frames": 3, "backend": "vision"})
        self.assertEqual(rc, 0)
        self.assertNotIn("\n", out, "stdout 必须是单行 JSON，不能混入日志")
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["face"]["backend"], "vision")


class VarListAccessTest(unittest.TestCase):
    """_points 必须按 pointCount 索引访问，不能直接迭代 varlist。"""

    def test_points_uses_index_access(self):
        src = VISION_PATH.read_text(encoding="utf-8")
        start = src.index("def _points(")
        end = src.index("def _regions(")
        body = src[start:end]
        self.assertIn("val[i]", body,
                      "normalizedPoints 是 objc.varlist，必须下标取值")
        self.assertIn("pointCount", body, "应按 pointCount 决定取点数量")
        self.assertNotIn("for p in val", body,
                         "varlist 无 __iter__，直接迭代会 SIGBUS")

    def test_points_drops_none_and_empty(self):
        mod = _load_module()
        self.assertEqual(mod._points(None), [])


class FeatureExtractTest(unittest.TestCase):
    """六个特征的口径与量纲必须与 face_mood 一致（复用同一套阈值）。"""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def _regions(self):
        # 归一化坐标、y 向下；脸高归一化为 1，方便手算期望值
        return {
            "faceContour": [(0.0, 0.0), (0.5, 0.0), (1.0, 0.0),
                            (1.0, 1.0), (0.5, 1.0), (0.0, 1.0)],
            "outerLips": [(0.4, 0.5), (0.6, 0.5)],
            "innerLips": [(0.4, 0.55), (0.6, 0.55), (0.6, 0.60), (0.4, 0.60)],
            "leftEye": [(0.2, 0.40), (0.3, 0.40), (0.3, 0.42), (0.2, 0.42)],
            "rightEye": [(0.7, 0.40), (0.8, 0.40), (0.8, 0.44), (0.7, 0.44)],
            "leftEyebrow": [(0.10, 0.36), (0.40, 0.35)],
            "rightEyebrow": [(0.60, 0.36), (0.90, 0.37)],
        }

    def test_feature_keys_match_face_mood(self):
        feats = self.mod.extract_features(self._regions())
        self.assertEqual(tuple(sorted(feats)), tuple(sorted(FEATURE_KEYS)))

    def test_feature_values(self):
        f = self.mod.extract_features(self._regions())
        # smile = (唇心 - 嘴角均值) / 脸高 = (0.575 - 0.5) / 1 = 0.075 > 0 表示嘴角上扬
        self.assertAlmostEqual(f["smile"], 0.075, places=6)
        self.assertAlmostEqual(f["mouth_open"], 0.05, places=6)   # 内唇竖直跨度
        self.assertAlmostEqual(f["brow_eye"], 0.035, places=6)    # (0.04 + 0.03) / 2
        self.assertAlmostEqual(f["brow_gap"],
                               ((0.4 - 0.6) ** 2 + (0.35 - 0.36) ** 2) ** 0.5,
                               places=6)
        self.assertAlmostEqual(f["sad_brow"], -0.01, places=6)    # 眉头 - 眉尾
        self.assertAlmostEqual(f["eye_open"], 0.03, places=6)     # (0.02 + 0.04) / 2

    def test_empty_regions_are_tolerated(self):
        f = self.mod.extract_features({})
        self.assertEqual(set(f), set(FEATURE_KEYS))
        self.assertEqual(f["mouth_open"], 0.0)
        self.assertEqual(f["brow_gap"], 1.0)

    def test_mood_mapping_reuses_face_mood_thresholds(self):
        # 复用同一份 features_to_mood，保证两条后端口径一致
        f = self.mod.extract_features(self._regions())
        mood, conf, detail = self.mod.features_to_mood(f)
        self.assertIn(mood, self.mod.MOODS)
        self.assertGreater(conf, 0.0)
        self.assertTrue(detail)


class SubprocessIsolationTest(unittest.TestCase):
    """web_server 必须把面部识别放进子进程，避免 native abort 带崩 HTTP 服务。"""

    @classmethod
    def setUpClass(cls):
        cls.src = WEB_SERVER_PATH.read_text(encoding="utf-8")
        cls.vsrc = VISION_PATH.read_text(encoding="utf-8")

    def test_web_server_prefers_vision_backend(self):
        self.assertIn("import vision_face_mood", self.src)
        self.assertIn("_FACE_TIMEOUT", self.src)

    def test_face_capture_goes_through_worker(self):
        self.assertIn("_run_face_worker", self.src)
        self.assertIn("subprocess.run", self.src)
        self.assertIn('"--json"', self.src)

    def test_no_in_process_capture_call(self):
        self.assertNotIn("face_mood.capture_and_analyze()", self.src,
                         "不得在 web_server 进程内直接调用 capture_and_analyze")

    def test_face_mood_cli_supports_json(self):
        fsrc = FACE_MOOD_PATH.read_text(encoding="utf-8")
        self.assertIn("--json", fsrc)
        self.assertIn("_cli_main", fsrc)

    def test_worker_handles_timeout_and_signal_death(self):
        for kw in ("TimeoutExpired", "returncode"):
            self.assertIn(kw, self.src)




class CameraRobustnessTest(unittest.TestCase):
    """「摄像头无法打开」的定位与重试。"""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()
        cls.ws = WEB_SERVER_PATH.read_text(encoding="utf-8")
        cls.mood_html = (PROJECT_ROOT / "mood_web.html").read_text(encoding="utf-8")
        cls.face_html = (PROJECT_ROOT / "face_mood_web.html").read_text(encoding="utf-8")

    def test_avf_state_has_three_keys(self):
        state = self.mod._avf_state()
        self.assertEqual(set(state), {"present", "device", "busy_by_other"})
        for v in state.values():
            self.assertTrue(v is None or isinstance(v, (bool, str)), v)

    def test_hint_when_busy_by_other_app(self):
        hint = self.mod.camera_hint({"present": True, "device": "MacBook 相机",
                                      "busy_by_other": True})
        self.assertIn("占用", hint)
        self.assertIn("Zoom", hint)

    def test_hint_when_device_missing(self):
        hint = self.mod.camera_hint({"present": False, "device": None,
                                     "busy_by_other": None})
        self.assertIn("未检测到摄像头", hint)

    def test_hint_when_present_but_cannot_open(self):
        hint = self.mod.camera_hint({"present": True, "device": "MacBook 相机",
                                      "busy_by_other": False})
        self.assertIn("隐私与安全性", hint)

    def test_read_frames_retries_first_frames(self):
        """首帧常未就绪：前两次 read 失败不应直接判定「采集不到画面」。"""
        calls = {"n": 0}

        class FakeCap:
            def read(self):
                calls["n"] += 1
                if calls["n"] <= 2:
                    return False, None
                return True, object()

        class FakeCv2:
            @staticmethod
            def imencode(_ext, _frame):
                return True, bytearray(b"jpeg-bytes")

        frames = self.mod._read_frames(FakeCap(), 1, 0.0, cv2mod=FakeCv2)
        self.assertEqual(len(frames), 1)
        self.assertEqual(calls["n"], 3)

    def test_read_frames_empty_when_all_reads_fail(self):
        class DeadCap:
            def read(self):
                return False, None

        class FakeCv2:
            @staticmethod
            def imencode(_ext, _frame):
                return True, bytearray(b"x")

        self.assertEqual(self.mod._read_frames(DeadCap(), 2, 0.0, cv2mod=FakeCv2), [])

    def test_capture_retries_open_when_busy(self):
        """被占用时多等几轮，避免一句「无法打开摄像头」把用户挡死。"""
        opens = {"n": 0}

        class FakeCap:
            def isOpened(self):
                opens["n"] += 1
                return opens["n"] >= 3

            def read(self):
                return True, object()

            def release(self):
                pass

        mod = self.mod
        state = {"present": True, "device": "MacBook 相机", "busy_by_other": True}
        seen = {}

        def fake_open(cam_index, tries=None):
            seen["tries"] = tries
            return FakeCap(), True

        real = (mod._avf_state, mod._open_camera, mod._read_frames,
                mod.analyze_frames)
        mod._avf_state = lambda: state
        mod._open_camera = fake_open
        mod._read_frames = lambda cap, n, iv, cv2mod=None: [b"jpg"]
        mod.analyze_frames = lambda frames: {
            "mood": "开心", "confidence": 0.5, "detail": "嘴角上扬",
            "frames": len(frames), "backend": "vision"}
        try:
            out = mod.capture_and_analyze(num_frames=1)
        finally:
            (mod._avf_state, mod._open_camera, mod._read_frames,
             mod.analyze_frames) = real
        self.assertIn("mood", out)
        # 被占用时必须要求打开重试，而不是一次失败就放弃
        self.assertEqual(seen["tries"], mod.CAMERA_OPEN_TRIES)

    def test_capture_error_message_is_actionable(self):
        mod = self.mod
        state = {"present": True, "device": "MacBook 相机", "busy_by_other": True}
        real = (mod._avf_state, mod._open_camera)
        mod._avf_state = lambda: state
        mod._open_camera = lambda cam_index, tries=None: (None, False)
        try:
            out = mod.capture_and_analyze(num_frames=1)
        finally:
            mod._avf_state, mod._open_camera = real
        self.assertIn("error", out)
        self.assertIn("占用", out["error"])

    def test_main_supports_camera_probe(self):
        import io as _io
        import sys as _sys
        buf = _io.StringIO()
        old_out, old_argv = _sys.stdout, _sys.argv
        real_probe = self.mod.camera_probe
        self.mod.camera_probe = lambda cam_index=0: {
            "present": True, "device": "MacBook 相机", "busy_by_other": False,
            "can_open": True, "can_read": True, "ok": True}
        _sys.stdout = buf
        _sys.argv = ["vision_face_mood.py", "--camera-probe"]
        try:
            rc = self.mod.main()
        finally:
            _sys.stdout, _sys.argv = old_out, old_argv
            self.mod.camera_probe = real_probe
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["camera"]["can_read"])

    def test_main_camera_probe_failure_exit_code(self):
        import io as _io
        import sys as _sys
        buf = _io.StringIO()
        old_out, old_argv = _sys.stdout, _sys.argv
        real_probe = self.mod.camera_probe
        self.mod.camera_probe = lambda cam_index=0: {
            "present": True, "device": None, "busy_by_other": True,
            "can_open": False, "can_read": False, "ok": False}
        _sys.stdout = buf
        _sys.argv = ["vision_face_mood.py", "--camera-probe"]
        try:
            rc = self.mod.main()
        finally:
            _sys.stdout, _sys.argv = old_out, old_argv
            self.mod.camera_probe = real_probe
        self.assertEqual(rc, 1)
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["ok"])

    def test_web_server_exposes_camera_probe_route(self):
        self.assertIn('/api/face/camera', self.ws)
        self.assertIn('_handle_face_camera', self.ws)
        self.assertIn('--camera-probe', self.ws)

    def test_web_server_capture_does_not_require_face_mood(self):
        """Vision 可用时不应再要求 face_mood（mediapipe）导入成功。"""
        self.assertIn('if face_mood is None and vision_face_mood is None:', self.ws)
        self.assertNotIn('"face_mood 模块不可用"', self.ws)

    def test_mood_web_has_camera_self_check(self):
        self.assertIn('id="camBtn"', self.mood_html)
        self.assertIn('/api/face/camera', self.mood_html)
        self.assertIn('摄像头不可用', self.mood_html)

    def test_face_mood_web_maps_gum_errors(self):
        for name in ("NotAllowedError", "NotReadableError", "NotFoundError",
                     "OverconstrainedError", "AbortError"):
            self.assertIn(name, self.face_html)
        self.assertIn('function cameraErrorHint(e)', self.face_html)
        self.assertIn('setStatus("摄像头开启失败：" + cameraErrorHint(e)', self.face_html)
        # 旧的笼统提示已移除
        self.assertNotIn('（需在 https 或 localhost 下授权', self.face_html)


if __name__ == "__main__":
    unittest.main()
