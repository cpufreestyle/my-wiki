#!/usr/bin/env python3
"""
tests/test_face_mood_web.py — face_mood_web.html 结构与后端路由一致性单元测试

纯标准库实现（unittest + html.parser + re），无需任何第三方依赖。目标与
test_mood_web.py 一致：守住 JS 引用的元素 id 不存在、关键 DOM / 逻辑缺失、
以及与 web_server.py 后端路由 / 模块注册表脱节的整类 bug。

前端约定（face_mood_web.html）：
  - 摄像头经浏览器 getUserMedia 取流，MediaPipe FaceLandmarker（本地 vendor ESM）本地推理
  - 由 27 维 blendshape 线性权重推断 7 类情绪（平静/开心/悲伤/愤怒/惊讶/恐惧/轻蔑）
  - 结果 POST 到 /api/face_mood，由 web_server.py 落盘到 mood/<date>.json(source="face")

资源本地化约定（vendor/mediapipe/）：
  - MediaPipe 的 JS/WASM 与 face_landmarker.task 一律从同源路径加载，
    不依赖公网 CDN，避免用户网络/VPN 环境下 CDN 慢或不可达，
    页面长期停在「正在加载 MediaPipe 模型…」。
"""
import os
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent.parent / "face_mood_web.html"
WEB_SERVER_PATH = Path(__file__).resolve().parent.parent / "web_server.py"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 页面不得再出现的外网 CDN 域名（含常见的 MediaPipe 模型托管域名）
FORBIDDEN_CDN_HOSTS = (
    "cdn.jsdelivr.net",
    "unpkg.com",
    "storage.googleapis.com",
    "cdn.skypack.dev",
)


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
        self.assertIn("assets/web/theme.js", self.text,
                      "缺少共享主题脚本 theme.js（data-theme 切换逻辑所在）")

    def test_toast_role_status(self):
        toast = next((d for t, d in self.p.tags if d.get("id") == "toast"), None)
        self.assertIsNotNone(toast, "缺少 toast 元素")




class TestFaceMoodWebLocalAssets(unittest.TestCase):
    """MediaPipe 资源本地化回归（防止 CDN 拉取失败复发）。"""

    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script, cls.server = _load()

    def test_no_external_cdn_reference(self):
        # 页面（含 <script type="module"> 正文）不得再引用任何公网 CDN
        for host in FORBIDDEN_CDN_HOSTS:
            self.assertNotIn(host, self.text,
                             f"face_mood_web.html 仍引用外网 CDN：{host}")
            self.assertNotIn(host, self.script,
                             f"页面脚本仍引用外网 CDN：{host}")

    def test_vendor_paths_are_local(self):
        # ESM 依赖经 importmap 指向本地 vendor 文件
        self.assertIn('"/vendor/mediapipe/vision_bundle.mjs"', self.text,
                      "importmap 应把 @mediapipe/tasks-vision 映射到本地 vision_bundle.mjs")
        # 人像分割脚本同源加载（本地存在时才有效，站内资源无需 crossorigin）
        self.assertIn('src="/vendor/mediapipe/selfie_segmentation.js"', self.text,
                      "selfie_segmentation.js 应同源加载")
        # wasm 文件集与模型文件均指向本地
        self.assertIn('"/vendor/mediapipe/wasm"', self.script,
                      "forVisionTasks 应指向本地 wasm 目录")
        self.assertIn('"/models/face_landmarker.task"', self.script,
                      "modelAssetPath 应指向本地 face_landmarker.task")
        self.assertIn("/vendor/mediapipe/${file}", self.script,
                      "locateFile 应拼装本地 vendor 路径")

    def test_vendor_assets_exist_on_disk(self):
        # 页面引用的每个本地站点路径都必须真实存在，否则运行期 404
        refs = re.findall(r'["\'`]((?:/vendor|/models)/[^"\'`\s)]+)["\'`]',
                          self.text + self.script)
        normalized = set()
        for ref in refs:
            normalized.add(ref.split("${")[0].rstrip("/"))
        missing = []
        for ref in sorted(normalized):
            if not (PROJECT_ROOT / ref.lstrip("/")).exists():
                missing.append(ref)
        self.assertFalse(missing, f"页面引用的本地资源在仓库中不存在: {missing}")
        self.assertTrue(normalized, "未在页面中发现任何 /vendor 或 /models 本地资源引用")

    def test_vendor_wasm_binaries_are_not_empty(self):
        # wasm 二进制必须真实入仓（曾出现 curl 半截文件导致页面卡加载）
        for rel in (
            "vendor/mediapipe/vision_bundle.mjs",
            "vendor/mediapipe/wasm/vision_wasm_internal.js",
            "vendor/mediapipe/wasm/vision_wasm_internal.wasm",
            "vendor/mediapipe/wasm/vision_wasm_nosimd_internal.js",
            "vendor/mediapipe/wasm/vision_wasm_nosimd_internal.wasm",
            "vendor/mediapipe/selfie_segmentation.js",
            "vendor/mediapipe/selfie_segmentation_solution_simd_wasm_bin.js",
            "vendor/mediapipe/selfie_segmentation_solution_simd_wasm_bin.wasm",
            "vendor/mediapipe/selfie_segmentation_solution_wasm_bin.js",
            "vendor/mediapipe/selfie_segmentation_solution_wasm_bin.wasm",
        ):
            path = PROJECT_ROOT / rel
            self.assertTrue(path.is_file(), f"缺少 vendor 文件: {rel}")
            size = path.stat().st_size
            self.assertGreater(size, 1024,
                                f"vendor 文件过小（疑似 404 占位或半截文件）: {rel} ({size}B)")
            if rel.endswith(".wasm"):
                with open(path, "rb") as fh:
                    self.assertEqual(fh.read(4), b"\x00asm",
                                     f"不是合法 wasm 文件: {rel}")

    def test_face_landmarker_model_exists(self):
        model = PROJECT_ROOT / "models/face_landmarker.task"
        self.assertTrue(model.is_file(), "缺少本地模型文件 models/face_landmarker.task")
        self.assertGreater(model.stat().st_size, 1024 * 1024,
                           "face_landmarker.task 体积异常，疑似下载不完整")


class TestFaceMoodWebMirror(unittest.TestCase):
    """方向/镜像开关与画布尺寸时序回归（修复「抠图和人方向反了」）。"""

    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script, cls.server = _load()

    def test_mirror_toggle_present(self):
        self.assertIn("mirrorBtn", self.p.ids, "缺少方向/镜像开关按钮 mirrorBtn")
        self.assertIn("mirrorMode", self.script, "脚本应定义方向开关 mirrorMode")

    def test_no_five_arg_drawimage_video(self):
        # 回归「看不见人脸」：5 参 drawImage(video, dx, dy, dw, dh) 的后 4 个参数是
        # 「源图裁剪矩形」而非目标矩形，dx=w 会把整块画面画到画布外，
        # 真实模式（默认）下什么都不画，只剩背景图。
        draws = self.script.split("drawImage(video")[1:]
        self.assertTrue(draws, "未发现任何 drawImage(video, ...) 调用")
        for seg in draws:
            args = seg.split(";")[0]
            self.assertIn(
                "video.videoWidth", args,
                "drawImage(video, ...) 必须是 9 参形态（含源矩形）: " + repr(args),
            )

    def test_video_draws_go_through_drawvideoframe(self):
        # 统一入口 drawVideoFrame 必须是 9 参形态，且 5 路绘制全部走它
        self.assertIn("function drawVideoFrame(", self.script,
                      "应定义统一的视频帧绘制入口 drawVideoFrame")
        self.assertIn(
            "drawImage(video, 0, 0, video.videoWidth, video.videoHeight,",
            self.script,
            "drawVideoFrame 应使用 9 参 drawImage 形态",
        )
        self.assertGreaterEqual(
            self.script.count("drawVideoFrame("), 6,
            "drawVideoFrame 应被 5 路绘制调用（含定义共 >= 6 处）",
        )
        for ctxname in ("bgSmall1Ctx", "frameCtx", "ctx", "pctx"):
            self.assertIn("drawVideoFrame(%s," % ctxname, self.script,
                          "缺少 drawVideoFrame(%s, ...) 调用" % ctxname)

    def test_mirror_gates_drawvideoframe(self):
        # 方向开关仍需只经由 drawVideoFrame 一处生效
        self.assertIn("const dx = mirrorMode ? w : 0;", self.script,
                      "drawVideoFrame 应由 mirrorMode 决定水平偏移")
        self.assertIn("const dw = mirrorMode ? -w : w;", self.script,
                      "drawVideoFrame 应由 mirrorMode 决定绘制宽度")

    def test_landmark_flip_mirror_gated(self):
        self.assertIn("x: mirrorMode ? 1 - p.x : p.x", self.script,
                      "landmark x 翻转应由 mirrorMode 控制")

    def test_canvas_size_metadata_timing(self):
        # start() 需用事件监听 loadedmetadata 对齐画布尺寸，避免画布停在 300x150
        self.assertIn('video.addEventListener("loadedmetadata"', self.script,
                      "应使用事件监听 loadedmetadata 对齐画布尺寸")
        self.assertIn("{ once: true }", self.script,
                      "loadedmetadata 监听应为一次性事件")


class TestFaceMoodWebMaskFallback(unittest.TestCase):
    """mask 无人兜底回归（修复「人消失 / 只剩背景图」的另一半成因）。"""

    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script, cls.server = _load()

    def test_person_presence_probe_defined(self):
        self.assertIn("function maskHasPerson", self.script,
                      "应定义 mask 人物探针 maskHasPerson")
        self.assertIn("willReadFrequently", self.script,
                      "探针画布应使用 willReadFrequently 读取像素")
        self.assertIn("getImageData", self.script,
                      "探针应读取 alpha 像素判断是否有人")
        self.assertIn("drawImage(bmp, 0, 0, pw, ph)", self.script,
                      "探针应把 mask 降采样到 16x12 再读像素")

    def test_no_person_counter_and_thresholds(self):
        self.assertIn("const NO_PERSON_FRAMES =", self.script,
                      "应定义连续无人帧阈值 NO_PERSON_FRAMES")
        self.assertIn("const NO_PERSON_ALPHA =", self.script,
                      "应定义 alpha 均值阈值 NO_PERSON_ALPHA")
        self.assertIn("let maskNoPerson = 0;", self.script,
                      "应定义连续无人帧计数器 maskNoPerson")

    def test_draw_person_skips_mask_when_no_person(self):
        # 连续无人时不得再按 mask 抠图：destination-in 会擦掉整块画面
        self.assertIn("maskNoPerson >= NO_PERSON_FRAMES", self.script,
                      "drawPerson 应在连续无人时放弃 mask 抠图")

    def test_update_person_presence_called_for_both_paths(self):
        # Vision 与 MediaPipe 两条 mask 来源都要更新人物在/离场状态
        self.assertGreaterEqual(
            self.script.count("updatePersonPresence(maskHasPerson("), 2,
            "Vision 与 MediaPipe 两条路径都应调用 updatePersonPresence",
        )


class TestFaceMoodWebMatteNormalization(unittest.TestCase):
    """matte 通道归一回归（修复「抠图没成功」）。"""

    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script, cls.server = _load()

    def test_build_matte_defined(self):
        # 抠图前必须把引擎返回的 mask 归一小图，否则无法保证
        # destination-in 读到的 alpha 就是人物覆盖率
        self.assertIn("function buildMatte(", self.script,
                      "应定义 buildMatte 把引擎 mask 归一为 alpha=覆盖率")

    def test_matte_channel_detection_defined(self):
        self.assertIn("function matteChannel(", self.script,
                      "应定义 matteChannel 判定覆盖率在哪个通道")

    def test_rgb_matte_is_inverted_into_alpha(self):
        # 覆盖率落在 RGB、alpha 恒 255 的构建：destination-in 读 alpha 会得到
        # 「整幅保留」——画面看着像没抠图；必须反相写进 alpha。
        self.assertIn("const out = maskSmallCtx.createImageData(mw, mh);", self.script,
                      "RGB 型 mask 必须重写为 alpha 通道")
        self.assertIn("const cov = 255 - d[i];", self.script,
                      "RGB 覆盖率需反相为 alpha")
        self.assertIn("maskSmallCtx.putImageData(out, 0, 0);", self.script,
                      "重写后的 matte 必须写回画布")

    def test_draw_person_uses_build_matte(self):
        self.assertIn("buildMatte(mask, mw, mh);", self.script,
                      "drawPerson 必须走 buildMatte 而不是直接 drawImage(mask)")

    def test_empty_matte_never_erases_person(self):
        # 单帧保险：这一帧覆盖率接近 0 就不能抠，否则偶发空 mask 会在
        # 一两帧内把人整块擦掉（用户看到「人突然消失」）。
        self.assertIn("if (lastMatteCoverage < NO_PERSON_ALPHA) {", self.script,
                      "matte 覆盖率接近 0 时应降级为直接显示原帧")
        self.assertIn("let lastMatteCoverage = 0;", self.script,
                      "应记录最近一帧的 matte 覆盖率")

    def test_mask_probe_still_reads_pixels(self):
        self.assertIn("function maskHasPerson", self.script)
        self.assertIn("drawImage(bmp, 0, 0, pw, ph)", self.script)
        self.assertIn("getImageData", self.script)


class TestFaceMoodWebMaskDelivery(unittest.TestCase):
    """Vision mask 送达率回归（修复「抠图没成功」的另一半成因）。"""

    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script, cls.server = _load()

    def test_stale_logic_does_not_discard_everything(self):
        # 旧逻辑：if (seq !== _visionSeq) return null;
        # Vision 往返 ~35ms 与 VISION_POLL_MS(50) 同量级，主线程还要让给
        # detectForVideo，实测同节奏 60 次请求 0 次被采纳 —— lastMask 永远
        # 是 null，drawPerson 只能走兜底画原帧，用户看到「抠图没成功」。
        self.assertNotIn("if (seq !== _visionSeq) return null;", self.script,
                         "不得要求 seq 恰为最新发出的那一个，否则 mask 几乎全被丢弃")

    def test_mask_acceptance_tracks_applied_seq(self):
        self.assertIn("if (seq < _visionApplied) return null;", self.script,
                      "只应作废已被更新结果取代的响应")
        self.assertIn("_visionApplied = seq;", self.script,
                      "采纳后必须推进 _visionApplied")

    def test_mask_backlog_limit_defined(self):
        self.assertIn("const MAX_VISION_LAG =", self.script,
                      "应定义未决请求积压上限 MAX_VISION_LAG")
        self.assertIn("if (_visionSeq - seq > MAX_VISION_LAG) return null;", self.script,
                      "积压过旧的响应应作废")

    def test_single_failure_does_not_disable_vision(self):
        # 一次网络抖动就永久关掉 Vision，之后整条抠图链只剩「不抠」。
        self.assertIn("const VISION_FAIL_LIMIT =", self.script,
                      "应定义连续失败上限 VISION_FAIL_LIMIT")
        self.assertIn('if (++visionFail >= VISION_FAIL_LIMIT) visionMode = "off";', self.script,
                      "只有连续失败达到上限才降级")
        self.assertIn("visionFail = 0;", self.script,
                      "成功一次即清零失败计数")

    def test_person_presence_still_updated_both_paths(self):
        self.assertGreaterEqual(
            self.script.count("updatePersonPresence(maskHasPerson("), 2,
            "Vision 与 MediaPipe 两条路径都应调用 updatePersonPresence",
        )

    def test_matte_canvas_reads_frequently(self):
        # buildMatte 每帧读像素判通道，maskSmallCtx 需标 willReadFrequently
        self.assertIn(
            'maskSmall.getContext("2d", { willReadFrequently: true })',
            self.script,
            "maskSmallCtx 应使用 willReadFrequently 避免每帧 GPU→CPU 回读",
        )


class TestVisionSegmentMatteSize(unittest.TestCase):
    """vision_segment.py 掩码尺寸必须回到帧尺寸（同坐标系）。"""

    def setUp(self):
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        import vision_segment as vs
        self.vs = vs

    def test_matte_to_frame_size_defined(self):
        self.assertTrue(hasattr(self.vs, "matte_to_frame_size"),
                        "应抽出可单测的 matte_to_frame_size")

    def test_matte_is_resampled_to_frame_size(self):
        import io
        from PIL import Image
        # Vision 固定输出 4:3；帧是 16:9 —— 掩码必须回到 16:9
        frame = Image.new("RGB", (320, 180), (32, 64, 96))
        buf = io.BytesIO()
        frame.save(buf, "JPEG")
        mask = Image.new("L", (512, 384), 0)
        out = self.vs.matte_to_frame_size(mask, buf.getvalue())
        self.assertEqual(out.size, (320, 180),
                         "16:9 帧必须把 4:3 掩码重采样回帧尺寸")

    def test_same_size_is_noop(self):
        import io
        from PIL import Image
        frame = Image.new("RGB", (320, 240), (10, 20, 30))
        buf = io.BytesIO()
        frame.save(buf, "JPEG")
        mask = Image.new("L", (320, 240), 128)
        out = self.vs.matte_to_frame_size(mask, buf.getvalue())
        self.assertEqual(out.size, (320, 240))
        self.assertEqual(out.getpixel((0, 0)), 128, "尺寸一致时不得改动像素")

    def test_matte_pixel_semantics_preserved(self):
        import io
        from PIL import Image
        frame = Image.new("RGB", (320, 180), (0, 0, 0))
        buf = io.BytesIO()
        frame.save(buf, "JPEG")
        mask = Image.new("L", (512, 384), 255)   # 全人像
        out = self.vs.matte_to_frame_size(mask, buf.getvalue())
        self.assertGreaterEqual(out.getpixel((160, 90)), 250,
                                "重采样后 255 仍应代表人像")



if __name__ == "__main__":
    unittest.main(verbosity=2)
