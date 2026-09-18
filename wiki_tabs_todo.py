#!/usr/bin/env python3
"""wiki_tabs_todo.py — 待办清单标签页（TodoTabMixin）

新增 / 完成 / 删除待办，落盘到 vault/todos.json；数据逻辑在 wiki_data。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from wiki_theme import get_theme_colors
from wiki_i18n import t
from wiki_data import add_todo, delete_todo, load_todos, sort_todos, toggle_todo

# 优先级 → 主题色 token
PRIORITY_COLORS = {"high": "ORANGE", "medium": "ACCENT", "low": "TEXT2"}


class TodoTabMixin:
    def _build_todo_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self._section_label(layout, t("todo_add"))

        # 新增待办卡片
        card = self._card_frame()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 14, 14, 14)
        cl.setSpacing(8)
        row = QHBoxLayout()
        self.todo_input = QLineEdit()
        self.todo_input.setPlaceholderText(t("todo_ph"))
        self.todo_input.returnPressed.connect(self.add_todo_ui)
        row.addWidget(self.todo_input, stretch=1)
        self.todo_priority = QComboBox()
        for label, val in ((t("pri_high"), "high"), (t("pri_medium"), "medium"), (t("pri_low"), "low")):
            self.todo_priority.addItem(label, val)
        self.todo_priority.setCurrentIndex(1)
        self.todo_priority.setFixedWidth(80)
        row.addWidget(self.todo_priority)
        self.todo_due = QLineEdit()
        self.todo_due.setPlaceholderText(t("todo_due_ph"))
        self.todo_due.setFixedWidth(130)
        row.addWidget(self.todo_due)
        row.addWidget(self._primary_btn(t("add"), self.add_todo_ui))
        cl.addLayout(row)
        layout.addWidget(card)

        # 待办列表
        self._section_label(layout, t("todo_list"))
        self.todo_scroll = QScrollArea()
        self.todo_scroll.setWidgetResizable(True)
        self.todo_container = QWidget()
        self.todo_layout = QVBoxLayout(self.todo_container)
        self.todo_layout.setContentsMargins(0, 0, 0, 0)
        self.todo_layout.setSpacing(6)
        self.todo_layout.addStretch()
        self.todo_scroll.setWidget(self.todo_container)
        layout.addWidget(self.todo_scroll, stretch=1)

        self.nb.addTab(tab, t("tab_todo"))
        self.refresh_todo_list()

    def refresh_todo_list(self):
        """按当前待办数据重建列表。"""
        while self.todo_layout.count() > 1:
            item = self.todo_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        todos = sort_todos(load_todos())
        if not todos:
            empty = QLabel(t("todo_empty"))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.todo_layout.insertWidget(0, empty)
            return
        for todo in todos:
            self.todo_layout.insertWidget(self.todo_layout.count() - 1, self._todo_card(todo))

    def _todo_card(self, todo):
        T = get_theme_colors()
        done = bool(todo.get("done"))
        card = self._card_frame()
        h = QHBoxLayout(card)
        h.setContentsMargins(14, 10, 14, 10)
        h.setSpacing(10)

        # 完成勾选按钮
        check = QPushButton("✓" if done else "")
        check.setFixedSize(24, 24)
        check.setStyleSheet(
            f"QPushButton {{ border-radius: 12px; font-size: 14px; font-weight: 700; "
            f"background-color: {T['GREEN'] if done else 'transparent'}; "
            f"color: {'#FFFFFF' if done else T['TEXT2']}; "
            f"border: 2px solid {T['GREEN'] if done else T['BORDER']}; }}"
        )
        check.clicked.connect(lambda _=False, tid=todo["id"]: self._toggle_todo(tid))
        h.addWidget(check)

        # 正文
        text = QLabel(todo.get("text", ""))
        strike = " text-decoration: line-through;" if done else ""
        text.setStyleSheet(f"color: {T['TEXT2'] if done else T['TEXT']}; font-size: 14px;{strike}")
        text.setWordWrap(True)
        h.addWidget(text, stretch=1)

        # 优先级 · 截止
        p = todo.get("priority", "medium")
        meta = [t(f"pri_{p}")]
        if todo.get("due"):
            meta.append(todo["due"])
        meta_lbl = QLabel(" · ".join(meta))
        meta_lbl.setStyleSheet(f"color: {T[PRIORITY_COLORS.get(p, 'TEXT2')]}; font-size: 12px;")
        h.addWidget(meta_lbl)

        # 删除
        del_btn = QPushButton("🗑")
        del_btn.setFixedSize(28, 28)
        del_btn.setToolTip(t("cancel"))
        del_btn.setStyleSheet(
            f"QPushButton {{ border: none; font-size: 13px; color: {T['TEXT2']}; background: transparent; }} "
            f"QPushButton:hover {{ color: {T['ORANGE']}; }}"
        )
        del_btn.clicked.connect(lambda _=False, tid=todo["id"]: self._delete_todo(tid))
        h.addWidget(del_btn)
        return card

    def add_todo_ui(self):
        text = self.todo_input.text().strip()
        if not text:
            QMessageBox.information(self, t("app_title"), t("todo_need_text"))
            return
        add_todo(text, priority=self.todo_priority.currentData(), due=self.todo_due.text().strip())
        self.todo_input.clear()
        self.todo_due.clear()
        self.refresh_todo_list()
        self.status_label.setText(t("todo_added"))

    def _toggle_todo(self, tid):
        toggle_todo(tid)
        self.refresh_todo_list()

    def _delete_todo(self, tid):
        delete_todo(tid)
        self.refresh_todo_list()
