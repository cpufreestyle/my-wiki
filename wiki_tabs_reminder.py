#!/usr/bin/env python3
"""wiki_tabs_reminder.py — 提醒标签页（Mixin）

包含快捷提醒卡片、自定义提醒、待提醒列表与卡片高度拖拽手柄，
由 WikiApp 通过多继承组合。
"""
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget, QGraphicsDropShadowEffect,
)

from wiki_theme import get_theme_colors, get_ui_pref, set_ui_pref, is_dark, apply_card_shadow
from wiki_i18n import t
from wiki_data import load_reminders, add_reminder, cancel_reminder


class ResizeHandle(QLabel):
    """卡片底部拖拽手柄：上下拖动调整卡片高度，释放时保存偏好。
    仅在手柄范围内响应鼠标，不干扰卡片本身的点击。"""

    def __init__(self, card, on_release=None, parent=None):
        super().__init__("⎍", parent)
        self._card = card
        self._on_release = on_release
        self._dragging = False
        self._start_y = 0
        self._start_height = 0
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setFixedHeight(16)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        T = get_theme_colors()
        self.setStyleSheet(
            f"color: {T['TEXT2']}; background: transparent; border: none; "
            f"font-size: 10px; padding: 0;"
        )
        # 不透明鼠标事件，让手柄能接收拖拽
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_y = int(event.globalPosition().y())
            self._start_height = self._card.height()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = int(event.globalPosition().y()) - self._start_y
            new_height = max(60, self._start_height + delta)
            self._card.setFixedHeight(new_height)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            new_height = self._card.height()
            if self._on_release:
                self._on_release(new_height)
            event.accept()


class ReminderTabMixin:
    """提醒标签页：预设卡片 + 自定义提醒 + 待提醒列表 + 取消。"""

    def _build_reminder_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self._section_label(layout, t("quick_reminders"))

        # 预设卡片
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(get_ui_pref("card_gap", 12))
        preset_items = [
            ("+1h", 1, "快速稍后提醒"),
            ("+2h", 2, "午间 / 会议"),
            ("+3h", 3, "下午安排"),
            (t("tmr9"), "tmr9", "晨间待办"),
            (t("tmr18"), "tmr18", "下班提醒"),
        ]
        for i, (label, val, hint) in enumerate(preset_items):
            card = self._reminder_card(label, hint, lambda v=val: self.preset_reminder(v))
            grid.addWidget(card, i // 2, i % 2)
        layout.addWidget(grid_widget)

        # 自定义提醒卡片
        ccard = self._card_frame()
        clayout = QVBoxLayout(ccard)
        clayout.setContentsMargins(14, 14, 14, 14)
        clayout.setSpacing(8)
        custom_lbl = QLabel(t("custom"))
        custom_lbl.setStyleSheet(f"font-weight: 600; font-size: 14px; color: {get_theme_colors()['TEXT']};")
        clayout.addWidget(custom_lbl)
        row = QHBoxLayout()
        self.reminder_msg = QLineEdit()
        self.reminder_msg.setPlaceholderText("提醒内容…")
        row.addWidget(self.reminder_msg)
        self.reminder_time = QLineEdit()
        self.reminder_time.setPlaceholderText("HH:MM")
        self.reminder_time.setFixedWidth(80)
        row.addWidget(self.reminder_time)
        add_btn = self._primary_btn(t("add"), self.add_custom_reminder)
        row.addWidget(add_btn)
        clayout.addLayout(row)
        layout.addWidget(ccard)

        # 待提醒列表
        self._section_label(layout, t("pending"))
        self.pending_scroll = QScrollArea()
        self.pending_scroll.setWidgetResizable(True)
        self.pending_container = QWidget()
        self.pending_layout = QVBoxLayout(self.pending_container)
        self.pending_layout.setContentsMargins(0, 0, 0, 0)
        self.pending_layout.setSpacing(6)
        self.pending_layout.addStretch()
        self.pending_scroll.setWidget(self.pending_container)
        layout.addWidget(self.pending_scroll, stretch=1)

        # 取消提醒
        bot = QHBoxLayout()
        bot.addWidget(QLabel(t("cancel_id")))
        self.cancel_id_input = QLineEdit()
        self.cancel_id_input.setFixedWidth(60)
        bot.addWidget(self.cancel_id_input)
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.cancel_reminder_ui)
        bot.addWidget(cancel_btn)
        bot.addStretch()
        layout.addLayout(bot)

        self.nb.addTab(tab, t("tab_reminder"))
        self.refresh_reminder_list()

    def _reminder_card(self, title, hint, on_click):
        """预设提醒卡片（对齐网页 .preset-card：阴影无边框、圆点+标题+副文案）。
        行间距、内边距等可通过 UI 偏好手动调整（顶栏 ⚙️ 按钮）。"""
        T = get_theme_colors()
        dark = is_dark()
        # 从偏好读取可调参数
        line_spacing = get_ui_pref("card_line_spacing", 12)
        pad_v = get_ui_pref("card_padding_v", 16)
        pad_h = get_ui_pref("card_padding_h", 18)
        title_size = get_ui_pref("title_font_size", 15)
        hint_size = get_ui_pref("hint_font_size", 12)
        title_pad = get_ui_pref("title_line_padding", 2)
        min_height = get_ui_pref("card_min_height", 80)
        card = QPushButton()
        card.clicked.connect(on_click)
        card.setProperty("card", True)
        card.setMinimumHeight(min_height)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(pad_h, pad_v, pad_h, pad_v)
        card_layout.setSpacing(line_spacing)
        # 标题行：圆点 + 标题
        head = QHBoxLayout()
        head.setSpacing(10)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {T['ACCENT']}; font-size: 11px; background: transparent; border: none;")
        dot.setFixedSize(10, 10)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        head.addWidget(dot)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-weight: 600; font-size: {title_size}px; color: {T['TEXT']}; "
            f"border: none; background: transparent; padding: {title_pad}px 0;"
        )
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        head.addWidget(title_lbl)
        head.addStretch()
        card_layout.addLayout(head)
        # 副文案
        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(
            f"color: {T['TEXT2']}; font-size: {hint_size}px; border: none; background: transparent; "
            f"padding-left: 20px; padding-top: 2px;"
        )
        hint_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(hint_lbl)
        # 弹性间距，让手柄靠底
        card_layout.addStretch()
        # 拖拽手柄（拖动调整卡片高度，释放后保存并重建）
        handle = ResizeHandle(card, on_release=self._on_card_resized)
        handle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        card_layout.addWidget(handle, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        # 阴影
        apply_card_shadow(card, dark)
        return card

    def _on_card_resized(self, new_height):
        """卡片拖拽手柄释放后回调：保存高度偏好并重建 UI。"""
        set_ui_pref("card_min_height", new_height)
        self._rebuild_ui()

    def preset_reminder(self, val):
        """预设提醒：+N 小时或明早 9 点 / 明晚 18 点。"""
        now = datetime.now()
        msg = self.reminder_msg.text().strip() or "Reminder!"
        if isinstance(val, int):
            target = now + timedelta(hours=val)
        elif val == "tmr9":
            target = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        elif val == "tmr18":
            target = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        else:
            return
        add_reminder(target, msg)
        self.status_label.setText(t("reminder_set", t=target.strftime('%H:%M'), m=msg))
        self.refresh_reminder_list()

    def add_custom_reminder(self):
        """自定义提醒：内容 + HH:MM（过期自动顺延到明天）。"""
        msg = self.reminder_msg.text().strip()
        time_str = self.reminder_time.text().strip()
        if not msg:
            self.status_label.setText(t("enter_msg"))
            return
        try:
            h, m = map(int, time_str.split(":"))
            target = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= datetime.now():
                target += timedelta(days=1)
            add_reminder(target, msg)
            self.status_label.setText(t("reminder_set", t=target.strftime('%H:%M'), m=msg))
            self.refresh_reminder_list()
        except ValueError:
            self.status_label.setText(t("bad_time"))

    def cancel_reminder_ui(self):
        """按编号取消待提醒。"""
        try:
            rid = int(self.cancel_id_input.text().strip())
            if cancel_reminder(rid):
                self.status_label.setText(t("reminder_cancelled", i=rid))
                self.refresh_reminder_list()
            else:
                self.status_label.setText(t("cannot_cancel", i=rid))
        except ValueError:
            self.status_label.setText(t("enter_id"))

    def refresh_reminder_list(self):
        """刷新待提醒列表卡片。"""
        # 清除旧卡片（保留末尾的 stretch）
        while self.pending_layout.count() > 1:
            item = self.pending_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        reminders = load_reminders()
        pending = [r for r in reminders if r["status"] == "pending"]
        T = get_theme_colors()
        dark = is_dark()
        if not pending:
            empty = QLabel(t("no_pending"))
            empty.setStyleSheet(f"color: {T['TEXT2']}; font-size: 14px; padding: 20px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.pending_layout.insertWidget(0, empty)
        else:
            for r in pending:
                card = QFrame()
                card.setProperty("card", True)
                apply_card_shadow(card, dark)
                cl = QVBoxLayout(card)
                cl.setContentsMargins(16, 14, 16, 14)
                cl.setSpacing(4)
                head = QLabel(f"#{r['id']}  {r['remind_at']}")
                head.setStyleSheet(f"color: {T['ACCENT']}; font-weight: 600; font-size: 13px; border: none; background: transparent;")
                cl.addWidget(head)
                body = QLabel(r["message"])
                body.setStyleSheet(f"font-size: 15px; color: {T['TEXT']}; border: none; background: transparent;")
                body.setWordWrap(True)
                cl.addWidget(body)
                self.pending_layout.insertWidget(self.pending_layout.count() - 1, card)
