#!/usr/bin/env python3
"""
tests/test_mood_web.py — mood_web.html 结构 / 选择器一致性单元测试

纯标准库实现（unittest + html.parser + re），无需任何第三方依赖。核心目标：
守住 JS 里引用了不存在的元素 id / class 导致 querySelector 返回 null 的整类 bug，
同时校验关键交互元素、心情分析逻辑可达、深色模式与可访问性属性。
"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent.parent / "mood_web.html"
VOICE_JS_PATH = Path(__file__).resolve().parent.parent / "voice-controller.js"


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
    m = re.search(r"<script>(.*?)</script>", text, re.DOTALL)
    script = m.group(1) if m else ""
    voice_js = VOICE_JS_PATH.read_text(encoding="utf-8") if VOICE_JS_PATH.exists() else ""
    return text, parser, script, voice_js


class TestMoodWebStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script, cls.voice_js = _load()

    def test_file_exists(self):
        self.assertTrue(HTML_PATH.exists(), f"缺少文件: {HTML_PATH}")
        self.assertIn("<!DOCTYPE html>", self.text)

    def test_has_script_block(self):
        self.assertTrue(self.script.strip(), "未找到 <script> 正文")

    def test_id_selectors_resolve(self):
        refs = set(re.findall(r"""['"]#([A-Za-z][\w-]*)['"]""", self.script))
        self.assertTrue(refs, "脚本中未发现任何 #id 选择器")
        missing = sorted(r for r in refs if r not in self.p.ids)
        self.assertFalse(
            missing,
            f"脚本引用了不存在的元素 id: {missing}\n实际 id: {sorted(self.p.ids)}",
        )

    def test_class_selectors_resolve(self):
        refs = set(re.findall(r"""querySelector(?:All)?\(['"]\.([A-Za-z][\w-]*)""", self.script))
        missing = sorted(r for r in refs if r not in self.p.classes)
        self.assertFalse(missing, f"脚本引用了不存在的 class: {missing}")

    def test_required_ids_present(self):
        required = {
            "themeToggle", "toast", "moodInput", "voiceBtn", "voiceStatus",
            "autosave", "moodGrid", "analyzeBtn", "moodResult", "history", "status",
        }
        missing = sorted(required - self.p.ids)
        self.assertFalse(missing, f"缺少关键元素 id: {missing}")

    def test_mood_logic_defined(self):
        self.assertIn("function analyze_mood", self.script, "脚本应定义 analyze_mood")
        self.assertIn("MOOD_KEYWORDS", self.script, "脚本应定义 MOOD_KEYWORDS")
        # 5 种心情：开心/平静/低落/兴奋/焦虑
        for m in ["开心", "平静", "低落", "兴奋", "焦虑"]:
            self.assertIn(m, self.script, f"MOOD_KEYWORDS 应含 {m}")

    def test_accessibility_attributes(self):
        toggle = next((d for t, d in self.p.tags if d.get("id") == "themeToggle"), None)
        self.assertIsNotNone(toggle)
        self.assertIn("aria-label", toggle, "themeToggle 缺少 aria-label")
        toast = next((d for t, d in self.p.tags if d.get("id") == "toast"), None)
        self.assertIsNotNone(toast)
        self.assertEqual(toast.get("role"), "status", "toast 缺少 role=status")

    def test_dark_mode_support(self):
        self.assertIn('[data-theme="dark"]', self.text, "缺少深色模式样式")
        self.assertIn("assets/web/theme.js", self.text,
                      "缺少共享主题脚本 theme.js（data-theme 切换逻辑所在）")

    def test_global_error_filter_present(self):
        self.assertIn('"Script error."', self.script,
                      "缺少屏蔽跨域 Script error 的全局错误过滤器")

    def test_voice_graceful_degradation(self):
        # 不支持语音时给出友好提示而非直接报错
        # 该提示逻辑现已抽到共享模块 voice-controller.js
        combined = self.script + "\n" + self.voice_js
        self.assertIn("不支持语音识别", combined,
                      "应处理浏览器不支持语音识别的情况（内联脚本或 voice-controller.js）")
        # 内联脚本应通过 VoiceController 接入共享模块
        self.assertIn("new VoiceController(", self.script, "应实例化共享语音控制器")



    def test_card_height_control_present(self):
        # 卡片高度调节：滑块面板 + 控件 + 卡片 min-height 绑定变量
        self.assertIn("height-panel", self.p.classes, "缺少 .height-panel 卡片高度面板")
        for i in ["cardHeight", "cardHeightVal"]:
            self.assertIn(i, self.p.ids, f"缺少卡片高度控件 id: {i}")
        self.assertIn("var(--card-h)", self.text, "卡片 min-height 应绑定 --card-h 变量")
        self.assertIn('LS_CARD_H = "mywiki-card-h"', self.script,
                      "应定义卡片高度 localStorage key(mywiki-card-h)")
        self.assertIn("localStorage.setItem(LS_CARD_H", self.script,
                      "卡片高度应持久化到 localStorage")


class TestFaceRecognitionPopup(unittest.TestCase):
    """面部识别必须有明显弹窗反馈。

    曾经的形态是：点「📷 面部」→ 只在底部状态行写一行字，用户看不到任何
    弹出，反馈「点面部 无法跳出」。这里守住进度弹窗 / 结果弹窗 / 失败弹窗
    三条路径都存在且可关闭。"""

    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script, cls.voice_js = _load()

    def test_modal_element_present(self):
        mask = next((d for t, d in self.p.tags if d.get("id") == "faceModal"), None)
        self.assertIsNotNone(mask, "缺少面部识别弹窗遮罩 #faceModal")
        self.assertIn("hidden", mask, "#faceModal 初始应为 hidden")
        # dialog 语义放在卡片上，并用 aria-labelledby 指向标题
        dialog = next((d for t, d in self.p.tags if d.get("role") == "dialog"), None)
        self.assertIsNotNone(dialog, "弹窗卡片缺少 role=dialog")
        self.assertEqual(dialog.get("aria-modal"), "true")
        self.assertEqual(dialog.get("aria-labelledby"), "faceModalTitle")

    def test_modal_ids_exist(self):
        for mid in ("faceEmoji", "faceModalTitle", "faceProg", "faceResult",
                    "faceMood", "faceDetail", "faceMeta", "faceProgTime",
                    "faceSaveBtn", "faceCloseBtn"):
            self.assertIn(mid, self.p.ids, f"缺少弹窗元素 #{mid}")

    def test_modal_css_present(self):
        self.assertIn(".modal-mask", self.text, "缺少弹窗遮罩样式")
        self.assertIn(".modal-mask[hidden]", self.text,
                      "hidden 状态必须能真正隐藏（否则弹窗关不掉）")
        self.assertIn(".spinner", self.text, "缺少进度指示器样式")
        self.assertIn("z-index", self.text, "弹窗应浮在页面之上")

    def test_modal_functions_defined(self):
        for fn in ("showFaceProgress", "showFaceResult", "showFaceError",
                   "closeFaceModal", "openFaceModal"):
            self.assertIn("function " + fn, self.script,
                          f"缺少弹窗控制函数 {fn}()")

    def test_click_handler_shows_popup(self):
        for call in ("showFaceProgress();", "showFaceResult(f);",
                     "showFaceError(why);",
                     'showFaceError("面部服务无响应'):
            self.assertIn(call, self.script,
                          f"点击「📷 面部」后未调用 {call}")

    def test_modal_closable(self):
        self.assertIn('$("#faceCloseBtn").addEventListener("click", closeFaceModal)',
                      self.script, "关闭按钮未绑定")
        self.assertIn('"Escape"', self.script, "应支持 Esc 关闭弹窗")
        self.assertIn("e.target === faceModal", self.script,
                      "应支持点遮罩关闭弹窗")

    def test_result_can_be_saved(self):
        self.assertIn('$("#faceSaveBtn").addEventListener', self.script,
                      "保存按钮未绑定")
        idx = self.script.index('$("#faceSaveBtn").addEventListener')
        self.assertIn("analyzeMoodUi(null, f)", self.script[idx:idx + 300],
                      "保存后应把面部结果交给心情分析")

    def test_progress_shows_elapsed_time(self):
        self.assertIn("faceProgTime", self.script)
        self.assertIn("toFixed(1)", self.script,
                      "进度应显示已等待秒数，避免用户以为卡死")


if __name__ == "__main__":
    unittest.main()

