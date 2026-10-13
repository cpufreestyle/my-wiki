#!/usr/bin/env python3
"""tests/_html_probe.py — 网页结构测试共享 helper

daily / mood / rag / graph / face_mood / reminder / index 七个页面测试原本各自
复制了一份 _Collector + _load()（约 110 行逐字重复），差异只有四点：

  * script 提取方式：第一个裸 <script>、最后一个裸 <script>，还是
    <script type="module">（face_mood_web.html 的脚本是 module，裸正则匹配不到）；
  * 是否附带 voice-controller.js 内容（mood / rag / reminder）；
  * 是否附带 web_server.py 内容（face_mood）；
  * _Collector 是否记录 <a href>（index，其余页面用不到但无害）。

统一由本文件提供，调用方用关键字参数表达差异；返回元组按
(text, parser, script[, voice_js][, server_src]) 顺序追加，与各测试
setUpClass 的解包一一对应。新增页面测试请直接 import 本模块，不要再复制。
"""
import re
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _Collector(HTMLParser):
    """收集 HTML 的 id / class / 标签序列，以及全部 <a href>。"""

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.classes = set()
        self.tags = []
        self.href = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.tags.append((tag, d))
        if "id" in d and d["id"]:
            self.ids.add(d["id"])
        if "class" in d and d["class"]:
            for c in d["class"].split():
                self.classes.add(c)
        if tag == "a" and d.get("href"):
            self.href.append(d["href"])


def _load(path, *, voice=False, server=False, module_script=False, last=False):
    """解析页面文件，返回 (text, parser, script[, voice_js][, server_src])。

    voice=True        追加 voice-controller.js 内容（不存在时为 ""）；
    server=True       追加 web_server.py 内容（不存在时为 ""）；
    module_script=True 提取 <script type="module"> 块；
    last=True         取最后一个裸 <script> 块，否则取第一个。
    """
    text = Path(path).read_text(encoding="utf-8")
    parser = _Collector()
    parser.feed(text)
    if module_script:
        m = re.search(r'<script type="module">(.*?)</script>', text, re.DOTALL)
        script = m.group(1) if m else ""
    elif last:
        blocks = re.findall(r"<script>(.*?)</script>", text, re.DOTALL)
        script = blocks[-1] if blocks else ""
    else:
        m = re.search(r"<script>(.*?)</script>", text, re.DOTALL)
        script = m.group(1) if m else ""
    out = [text, parser, script]
    if voice:
        p = PROJECT_ROOT / "voice-controller.js"
        out.append(p.read_text(encoding="utf-8") if p.exists() else "")
    if server:
        p = PROJECT_ROOT / "web_server.py"
        out.append(p.read_text(encoding="utf-8") if p.exists() else "")
    return tuple(out)
