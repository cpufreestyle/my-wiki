"""wiki_clip.py — 网页剪藏模块（复刻 Notion Web Clipper）。

把任意网页的正文抽取为 Markdown 笔记，存到 inbox/clips/ 目录：
仅依赖标准库（html.parser 做正文抽取，urllib 做抓取），
抓取失败时向上抛 RuntimeError，由 CLI 转成友好错误码。

主要 API：
    fetch_url(url, timeout)            -> html 文本
    extract_main_text(html)            -> dict(title, blocks, excerpt)
    clip_url(url, root, title=None)    -> Path（落盘的笔记）

CLI（经 wiki_tool.py 转发）：
    clip <url> [--title T] [--root DIR]

依赖：仅标准库。
"""

import os
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

BT = chr(96)          # 反引号：统一 chr 构造，源码内不出现字面反引号
FENCE = BT * 3        # Markdown 代码围栏

# 噪音标签：进入这些标签后内容整体丢弃
_SKIP_TAGS = {
    "script", "style", "nav", "footer", "aside", "header", "form",
    "iframe", "svg", "noscript", "template", "button", "select",
    "option", "canvas", "video", "audio", "input",
}
# 块级标签：作为切分块的依据
_BLOCK_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote",
    "pre", "figcaption",
}
_USER_AGENT = "MyWikiClip/1.0 (+personal knowledge wiki)"


class _Extractor(HTMLParser):
    """从 HTML 中抽取标题与正文块的解析器。

    规则：跳过 _SKIP_TAGS 内的全部内容；块级标签各自成块；
    title 取 <title>，og/twitter title 与 meta description 作兜底。
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.og_title = ""
        self.description = ""
        self.blocks = []
        self._in_title = False
        self._skip_depth = 0
        self._cur_tag = None
        self._buf = []

    # ------------------------------------------------------------ 内部

    def _flush(self):
        """把当前缓冲拼装成块。注意先存 tag 再清状态。"""
        tag = self._cur_tag
        text = "".join(self._buf).strip()
        self._buf = []
        self._cur_tag = None
        if text:
            self.blocks.append((tag or "p", text))

    def _meta(self, attrs):
        """读取 og:title / twitter:title / description（不覆盖已有值）。"""
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        content = attrs.get("content") or ""
        if not content:
            return
        if key in ("og:title", "twitter:title") and not self.og_title:
            self.og_title = content
        elif key == "description" and not self.description:
            self.description = content

    # ------------------------------------------------------------ 回调

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = True
            return
        if tag == "meta":
            self._meta(dict(attrs))
            return
        if tag == "br":
            self._buf.append("\n")
            return
        if tag in _BLOCK_TAGS:
            self._flush()
            self._cur_tag = tag

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = False
            return
        if tag in _BLOCK_TAGS and self._cur_tag == tag:
            self._flush()

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
            return
        self._buf.append(data)

    def close(self):
        super().close()
        self._flush()


def extract_main_text(html_text):
    """抽取网页正文，返回 dict(title, blocks, excerpt)。

    title 依次取 <title> -> og:title -> 首个 h1；
    excerpt 依次取 meta description -> 首个较长段落 -> 首块截断。
    blocks 为 [(tag, text)]，保留标题层级供 Markdown 重建。
    """
    parser = _Extractor()
    try:
        parser.feed(html_text)
        parser.close()
    except Exception:
        pass
    title = (parser.title or "").strip() or (parser.og_title or "").strip()
    if not title:
        for tag, text in parser.blocks:
            if tag == "h1":
                title = text
                break
    excerpt = (parser.description or "").strip()
    if not excerpt:
        for tag, text in parser.blocks:
            if tag == "p" and len(text) >= 8:
                excerpt = text[:200]
                break
    if not excerpt and parser.blocks:
        excerpt = parser.blocks[0][1][:200]
    return {"title": title, "blocks": parser.blocks, "excerpt": excerpt}


def fetch_url(url, timeout=15):
    """抓取网页并解码为文本，失败抛 RuntimeError。"""
    import urllib.request
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
    except Exception as exc:
        raise RuntimeError("抓取失败: %s (%s)" % (url, exc))
    try:
        return raw.decode(charset, "replace")
    except LookupError:
        return raw.decode("utf-8", "replace")


# ------------------------------------------------------------ 落盘

def _slugify(text):
    """标题转 URL 友好 slug（保留中英文与数字）。"""
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.lower()).strip("-")
    return s[:60] or "clip"


def _yaml_quote(value):
    """YAML 标量加引号（含特殊字符时）。"""
    v = str(value)
    if any(c in v for c in (":", " ", "#", '"', "'", "\n")):
        return '"%s"' % v.replace('"', "'")
    return v


def clip_url(url, root, title=None):
    """抓取 url 并写为 inbox/clips/YYYY-MM-DD-slug.md，返回路径。"""
    html_text = fetch_url(url)
    data = extract_main_text(html_text)
    final_title = (title or data["title"] or url).strip()
    day = date.today().isoformat()
    out_dir = Path(root) / "inbox" / "clips"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ("%s-%s.md" % (day, _slugify(final_title)))

    lines = [
        "---",
        "title: %s" % _yaml_quote(final_title),
        "source: %s" % _yaml_quote(url),
        "clipped: %s" % day,
        "---",
        "",
        "# %s" % final_title,
        "",
    ]
    if data["excerpt"]:
        lines.append("> %s" % data["excerpt"])
        lines.append("")
    for tag, text in data["blocks"]:
        if tag == "h1":
            continue
        if tag in ("h2", "h3", "h4", "h5", "h6"):
            lines.append("")
            lines.append("%s %s" % ("#" * int(tag[1]), text))
        elif tag == "li":
            lines.append("- %s" % text)
        elif tag == "blockquote":
            lines.append("> %s" % text)
        elif tag == "pre":
            lines.append("")
            lines.append(FENCE)
            lines.append(text)
            lines.append(FENCE)
        elif tag == "figcaption":
            lines.append("*%s*" % text)
        else:
            lines.append(text)
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


# ------------------------------------------------------------ CLI

def _default_root():
    """推断知识库根目录：MYWIKI_ROOT > wiki_paths.WIKI_DIR > 本文件所在目录。"""
    env = os.environ.get("MYWIKI_ROOT")
    if env:
        return Path(env).expanduser()
    try:
        import wiki_paths
        return Path(wiki_paths.WIKI_DIR)
    except Exception:
        return Path(__file__).resolve().parent


def main(argv):
    """CLI 入口：clip <url> [--title T] [--root DIR]。"""
    import argparse
    parser = argparse.ArgumentParser(
        prog="wiki_tool clip", description="剪藏网页为 Markdown 笔记")
    parser.add_argument("url", help="要剪藏的网页地址")
    parser.add_argument("--title", default=None, help="自定义标题")
    parser.add_argument("--root", default=None, help="知识库根目录")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser() if args.root else _default_root()
    try:
        path = clip_url(args.url, root, title=args.title)
    except RuntimeError as exc:
        print("[ERROR] %s" % exc)
        return 2
    print("[OK] 已剪藏 -> %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
