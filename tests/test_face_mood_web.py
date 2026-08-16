#!/usr/bin/env python3
"""
tests/test_face_mood_web.py — face_mood_web.html 结构与后端路由一致性单元测试

纯标准库实现（unittest + html.parser + re），无需任何第三方依赖。目标与
test_mood_web.py 一致：守住 JS 引用的元素 id 不存在、关键 DOM / 逻辑缺失、
以及与 web_server.py 后端路由 / 模块注册表脱节的整类 bug。

前端约定（face_mood_web.html）：
  - 摄像头经浏览器 getUserMedia 取流，MediaPipe FaceLandmarker（CDN ESM）本地推理
  - 由 27 维 blendshape 线性权重推断 7 类情绪（平静/开心/悲伤/愤怒/惊讶/恐惧/轻蔑）
  - 结果 POST 到 /api/face_mood，由 web_server.py 落盘到 mood/<date>.json(source="face")
"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent.parent / "face_mood_web.html"
WEB_SERVER_PATH = Path(__file__).resolve().parent.parent / "web_server.py"


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.classes = set()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.tags.append((tag, d))
        if "id" in d and d["id"]:
            self.ids.add(d["id"])
        if "class" in d and d["class"]:
            for c in d["class"].split():
                self.classes.add(c)


def _load():
    text = HTML_PATH.read_text(encoding="utf-8")
    parser = _Collector()
    parser.feed(text)
    # 本页脚本为 <script type="module">，裸 <script> 正则匹配不到，需定向提取
    m = re.search(r'<script type="module">(.*?)</script>', text, re.DOTALL)
    script = m.group(1) if m else ""
    server = WEB_SERVER_PATH.read_text(encoding="utf-8") if WEB_SERVER_PATH.exists() else ""
    return text, parser, script, server


class TestFaceMoodWebStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script, cls.server = _load()

    # ---------- 文件与脚本 ----------
    def test_file_exists(self):
        self.assertTrue(HTML_PATH.exists(), f"缺少文件: {HTML_PATH}")
        self.assertIn("<!DOCTYPE html>", self.text)

    def test_has_module_script(self):
        self.assertTrue(self.script.strip(), "未找到 <script type=\"module\"> 正文")

    # ---------- 关键 DOM 节点 ----------
    def test_required_ids_present(self):
        required = {
            "video", "overlay", "placeholder", "status", "startBtn", "stopBtn",
            "saveBtn", "emoLabel", "emoConf", "bars", "note", "toast",
        }
        missing = sorted(required - self.p.ids)
        self.assertFalse(missing, f"缺少关键元素 id: {missing}")

    def test_getelementbyid_refs_resolve(self):
        refs = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', self.script))
        self.assertTrue(refs, "脚本中未发现任何 getElementById 引用")
        missing = sorted(r for r in refs if r not in self.p.ids)
        self.assertFalse(
            missing,
            f"脚本引用了不存在的元素 id: {missing}\n实际 id: {sorted(self.p.ids)}",
        )

    def test_back_link_present(self):
        self.assertIn('href="index.html"', self.text, "缺少返回首页链接")

    # ---------- 情绪模型一致性 ----------
    def test_emotions_defined(self):
        m = re.search(r'const EMOTIONS = \[(.*?)\];', self.script, re.DOTALL)
        self.assertIsNotNone(m, "脚本应定义 EMOTIONS 数组")
        emotions = re.findall(r'"([^"]+)"', m.group(1))
        self.assertEqual(len(emotions), 7, f"EMOTIONS 应为 7 类，实际 {len(emotions)}: {emotions}")
        for e in ["平静", "开心", "悲伤", "愤怒", "惊讶", "恐惧", "轻蔑"]:
            self.assertIn(e, emotions, f"EMOTIONS 应含 {e}")

    def test_feature_keys_count(self):
        m = re.search(r'const FEATURE_KEYS = \[(.*?)\];', self.script, re.DOTALL)
        self.assertIsNotNone(m, "脚本应定义 FEATURE_KEYS 数组")
        keys = re.findall(r'"([^"]+)"', m.group(1))
        self.assertEqual(len(keys), 27, f"FEATURE_KEYS 应为 27 维，实际 {len(keys)}")

    def test_weights_dimension_consistency(self):
        # 每个情绪的权重向量长度需与 FEATURE_KEYS(27) 一致，且情绪数需与 EMOTIONS(7) 一致
        wm = re.search(r'const WEIGHTS = \{(.*?)\n\s*\};', self.script, re.DOTALL)
        self.assertIsNotNone(wm, "脚本应定义 WEIGHTS 字典")
        block = wm.group(1)
        arrays = re.findall(r'\[(.*?)\]', block, re.DOTALL)
        self.assertEqual(len(arrays), 7, f"WEIGHTS 应有 7 个向量，实际 {len(arrays)}")
        for i, arr in enumerate(arrays):
            nums = re.findall(r'-?\d+\.?\d*', arr)
            self.assertEqual(
                len(nums), 27,
                f"WEIGHTS 第 {i} 个向量应为 27 维，实际 {len(nums)}",
            )

    def test_classify_function_defined(self):
        self.assertIn("function classify", self.script, "脚本应定义 classify")
        self.assertIn("softmax", self.script, "classify 应使用 softmax 归一化")
        self.assertIn("function extractFeatures", self.script, "脚本应定义 extractFeatures")
        self.assertIn("function topFeatures", self.script, "脚本应定义 topFeatures")

    # ---------- MediaPipe 接入与摄像头约束 ----------
    def test_mediapipe_import(self):
        self.assertIn("@mediapipe/tasks-vision", self.script, "应引入 @mediapipe/tasks-vision")
        self.assertIn("FaceLandmarker", self.script, "应引用 FaceLandmarker")
        self.assertIn("outputFaceBlendshapes", self.script, "应开启 outputFaceBlendshapes")
        self.assertIn("importmap", self.text, "应通过 importmap 解析 ESM 依赖")

    def test_localhost_camera_note(self):
        # 摄像头仅在 https / localhost 下可用，错误提示应覆盖该约束
        self.assertIn("localhost", self.script, "摄像头失败提示应说明 localhost/https 限制")

    # ---------- 保存接口与后端路由契约 ----------
    def test_save_posts_to_face_mood(self):
        self.assertIn('fetch("/api/face_mood"', self.script,
                      "保存逻辑应 POST 到 /api/face_mood")
        self.assertIn("method: \"POST\"", self.script, "fetch 应使用 POST 方法")

    def test_api_route_present(self):
        self.assertTrue(self.server, "未找到 web_server.py")
        self.assertIn('"/api/face_mood"', self.server,
                      "web_server.py 应注册 /api/face_mood 路由")
        self.assertIn("_handle_face_mood", self.server,
                      "web_server.py 应定义 _handle_face_mood 处理器")

    def test_handler_validates_emotion(self):
        # 后端缺 emotion 字段应 400 拒绝，避免写入脏数据
        fn = re.search(r'def _handle_face_mood\(self\):.*?def log_message',
                       self.server, re.DOTALL)
        self.assertIsNotNone(fn, "未能定位 _handle_face_mood 实现")
        body = fn.group(0)
        self.assertIn('if not data.get("emotion")', body,
                      "_handle_face_mood 应校验 emotion 字段")
        self.assertIn('"source": "face"', body,
                      "落盘记录应标记 source='face'")

    def test_module_registry_has_face_mood(self):
        self.assertIn('"face_mood"', self.server, "模块注册表应含 face_mood")
        self.assertIn('"face_mood_web.html"', self.server,
                      "模块注册表应指向 face_mood_web.html")

    # ---------- 主题与可访问性 ----------
    def test_dark_mode_support(self):
        self.assertIn('[data-theme="dark"]', self.text, "缺少深色模式样式")
        self.assertIn("data-theme", self.script, "脚本缺少 data-theme 切换逻辑")

    def test_toast_role_status(self):
        toast = next((d for t, d in self.p.tags if d.get("id") == "toast"), None)
        self.assertIsNotNone(toast, "缺少 toast 元素")


if __name__ == "__main__":
    unittest.main(verbosity=2)
