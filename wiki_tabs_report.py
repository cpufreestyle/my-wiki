#!/usr/bin/env python3
"""wiki_tabs_report.py — 周报 / 月报标签页（ReportTabMixin）

一键生成周期报告（汇总日记 / 心情 / 待办），支持复制与保存到 vault。
"""
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from wiki_theme import get_theme_colors
from wiki_i18n import t
import wiki_report


class ReportTabMixin:
    def _build_report_tab(self):
        T = get_theme_colors()
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self._section_label(layout, t("report_title"))

        row = QHBoxLayout()
        row.addWidget(self._primary_btn(t("report_weekly"), lambda: self.generate_report("weekly")))
        row.addWidget(self._primary_btn(t("report_monthly"), lambda: self.generate_report("monthly")))
        row.addStretch()
        copy_btn = QPushButton(t("report_copy"))
        copy_btn.clicked.connect(self.copy_report)
        row.addWidget(copy_btn)
        save_btn = QPushButton(t("report_save"))
        save_btn.clicked.connect(self.save_report)
        row.addWidget(save_btn)
        layout.addLayout(row)

        self.report_view = QTextBrowser()
        self.report_view.setStyleSheet(
            f"QTextBrowser {{ background-color: {T['SURFACE']}; border: 1px solid {T['BORDER']}; "
            f"border-radius: 10px; padding: 10px; color: {T['TEXT']}; }}"
        )
        layout.addWidget(self.report_view, stretch=1)

        self.nb.addTab(tab, t("tab_report"))
        self._report_text = ""
        self.generate_report("weekly")

    def generate_report(self, kind):
        """生成周报 / 月报并渲染。"""
        self._report_text = (wiki_report.monthly_report() if kind == "monthly"
                             else wiki_report.weekly_report())
        self.report_view.setMarkdown(self._report_text)

    def copy_report(self):
        """复制当前报告 Markdown 到剪贴板。"""
        QApplication.clipboard().setText(self._report_text)
        self.status_label.setText(t("report_copied"))

    def save_report(self):
        """保存报告到 vault 根目录。"""
        name = "report-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".md"
        path = wiki_report.save_report(self._report_text, name)
        self.status_label.setText(t("report_saved", p=path))
