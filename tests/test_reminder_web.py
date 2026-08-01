#!/usr/bin/env python3
"""
tests/test_reminder_web.py — reminder_web.html 结构 / 选择器一致性单元测试

纯标准库实现（unittest + html.parser + re），无需任何第三方依赖。核心目标：
守住 JS 里引用了不存在的元素 id / class 导致 querySelector 返回 null 的整类 bug，
同时校验关键交互元素、语音输入接入、深色模式与可访问性属性。
"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent.parent / "reminder_web.html"
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
    # 取最后一个 <script> 块（内联逻辑），共享模块由外部文件引入
    blocks = re.findall(r"<script>(.*?)</script>", text, re.DOTALL)
    script = blocks[-1] if blocks else ""
    voice_js = VOICE_JS_PATH.read_text(encoding="utf-8") if VOICE_JS_PATH.exists() else ""
    return text, parser, script, voice_js


class TestReminderWebStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, cls.p, cls.script, cls.voice_js = _load()

    def test_file_exists(self):
        self.assertTrue(HTML_PATH.exists(), f"缺少文件: {HTML_PATH}")
        self.assertIn("<!DOCTYPE html>", self.text)

    def test_has_script_block(self):
        self.assertTrue(self.script.strip(), "未找到内联 <script> 正文")

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
            "themeToggle", "toast", "status", "customBtn", "viewBtn",
            "contentModal", "customModal", "reminderText", "reminderVoiceBtn",
            "reminderVoiceStatus", "customText", "customVoiceBtn", "customVoiceStatus",
            "saveContentBtn", "saveCustomBtn",
        }
        missing = sorted(required - self.p.ids)
        self.assertFalse(missing, f"缺少关键元素 id: {missing}")

    def test_both_voice_buttons_present(self):
        # 两个模态各一个语音按钮
        for btn in ("reminderVoiceBtn", "customVoiceBtn"):
            self.assertIn(btn, self.p.ids, f"缺少语音按钮 id: {btn}")
        # 两个对应的状态行
        for st in ("reminderVoiceStatus", "customVoiceStatus"):
            self.assertIn(st, self.p.ids, f"缺少语音状态行 id: {st}")

    def test_voice_input_row_structure(self):
        # 语音按钮与输入框应同处 .input-row 中，且使用 .voice-btn / .voice-status 样式
        for cls in ("input-row", "voice-btn", "voice-status"):
            self.assertIn(cls, self.p.classes, f"缺少语音相关样式 class: {cls}")

    def test_accessibility_attributes(self):
        toggle = next((d for t, d in self.p.tags if d.get("id") == "themeToggle"), None)
        self.assertIsNotNone(toggle)
        self.assertIn("aria-label", toggle, "themeToggle 缺少 aria-label")
        toast = next((d for t, d in self.p.tags if d.get("id") == "toast"), None)
        self.assertIsNotNone(toast)
        self.assertEqual(toast.get("role"), "status", "toast 缺少 role=status")
        for modal in ("contentModal", "customModal"):
            m = next((d for t, d in self.p.tags if d.get("id") == modal), None)
            self.assertIsNotNone(m, f"缺少模态 {modal}")
            self.assertEqual(m.get("role"), "dialog", f"{modal} 缺少 role=dialog")
            self.assertEqual(m.get("aria-modal"), "true", f"{modal} 缺少 aria-modal=true")

    def test_dark_mode_support(self):
        self.assertIn('[data-theme="dark"]', self.text, "缺少深色模式样式")
        self.assertIn("data-theme", self.script, "脚本缺少 data-theme 切换逻辑")

    def test_global_error_filter_present(self):
        self.assertIn('"Script error."', self.script,
                      "缺少屏蔽跨域 Script error 的全局错误过滤器")

    def test_voice_shared_module_wired(self):
        # 引入共享语音模块
        self.assertIn('src="voice-controller.js"', self.text,
                      "应引入共享语音模块 voice-controller.js")
        # 内联脚本应接入共享模块并实例化两个控制器
        self.assertIn("new VoiceController(", self.script, "应实例化共享语音控制器")
        self.assertIn("reminderVoiceBtn", self.script, "应为 reminderVoiceBtn 实例化 VoiceController")
        self.assertIn("customVoiceBtn", self.script, "应为 customVoiceBtn 实例化 VoiceController")

    def test_voice_graceful_degradation(self):
        # 不支持语音时给出友好提示而非直接报错（逻辑在共享模块中）
        combined = self.script + "\n" + self.voice_js
        self.assertIn("不支持语音识别", combined,
                      "应处理浏览器不支持语音识别的情况（voice-controller.js）")
        # 提醒是单行输入：结果应以空格拼接而非换行
        self.assertIn("+ \" \" +", self.script,
                      "提醒语音结果应以空格拼接（单行输入框）")



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

if __name__ == "__main__":
    unittest.main(verbosity=2)
