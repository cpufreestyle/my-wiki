#!/usr/bin/env python3
"""wiki_tabs_tags.py — 标签浏览标签页（TagsTabMixin）

统计 vault 内 frontmatter 的标签，展示标签云；点击标签列出相关笔记。
"""
import os
from collections import Counter

from PySide6.QtWidgets import (
    QGridLayout, QLabel, QPushButton, QScrollArea, QTextBrowser, QVBoxLayout, QWidget,
)

from wiki_paths import WIKI_DIR
from wiki_theme import get_theme_colors
from wiki_i18n import t
from wiki_data import iter_vault_md, parse_frontmatter_tags, read_text_safe


def collect_tags():
    """统计 vault 内所有标签的出现次数，返回 Counter。"""
    counter = Counter()
    for path in iter_vault_md():
        for tag in parse_frontmatter_tags(read_text_safe(path)):
            counter[tag] += 1
    return counter


def notes_by_tag(tag):
    """返回含指定标签的笔记相对路径列表（升序）。"""
    out = []
    for path in iter_vault_md():
        if tag in parse_frontmatter_tags(read_text_safe(path)):
            out.append(os.path.relpath(path, WIKI_DIR))
    return sorted(out)


class TagsTabMixin:
    def _build_tags_tab(self):
        T = get_theme_colors()
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self._section_label(layout, t("tags_title"))

        # 标签云（按钮网格，可滚动）
        self.tags_cloud = QWidget()
        self.tags_cloud_layout = QGridLayout(self.tags_cloud)
        self.tags_cloud_layout.setSpacing(8)
        self.tags_scroll = QScrollArea()
        self.tags_scroll.setWidgetResizable(True)
        self.tags_scroll.setWidget(self.tags_cloud)
        self.tags_scroll.setMaximumHeight(170)
        layout.addWidget(self.tags_scroll)

        # 笔记列表
        self.tags_notes_view = QTextBrowser()
        self.tags_notes_view.setStyleSheet(
            f"QTextBrowser {{ background-color: {T['SURFACE']}; border: 1px solid {T['BORDER']}; "
            f"border-radius: 10px; padding: 8px; color: {T['TEXT']}; }}"
        )
        layout.addWidget(self.tags_notes_view, stretch=1)

        self.nb.addTab(tab, t("tab_tags"))
        self.refresh_tags_cloud()

    def refresh_tags_cloud(self):
        """重建标签云按钮。"""
        while self.tags_cloud_layout.count():
            item = self.tags_cloud_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        counter = collect_tags()
        if not counter:
            self.tags_cloud_layout.addWidget(QLabel(t("tags_empty")), 0, 0)
            return
        T = get_theme_colors()
        tags = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
        for i, (tag, cnt) in enumerate(tags):
            btn = QPushButton(f"{tag} ({cnt})")
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {T['SURFACE']}; color: {T['TEXT']}; "
                f"border: 1px solid {T['BORDER']}; border-radius: 12px; padding: 4px 12px; font-size: 13px; }} "
                f"QPushButton:hover {{ background-color: {T['BTN_HOVER']}; }}"
            )
            btn.clicked.connect(lambda _=False, tg=tag: self.show_tag_notes(tg))
            self.tags_cloud_layout.addWidget(btn, i // 4, i % 4)

    def show_tag_notes(self, tag):
        """在下方列出含指定标签的笔记。"""
        T = get_theme_colors()
        notes = notes_by_tag(tag)
        head = (f"<p style='color:{T['TEXT2']}'>{t('tags_notes', tag=tag)} "
                f"— {t('tags_count', n=len(notes))}</p>")
        rows = "".join(
            f"<div style='color:{T['TEXT']};font-size:13px;margin:2px 0;'>· {n}</div>" for n in notes
        )
        self.tags_notes_view.setHtml(head + (rows or f"<p style='color:{T['TEXT2']}'>—</p>"))
        self.status_label.setText(t("tags_count", n=len(notes)))
