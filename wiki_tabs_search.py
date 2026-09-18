#!/usr/bin/env python3
"""wiki_tabs_search.py — 全文搜索标签页（SearchTabMixin）

遍历 vault 内的 Markdown，做关键词匹配并高亮命中片段。
"""
import html
import os

from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QTextBrowser, QVBoxLayout, QWidget

from wiki_paths import WIKI_DIR
from wiki_theme import get_theme_colors
from wiki_i18n import t
from wiki_data import iter_vault_md, read_text_safe


def search_keyword(query, limit=40, per_file=3):
    """在 vault 的 md 内做关键词匹配（大小写不敏感）。

    返回 [{rel, hits:[(lineno, line)], count}]，按命中数降序。
    """
    q = query.lower()
    out = []
    for path in iter_vault_md():
        text = read_text_safe(path)
        if not text:
            continue
        hits = [(i, ln.strip()) for i, ln in enumerate(text.splitlines()) if q in ln.lower()]
        if hits:
            out.append({
                "rel": os.path.relpath(path, WIKI_DIR),
                "hits": hits[:per_file],
                "count": len(hits),
            })
            if len(out) >= limit:
                break
    out.sort(key=lambda x: -x["count"])
    return out


def render_results_html(query, results, colors):
    """把搜索结果渲染为高亮 HTML。"""
    if not results:
        return f"<p style='color:{colors['TEXT2']}'>{html.escape(t('search_no_result'))}</p>"
    q = query.lower()
    parts = [f"<p style='color:{colors['TEXT2']}'>{html.escape(t('search_results', n=len(results)))}</p>"]
    for r in results:
        parts.append(
            f"<p style='margin:12px 0 3px;'><b>{html.escape(r['rel'])}</b> "
            f"<span style='color:{colors['TEXT2']}'>({r['count']})</span></p>"
        )
        for _, line in r["hits"]:
            esc = html.escape(line)
            idx = esc.lower().find(q)
            if idx >= 0:
                esc = esc[:idx] + f"<mark>{esc[idx:idx + len(q)]}</mark>" + esc[idx + len(q):]
            parts.append(f"<div style='color:{colors['TEXT']};font-size:13px;'>· {esc}</div>")
    return "".join(parts)


class SearchTabMixin:
    def _build_search_tab(self):
        T = get_theme_colors()
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self._section_label(layout, t("tab_search"))
        row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("search_ph"))
        self.search_input.returnPressed.connect(self.do_search)
        row.addWidget(self.search_input, stretch=1)
        row.addWidget(self._primary_btn(t("search_btn"), self.do_search))
        layout.addLayout(row)

        self.search_view = QTextBrowser()
        self.search_view.setStyleSheet(
            f"QTextBrowser {{ background-color: {T['SURFACE']}; border: 1px solid {T['BORDER']}; "
            f"border-radius: 10px; padding: 8px; color: {T['TEXT']}; }}"
        )
        layout.addWidget(self.search_view, stretch=1)

        self.nb.addTab(tab, t("tab_search"))

    def do_search(self):
        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText(t("search_need_kw"))
            return
        results = search_keyword(query)
        self.search_view.setHtml(render_results_html(query, results, get_theme_colors()))
        self.status_label.setText(t("search_results", n=len(results)))
