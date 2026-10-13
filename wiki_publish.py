"""wiki_publish.py — 静态站点发布模块（复刻 Obsidian Publish）。

把 wiki 里的 Markdown 笔记渲染成可直接双击打开的静态站点：
搜索索引用 script 标签注入而非 fetch，保证 file:// 协议下可用；
双链解析、反向链接、标签页、站内搜索一应俱全。

主要 API：
    parse_frontmatter(text)        -> (meta, body)
    render_markdown(md, resolver)  -> html 片段
    collect_notes(root, sources)   -> list[dict]
    build_site(root, out_dir)      -> 统计 dict
    main(argv)                     -> int（CLI 入口）

CLI（经 wiki_tool.py 转发）：
    publish [--out DIR] [--clean] [--source a,b] [--name X]

依赖：仅标准库。
"""

import html
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

BT = chr(96)          # 反引号：统一 chr 构造，源码内不出现字面反引号
FENCE = BT * 3        # Markdown 代码围栏
DEFAULT_SOURCES = ("brain", "daily")
PROTECTED_DIRS = ("brain", "daily", "wiki")


# ------------------------------------------------------------ frontmatter

def _unquote(value):
    """去掉字符串首尾成对的引号。"""
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def parse_frontmatter(text):
    """解析 YAML frontmatter 子集，返回 (meta, body)。

    支持 key: value 与缩进列表两种形态，不引入 pyyaml 依赖。
    没有 frontmatter 时返回 ({}, 原文)。
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end = idx
            break
    if end is None:
        return {}, text
    meta = {}
    key = None
    for raw in lines[1:end]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and key is not None:
            if not isinstance(meta.get(key), list):
                meta[key] = []
            meta[key].append(_unquote(stripped[2:]))
            continue
        if ":" in stripped:
            k, _, v = stripped.partition(":")
            key = k.strip()
            v = v.strip()
            meta[key] = _unquote(v) if v else []
    return meta, "\n".join(lines[end + 1:])


# ------------------------------------------------------------ 行内渲染

# URL 允许一层平衡括号（如 javascript:alert(1)），否则行内链接会在第一个
# 右括号处截断，把残缺 URL 当链接、剩余的 ")" 漏成正文。
_URL_IN_PARENS = r'[^()\s]*(?:\([^()\s]*\)[^()\s]*)*'
_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\((' + _URL_IN_PARENS + r')(?:\s+"([^"]*)")?\)')
_LINK_RE = re.compile(r'\[([^\]]+)\]\((' + _URL_IN_PARENS + r')(?:\s+"([^"]*)")?\)')
_WIKILINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')
_BOLD_RE = re.compile(r'\*\*([^*]+)\*\*')
_ITALIC_RE = re.compile(r'(?<!\*)\*([^*\n]+)\*(?!\*)')
_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
_LIST_RE = re.compile(r'^(\s*)([-*+]|\d+[.)])\s+(.*)$')
_TASK_RE = re.compile(r'^\[([ xX])\]\s+(.*)$')
_BAD_SCHEMES = ("javascript:", "data:", "vbscript:", "file:")


def _safe_url(url):
    """拦截危险协议，返回安全 href。"""
    u = (url or "").strip()
    low = u.lower()
    for scheme in _BAD_SCHEMES:
        if low.startswith(scheme):
            return "#"
    return u


def _extract_code_spans(text):
    """抽出行内代码段，返回 (占位化文本, [code html])。"""
    parts = []
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == BT:
            j = text.find(BT, i + 1)
            if j > i:
                out.append("\x00%d\x00" % len(parts))
                parts.append("<code>" + html.escape(text[i + 1:j]) + "</code>")
                i = j + 1
                continue
        out.append(ch)
        i += 1
    return "".join(out), parts


def render_inline(text, link_resolver=None):
    """行内渲染：先代码占位、整体转义，再还原各类行内标记。

    顺序：图片 -> 双链 -> 链接 -> 粗体 -> 斜体，最后还原代码段。
    """
    text, codes = _extract_code_spans(text)
    out = html.escape(text)

    def _img(m):
        alt = html.escape(m.group(1))
        src = _safe_url(m.group(2))
        title = m.group(3)
        attr = ' title="%s"' % html.escape(title) if title else ""
        return '<img src="%s" alt="%s"%s loading="lazy">' % (src, alt, attr)

    def _wiki(m):
        target = m.group(1).strip()
        label = (m.group(2) or target).strip()
        href = link_resolver(target) if link_resolver else None
        if href:
            return '<a class="wikilink" href="%s">%s</a>' % (href, html.escape(label))
        return '<span class="wikilink-broken" title="未找到笔记">%s</span>' % html.escape(label)

    def _link(m):
        label = html.escape(m.group(1))
        url = m.group(2)
        low = url.lower()
        if "://" not in url and link_resolver:
            for ext in (".md", ".markdown"):
                if low.endswith(ext):
                    href = link_resolver(url)
                    if href:
                        return '<a href="%s">%s</a>' % (href, label)
                    url = url[: -len(ext)] + ".html"
                    break
        return '<a href="%s">%s</a>' % (_safe_url(url), label)

    out = _IMAGE_RE.sub(_img, out)
    out = _WIKILINK_RE.sub(_wiki, out)
    out = _LINK_RE.sub(_link, out)
    out = _BOLD_RE.sub(lambda m: "<strong>" + m.group(1) + "</strong>", out)
    out = _ITALIC_RE.sub(lambda m: "<em>" + m.group(1) + "</em>", out)
    for idx, code in enumerate(codes):
        out = out.replace("\x00%d\x00" % idx, code)
    return out


# ------------------------------------------------------------ 块级渲染

def _slug(text):
    """生成标题锚点 id（保留中文）。"""
    s = re.sub(r'[^\w\u4e00-\u9fff\- ]', '', text.lower())
    s = re.sub(r'\s+', '-', s.strip())
    return s or 'section'


def _starts_block(s):
    """判断一行是否开启新的块级结构。"""
    s = s.strip()
    if not s:
        return True
    if s.startswith(FENCE):
        return True
    if _HEADING_RE.match(s):
        return True
    if s.startswith('>'):
        return True
    if s in ('---', '***', '___'):
        return True
    if _LIST_RE.match(s):
        return True
    return False


def _split_row(line):
    """拆分表格行。"""
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    return [c.strip() for c in s.split('|')]


def _is_table_sep(line):
    """判断是否是表格分隔行（如 |---|---:|）。"""
    cells = _split_row(line)
    if not cells:
        return False
    for cell in cells:
        if not re.match(r'^:?-+:?$', cell.strip()):
            return False
    return True


def _align_style(aligns, idx):
    """表格对齐样式。"""
    if idx < len(aligns) and aligns[idx]:
        return ' style="text-align:%s"' % aligns[idx]
    return ''


def _render_table(lines, i, link_resolver):
    """渲染表格，返回 (html, next_i)。"""
    header = _split_row(lines[i])
    aligns = []
    for cell in _split_row(lines[i + 1]):
        c = cell.strip()
        left = c.startswith(':')
        right = c.endswith(':')
        aligns.append('center' if left and right else ('right' if right else ''))
    i += 2
    rows = []
    n = len(lines)
    while i < n and lines[i].strip() and '|' in lines[i]:
        rows.append(_split_row(lines[i]))
        i += 1
    parts = ['<table>', '<thead><tr>']
    for idx, cell in enumerate(header):
        parts.append('<th%s>%s</th>' % (_align_style(aligns, idx),
                                        render_inline(cell, link_resolver)))
    parts.append('</tr></thead><tbody>')
    for row in rows:
        parts.append('<tr>')
        for idx, cell in enumerate(row):
            parts.append('<td%s>%s</td>' % (_align_style(aligns, idx),
                                            render_inline(cell, link_resolver)))
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return ''.join(parts), i


def _render_item_body(node, link_resolver):
    """渲染列表项内容（含任务列表复选框）。"""
    text = node['text']
    if node['task'] is not None:
        checked = ' checked' if node['task'].lower() == 'x' else ''
        return '<input type="checkbox"%s disabled> %s' % (
            checked, render_inline(text, link_resolver))
    return render_inline(text, link_resolver)


def _render_list(lines, i, link_resolver):
    """渲染列表块（支持嵌套与任务列表），返回 (html, next_i)。"""
    first = _LIST_RE.match(lines[i])
    base_indent = len(first.group(1))
    bullet = first.group(2) in ('-', '*', '+')
    items = []
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j < n:
                m = _LIST_RE.match(lines[j])
                if m and len(m.group(1)) >= base_indent and (
                        len(m.group(1)) > base_indent
                        or (m.group(2) in ('-', '*', '+')) == bullet):
                    i = j
                    continue
            break
        m = _LIST_RE.match(line)
        if m:
            indent = len(m.group(1))
            if indent < base_indent:
                break
            if indent == base_indent and (m.group(2) in ('-', '*', '+')) != bullet:
                break
            text = m.group(3)
            task = None
            tm = _TASK_RE.match(text)
            if tm:
                task = tm.group(1)
                text = tm.group(2)
            items.append((indent, m.group(2), text, task))
            i += 1
            continue
        if items and (line.startswith(' ') or line.startswith('\t')):
            indent, marker, text, task = items[-1]
            items[-1] = (indent, marker, (text + ' ' + line.strip()).strip(), task)
            i += 1
            continue
        break
    root = []
    stack = []
    for indent, marker, text, task in items:
        node = {'marker': marker, 'text': text, 'task': task, 'children': []}
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            stack[-1][1]['children'].append(node)
        else:
            root.append(node)
        stack.append((indent, node))

    def render_nodes(nodes):
        if not nodes:
            return ''
        ordered = nodes[0]['marker'] not in ('-', '*', '+')
        tag = 'ol' if ordered else 'ul'
        parts = ['<%s>' % tag]
        for node in nodes:
            parts.append('<li>%s' % _render_item_body(node, link_resolver))
            if node['children']:
                parts.append(render_nodes(node['children']))
            parts.append('</li>')
        parts.append('</%s>' % tag)
        return ''.join(parts)

    return render_nodes(root), i


def render_markdown(md, link_resolver=None):
    """渲染 Markdown 子集为 HTML 片段。

    支持：ATX 标题、段落、粗/斜体、行内代码、链接/图片、双链、
    有序/无序列表（可嵌套）、任务列表、引用、分隔线、代码围栏、
    管道表格。链接目标经 _safe_url 过滤，双链经 link_resolver 解析。
    """
    lines = md.splitlines()
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith(FENCE):
            lang = stripped[3:].strip()
            code = []
            i += 1
            while i < n and not lines[i].strip().startswith(FENCE):
                code.append(lines[i])
                i += 1
            i += 1
            cls = ' class="language-%s"' % html.escape(lang) if lang else ''
            out.append('<pre><code%s>%s</code></pre>' % (cls, html.escape('\n'.join(code))))
            continue
        if stripped in ('---', '***', '___'):
            out.append('<hr>')
            i += 1
            continue
        m = _HEADING_RE.match(stripped)
        if m:
            level = len(m.group(1))
            content = render_inline(m.group(2).strip(), link_resolver)
            out.append('<h%d id="%s">%s</h%d>' % (level, _slug(m.group(2)), content, level))
            i += 1
            continue
        if stripped.startswith('>'):
            quote = []
            while i < n and lines[i].strip().startswith('>'):
                quote.append(lines[i].strip().lstrip('>').strip())
                i += 1
            out.append('<blockquote>%s</blockquote>'
                       % render_markdown('\n'.join(quote), link_resolver))
            continue
        if '|' in line and i + 1 < n and _is_table_sep(lines[i + 1]):
            table, i = _render_table(lines, i, link_resolver)
            out.append(table)
            continue
        if _LIST_RE.match(line):
            block, i = _render_list(lines, i, link_resolver)
            out.append(block)
            continue
        para = [stripped]
        i += 1
        while i < n:
            nxt = lines[i]
            s = nxt.strip()
            if not s or _starts_block(s):
                break
            if '|' in s and i + 1 < n and _is_table_sep(lines[i + 1]):
                break
            para.append(s)
            i += 1
        out.append('<p>%s</p>' % render_inline(' '.join(para), link_resolver))
    return '\n'.join(out)


# ------------------------------------------------------------ 笔记收集

_SCAN_EXTS = (".md", ".markdown")
_SKIP_DIRS = {
    ".git", ".obsidian", ".codebuddy", ".qoder", "node_modules",
    ".venv", "__pycache__", ".trash", "dist-publish", "vendor",
    "inbox", "backups",
}


def iter_notes(root, sources=DEFAULT_SOURCES):
    """遍历 root 下各来源目录的笔记，yield (Path, 相对路径字符串)。"""
    base = Path(root)
    for src in sources:
        top = base / src
        if not top.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
            for name in sorted(filenames):
                if name.lower().endswith(_SCAN_EXTS):
                    path = Path(dirpath) / name
                    yield path, path.relative_to(base).as_posix()


def _fmt_date(mtime):
    """mtime -> YYYY-MM-DD（本地时区），异常返回空串。"""
    try:
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return ""


def _excerpt(body, limit=120):
    """提取摘要：首个非空、非标题、非列表/引用/表格的段落。"""
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "-", "*", "+", ">", "|", "---")):
            continue
        if len(s) < 4:
            continue
        return s[:limit]
    return ""


def _plain_text(body, limit=4000):
    """去掉 Markdown 标记压平为纯文本，供搜索索引使用。"""
    text = re.sub("[*_#>|~\x60]", " ", body)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:limit]


def collect_notes(root, sources=DEFAULT_SOURCES):
    """收集所有笔记为 list[dict]，按 rel 排序。

    每条含 rel / title / tags / body / excerpt / words / mtime。
    tags 兼容 frontmatter 的 str 与 list 两种形态；
    title 依次取 frontmatter title -> 首个一级标题 -> 文件名。
    """
    notes = []
    for path, rel in iter_notes(root, sources):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        meta, body = parse_frontmatter(text)
        tags = meta.get("tags")
        if isinstance(tags, str):
            # frontmatter 行内列表写法 tags: [a, b]：先剥方括号再切分，
            # 否则标签名会带上 "[a" / "b]" 这样的残壳
            inner = tags.strip()
            if inner.startswith("[") and inner.endswith("]"):
                inner = inner[1:-1]
            tags = [t.strip() for t in inner.split(",") if t.strip()]
        elif isinstance(tags, list):
            tags = [str(t).strip() for t in tags if str(t).strip()]
        else:
            tags = []
        title = str(meta.get("title") or "").strip()
        if not title:
            m = re.search(r"^#\s+(.+)$", body, re.M)
            if m:
                title = m.group(1).strip()
        if not title:
            title = path.stem
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        notes.append({
            "rel": rel,
            "title": title,
            "tags": tags,
            "body": body,
            "excerpt": _excerpt(body),
            "words": len(_plain_text(body)),
            "mtime": mtime,
        })
    notes.sort(key=lambda n: n["rel"])
    return notes


# ------------------------------------------------------------ 链接解析

def _html_name(rel):
    """笔记相对路径 -> 站点内 html 文件名（保留来源目录前缀）。"""
    lower = rel.lower()
    for ext in _SCAN_EXTS:
        if lower.endswith(ext):
            return rel[: -len(ext)] + ".html"
    return rel + ".html"


def _rel_href(page_rel, target_rel):
    """计算 page_rel 页面指向 target_rel 的相对 href。

    target_rel 传 "." 表示站点根目录，返回值带尾斜杠。
    """
    base = os.path.dirname(page_rel) or os.curdir
    if target_rel == os.curdir:
        href = os.path.relpath(os.curdir, base)
        return href + "/" if href != os.curdir else "./"
    return Path(os.path.relpath(target_rel, base)).as_posix()


def _build_resolver(notes):
    """构造双链解析器：resolve(target) -> 目标页 html 名或 None。

    匹配顺序：完整相对路径（去后缀）-> 词干 -> basename 兜底。
    """
    by_rel = {}
    by_stem = {}
    for note in notes:
        rel = note["rel"]
        no_ext = _html_name(rel)[:-5]
        by_rel[no_ext] = note
        by_rel[rel] = note
        stem = Path(rel).stem
        prev = by_stem.get(stem)
        if prev is None or len(rel) < len(prev["rel"]):
            by_stem[stem] = note

    def resolve(target):
        if not target:
            return None
        t = target.strip().replace("\\", "/")
        while t.startswith("./"):
            t = t[2:]
        t = t.lstrip("/")
        if t.lower().endswith(".md"):
            t = t[:-3]
        for table in (by_rel, by_stem):
            note = table.get(t)
            if note is not None:
                return _html_name(note["rel"])
        note = by_stem.get(Path(t).stem)
        if note is not None:
            return _html_name(note["rel"])
        return None

    return resolve


def _outlink_targets(body):
    """提取正文出链目标（双链 + .md 链接），去重保序。"""
    targets = []
    seen = set()

    def add(t):
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            targets.append(t)

    for m in _WIKILINK_RE.finditer(body):
        add(m.group(1))
    for m in _LINK_RE.finditer(body):
        url = m.group(2)
        low = url.lower()
        if low.endswith((".md", ".markdown")) and "://" not in url:
            add(url)
    return targets


def _guard_out_dir(out_dir, root):
    """校验输出目录安全性，非法时 raise ValueError。

    拒绝：与 root 相同、是 root 的祖先、落在 brain/daily/wiki 内。
    """
    out = Path(out_dir).expanduser().resolve()
    base = Path(root).expanduser().resolve()
    if out == base:
        raise ValueError("输出目录不能是知识库根目录本身：%s" % out)
    if out in base.parents:
        raise ValueError("输出目录不能是知识库的上级目录：%s" % out)
    for name in PROTECTED_DIRS:
        prot = (base / name).resolve()
        if out == prot or prot in out.parents:
            raise ValueError("输出目录不能落在 %s/ 内：%s" % (name, out))
    return out


# ------------------------------------------------------------ 站点构建

def build_site(root, out_dir=None, clean=False, sources=DEFAULT_SOURCES,
               site_name="MyWiki"):
    """把知识库渲染为静态站点，返回统计 dict。

    流程：收集笔记 -> 校验输出目录 ->（可选）清空 -> 逐篇渲染页面 ->
    全量互算反向链接 -> 生成首页 / 标签页 / 搜索索引与静态资源。
    """
    root = Path(root).expanduser().resolve()
    if out_dir is None:
        out_dir = root / "dist-publish"
    out_dir = _guard_out_dir(out_dir, root)
    notes = collect_notes(root, sources)
    if clean and out_dir.is_dir():
        shutil.rmtree(out_dir)
    notes_dir = out_dir / "notes"
    assets_dir = out_dir / "assets"
    notes_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    resolve = _build_resolver(notes)

    # 反向链接：全量互算，排除自链
    backlinks = {}
    for note in notes:
        src_html = _html_name(note["rel"])
        for target in _outlink_targets(note["body"]):
            dest = resolve(target)
            if dest is None or dest == src_html:
                continue
            backlinks.setdefault(dest, []).append(note)

    # 标签索引
    tag_index = {}
    for note in notes:
        for tag in note["tags"]:
            tag_index.setdefault(tag, []).append(note)

    # 搜索索引（script 注入，file:// 下无需 fetch）
    search_entries = [{
        "title": n["title"],
        "url": "notes/" + _html_name(n["rel"]),
        "tags": n["tags"],
        "excerpt": n["excerpt"],
        "text": _plain_text(n["body"]),
    } for n in notes]

    # 笔记页
    for note in notes:
        page_rel = "notes/" + _html_name(note["rel"])

        def resolver(target, _page=page_rel):
            dest = resolve(target)
            return _rel_href(_page, dest) if dest else None

        date_str = _fmt_date(note["mtime"])
        meta_bits = [b for b in (date_str, "%d 字" % note["words"]) if b]
        parts = ['<article class="note">',
                 '<p class="meta">%s</p>' % " · ".join(meta_bits),
                 "<h1>%s</h1>" % html.escape(note["title"])]
        if note["tags"]:
            tag_href = _rel_href(page_rel, "tags.html")
            chips = "".join('<a class="chip" href="%s">%s</a>' % (
                tag_href, html.escape(t)) for t in note["tags"])
            parts.append('<p class="tags">%s</p>' % chips)
        parts.append(render_markdown(note["body"], resolver))
        srcs = backlinks.get(_html_name(note["rel"]), [])
        if srcs:
            items = "".join('<li><a href="%s">%s</a></li>' % (
                _rel_href(page_rel, "notes/" + _html_name(s["rel"])),
                html.escape(s["title"])) for s in srcs)
            parts.append('<section class="backlinks"><h2>反向链接</h2>'
                         "<ul>%s</ul></section>" % items)
        parts.append("</article>")
        target = notes_dir / _html_name(note["rel"])
        target.parent.mkdir(parents=True, exist_ok=True)
        _write(target, _render_page(page_rel, note["title"], site_name,
                                    "".join(parts), len(notes)))

    # 首页：按 mtime 倒序卡片列表
    ordered = sorted(notes, key=lambda n: n["mtime"], reverse=True)
    cards = []
    for note in ordered:
        page_rel = "notes/" + _html_name(note["rel"])
        date_str = _fmt_date(note["mtime"]) or note["rel"]
        cards.append(
            '<a class="card" href="%s"><h2>%s</h2><p>%s</p>'
            '<p class="meta">%s</p></a>' % (
                _rel_href("index.html", page_rel),
                html.escape(note["title"]),
                html.escape(note["excerpt"]) or "（暂无摘要）",
                html.escape(date_str)))
    index_content = (
        '<h1 class="site-title">%s</h1>'
        '<p class="site-sub">共 %d 篇笔记 · %d 个标签</p>'
        '<div class="note-list">%s</div>' % (
            html.escape(site_name), len(notes), len(tag_index),
            "".join(cards)))
    _write(out_dir / "index.html", _render_page(
        "index.html", site_name, site_name, index_content, len(notes)))

    # 标签页
    groups = []
    for tag in sorted(tag_index):
        items = "".join('<li><a href="%s">%s</a></li>' % (
            _rel_href("tags.html", "notes/" + _html_name(n["rel"])),
            html.escape(n["title"])) for n in tag_index[tag])
        groups.append('<div class="tag-group"><h2>%s</h2><ul>%s</ul></div>'
                      % (html.escape(tag), items))
    tags_content = ('<h1>标签</h1><p class="meta">共 %d 个标签</p>%s'
                    % (len(tag_index), "".join(groups)))
    _write(out_dir / "tags.html", _render_page(
        "tags.html", "标签 · " + site_name, site_name, tags_content,
        len(notes)))

    # 静态资源
    _write(assets_dir / "style.css", STYLE_CSS)
    _write(assets_dir / "search.js", SEARCH_JS)
    _write(assets_dir / "search-data.js",
           "window.SEARCH_INDEX = "
           + json.dumps(search_entries, ensure_ascii=False) + ";\n")

    return {
        "notes": len(notes),
        "pages": len(notes) + 2,
        "tags": len(tag_index),
        "backlinks": sum(len(v) for v in backlinks.values()),
        "out_dir": str(out_dir),
    }


# ------------------------------------------------------------ 页面模板

_PAGE_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="__CSS__">
</head>
<body>
<header class="site-header">
  <a class="brand" href="__HOME__">__SITE__</a>
  <nav class="nav">
    <a href="__HOME__">首页</a>
    <a href="__TAGS__">标签</a>
  </nav>
  <div class="search-box">
    <input id="q" type="search" placeholder="搜索笔记..." autocomplete="off">
    <div id="results" class="results" hidden></div>
  </div>
</header>
<main class="container">
__CONTENT__
</main>
<footer class="site-footer">由 MyWiki publish 生成 · 共 __COUNT__ 篇</footer>
<script>window.__SITE_PREFIX="__PREFIX__";</script>
<script src="__SEARCHJS__"></script>
</body>
</html>
"""


def _fill(tmpl, mapping):
    """逐项替换模板占位符（key 自动转为 __KEY__ 形态）。"""
    out = tmpl
    for key, value in mapping.items():
        out = out.replace("__%s__" % key.upper(), value)
    return out


def _render_page(page_rel, title, site_name, content, count):
    """渲染完整 HTML 页面，返回文本。"""
    prefix = _rel_href(page_rel, ".")
    if prefix == "./":
        prefix = ""
    else:
        prefix = prefix.rstrip("/") + "/"
    return _fill(_PAGE_TMPL, {
        "title": html.escape(title),
        "site": html.escape(site_name),
        "css": prefix + "assets/style.css",
        "home": prefix + "index.html",
        "tags": prefix + "tags.html",
        "searchjs": prefix + "assets/search.js",
        "prefix": prefix,
        "content": content,
        "count": str(count),
    })


def _write(path, text):
    """写 UTF-8 文本文件，自动创建父目录。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ------------------------------------------------------------ 静态资源

STYLE_CSS = """:root {
  --bg: #f6f6f4;
  --surface: #ffffff;
  --text: #1f2328;
  --muted: #6b7280;
  --accent: #7c5cbf;
  --border: #e5e3dd;
  --shadow: 0 1px 3px rgba(0, 0, 0, .06), 0 8px 24px rgba(0, 0, 0, .06);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #17181c;
    --surface: #1f2126;
    --text: #e8e6e1;
    --muted: #9aa0a8;
    --accent: #a78bfa;
    --border: #2e3138;
    --shadow: 0 1px 3px rgba(0, 0, 0, .4), 0 8px 24px rgba(0, 0, 0, .3);
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 16px/1.75 -apple-system, BlinkMacSystemFont, "SF Pro Text",
    "PingFang SC", "Helvetica Neue", "Segoe UI", sans-serif;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.site-header {
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: center; gap: 20px;
  padding: 12px 24px;
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--border);
}
.brand { font-weight: 700; font-size: 18px; color: var(--text); }
.nav { display: flex; gap: 16px; }
.nav a { color: var(--muted); font-size: 14px; }
.nav a:hover { color: var(--text); text-decoration: none; }
.search-box { margin-left: auto; position: relative; }
#q {
  width: 220px; padding: 7px 12px;
  border: 1px solid var(--border); border-radius: 8px;
  background: var(--bg); color: var(--text); font-size: 14px;
  outline: none;
}
#q:focus { border-color: var(--accent); }
.results {
  position: absolute; top: calc(100% + 6px); right: 0;
  width: 360px; max-height: 60vh; overflow: auto;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; box-shadow: var(--shadow);
  display: flex; flex-direction: column; padding: 6px;
}
.results .hit {
  display: block; padding: 10px 12px; border-radius: 8px;
  color: var(--text);
}
.results .hit:hover { background: var(--bg); text-decoration: none; }
.results .hit strong { display: block; font-size: 15px; }
.results .hit span {
  display: block; color: var(--muted); font-size: 13px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.results .search-empty { margin: 0; padding: 12px; color: var(--muted); }
.container { max-width: 760px; margin: 0 auto; padding: 32px 24px 64px; }
.site-title { font-size: 32px; margin: 8px 0 4px; }
.site-sub { color: var(--muted); margin: 0 0 28px; }
.note-list { display: grid; gap: 14px; }
.card {
  display: block; padding: 18px 20px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; color: var(--text);
  transition: transform .15s ease, box-shadow .15s ease;
}
.card:hover {
  transform: translateY(-2px); box-shadow: var(--shadow);
  text-decoration: none;
}
.card h2 { margin: 0 0 6px; font-size: 18px; }
.card p { margin: 0; color: var(--muted); font-size: 14px; }
.card .meta { margin-top: 8px; font-size: 12px; opacity: .8; }
.note h1 { font-size: 30px; line-height: 1.3; margin: 4px 0 12px; }
.note h2 { font-size: 22px; margin: 28px 0 10px; }
.note h3 { font-size: 18px; margin: 22px 0 8px; }
.meta { color: var(--muted); font-size: 13px; }
.tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 16px; }
.chip {
  padding: 2px 10px; font-size: 12px; border-radius: 999px;
  background: var(--bg); border: 1px solid var(--border); color: var(--muted);
}
.note pre {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px; overflow: auto;
}
.note code {
  background: var(--bg); border-radius: 4px;
  padding: 1px 5px; font-size: .9em;
}
.note pre code { background: none; padding: 0; }
.note blockquote {
  margin: 14px 0; padding: 4px 16px;
  border-left: 3px solid var(--accent); color: var(--muted);
}
.note table { border-collapse: collapse; width: 100%; margin: 16px 0; }
.note th, .note td {
  border: 1px solid var(--border); padding: 8px 12px; font-size: 14px;
}
.note img { max-width: 100%; border-radius: 10px; }
.wikilink-broken { color: var(--muted); text-decoration: line-through; }
.backlinks {
  margin-top: 40px; padding-top: 16px;
  border-top: 1px solid var(--border);
}
.backlinks h2 { font-size: 16px; }
.backlinks ul { margin: 0; padding-left: 20px; }
.tag-group { margin-bottom: 24px; }
.tag-group h2 { font-size: 18px; }
.tag-group ul { margin: 0; padding-left: 20px; }
.site-footer {
  border-top: 1px solid var(--border);
  padding: 20px 24px; text-align: center;
  color: var(--muted); font-size: 12px;
}
@media (max-width: 640px) {
  .site-header { flex-wrap: wrap; gap: 10px; padding: 10px 16px; }
  #q { width: 100%; }
  .search-box { margin-left: 0; width: 100%; }
  .results { width: 100%; }
  .container { padding: 20px 16px 48px; }
}
"""


SEARCH_JS = """(function () {
  var index = window.SEARCH_INDEX || [];
  var prefix = window.__SITE_PREFIX || "";
  var input = document.getElementById("q");
  var box = document.getElementById("results");
  if (!input || !box) { return; }
  var timer = null;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;",
              '"': "&quot;", "'": "&#39;"}[c];
    });
  }

  function search(query) {
    var words = query.toLowerCase().split(/\\s+/).filter(Boolean);
    if (!words.length) { box.hidden = true; box.innerHTML = ""; return; }
    var hits = [];
    for (var i = 0; i < index.length && hits.length < 20; i++) {
      var e = index[i];
      var hay = (e.title + " " + (e.tags || []).join(" ")
                 + " " + (e.text || "")).toLowerCase();
      var ok = true;
      for (var j = 0; j < words.length; j++) {
        if (hay.indexOf(words[j]) < 0) { ok = false; break; }
      }
      if (ok) { hits.push(e); }
    }
    if (!hits.length) {
      box.innerHTML = '<p class="search-empty">没有找到相关笔记</p>';
    } else {
      var out = "";
      for (var k = 0; k < hits.length; k++) {
        var h = hits[k];
        out += '<a class="hit" href="' + prefix + h.url + '">'
               + '<strong>' + esc(h.title) + '</strong>'
               + '<span>' + esc(h.excerpt || "") + '</span></a>';
      }
      box.innerHTML = out;
    }
    box.hidden = false;
  }

  input.addEventListener("input", function () {
    if (timer) { clearTimeout(timer); }
    timer = setTimeout(function () { search(input.value.trim()); }, 120);
  });
  input.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") { input.value = ""; box.hidden = true; }
  });
  document.addEventListener("click", function (ev) {
    if (ev.target !== input && !box.contains(ev.target)) {
      box.hidden = true;
    }
  });
})();
"""


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
    """CLI 入口：publish [--root DIR] [--out DIR] [--clean] [--source a,b] [--name X]。"""
    import argparse
    parser = argparse.ArgumentParser(
        prog="wiki_tool publish", description="把 wiki 渲染为静态站点")
    parser.add_argument("--out", default=None,
                        help="输出目录（默认 <root>/dist-publish）")
    parser.add_argument("--root", default=None, help="知识库根目录")
    parser.add_argument("--clean", action="store_true",
                        help="发布前清空输出目录")
    parser.add_argument("--source", default=",".join(DEFAULT_SOURCES),
                        help="扫描的来源目录，逗号分隔")
    parser.add_argument("--name", default="MyWiki", help="站点名称")
    args = parser.parse_args(argv)
    sources = tuple(s.strip() for s in args.source.split(",") if s.strip())
    root = Path(args.root).expanduser() if args.root else _default_root()
    try:
        stats = build_site(root, out_dir=args.out, clean=args.clean,
                           sources=sources, site_name=args.name)
    except ValueError as exc:
        print("[ERROR] %s" % exc)
        return 2
    print("[OK] 已发布 %d 篇笔记 -> %s" % (stats["notes"], stats["out_dir"]))
    print("     页面 %d · 标签 %d · 反向链接 %d"
          % (stats["pages"], stats["tags"], stats["backlinks"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
