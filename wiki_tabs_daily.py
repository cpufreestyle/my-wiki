#!/usr/bin/env python3
"""wiki_tabs_daily.py — 日记标签页（Mixin）

将原 wiki_app.py 中的日记 UI 构建与交互逻辑拆出，
由 WikiApp 通过多继承组合。
"""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QVBoxLayout

from wiki_theme import get_theme_colors, mono_font
from wiki_i18n import t
from wiki_data import get_today, get_now, load_daily, save_daily, extract_tags


class DailyTabMixin:
    """日记标签页：编辑器 + 模板插入 + 标签提取 + 保存。"""

    def _build_daily_tab(self):
        tab = type(self).__dict__ and None  # 占位避免 lint；实际类型见下方 QWidget
        from PySide6.QtWidgets import QWidget
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # 顶部：日期 + 按钮
        top = QHBoxLayout()
        top.setSpacing(8)
        date_lbl = QLabel(get_today())
        date_lbl.setStyleSheet(f"font-weight: 600; font-size: 17px; color: {get_theme_colors()['TEXT']};")
        top.addWidget(date_lbl)
        top.addStretch()
        tags_btn = QPushButton(t("tags"))
        tags_btn.clicked.connect(self.extract_and_show_tags)
        top.addWidget(tags_btn)
        tpl_btn = QPushButton(t("template"))
        tpl_btn.clicked.connect(self.insert_template)
        top.addWidget(tpl_btn)
        layout.addLayout(top)

        # 编辑器卡片
        editor_card = self._card_frame()
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(4, 4, 4, 4)
        self.daily_text = QPlainTextEdit()
        self.daily_text.setFont(mono_font(13))
        self.daily_text.setPlainText(load_daily(get_today()))
        editor_layout.addWidget(self.daily_text)
        layout.addWidget(editor_card, stretch=1)

        # 底部：保存 + 标签显示
        bot = QHBoxLayout()
        bot.setSpacing(10)
        self.tag_display = QLabel("")
        self.tag_display.setStyleSheet(f"color: {get_theme_colors()['GREEN']}; font-size: 13px; font-weight: 500;")
        bot.addWidget(self.tag_display)
        bot.addStretch()
        save_btn = self._primary_btn(t("save"), self.save_daily)
        bot.addWidget(save_btn)
        layout.addLayout(bot)

        self.nb.addTab(tab, t("tab_diary"))

    def insert_template(self):
        """在光标处插入日记模板。"""
        template = "\n## Done\n- \n\n## Thoughts\n- \n\n## Tomorrow\n- \n"
        self.daily_text.insertPlainText(template)
        self.daily_text.setFocus()

    def save_daily(self):
        """保存今日日记。"""
        content = self.daily_text.toPlainText().strip()
        save_daily(get_today(), content)
        self.status_label.setText(f"{t('diary_saved')} - {get_today()} {get_now()}")
        self.daily_text.setFocus()

    def extract_and_show_tags(self):
        """提取日记关键词标签并展示。"""
        content = self.daily_text.toPlainText()
        tags = extract_tags(content)
        if tags:
            self.tag_display.setText(f"{t('tags')}: {', '.join(tags)}")
            self.status_label.setText(t("extracted_tags", n=len(tags)))
        else:
            self.tag_display.setText(t("no_tags"))
            self.status_label.setText(t("no_keywords"))
        self.daily_text.setFocus()
