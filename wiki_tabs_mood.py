#!/usr/bin/env python3
"""wiki_tabs_mood.py — 心情标签页（Mixin）

包含心情输入、快捷心情卡片、文本 + 声学融合分析、语音录入与
麦克风权限处理，由 WikiApp 通过多继承组合。
"""
import subprocess
import sys
import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout, QGraphicsDropShadowEffect,
)

import voice_mood
from wiki_theme import get_theme_colors, is_dark, ui_font, mono_font, apply_card_shadow
from wiki_i18n import get_lang, t
from wiki_data import (
    get_today, load_moods, save_mood, analyze_mood, MOOD_EMOJI,
)


class MoodTabMixin:
    """心情标签页：输入 / 语音 / 快捷卡片 / 自动分析 / 今日记录。"""

    def _build_mood_tab(self):
        from PySide6.QtWidgets import QWidget
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self._section_label(layout, t("mood_q"))

        # 输入卡片
        inp_card = self._card_frame()
        inp_layout = QVBoxLayout(inp_card)
        inp_layout.setContentsMargins(14, 14, 14, 14)
        inp_layout.setSpacing(10)
        self.mood_input = QPlainTextEdit()
        self.mood_input.setFont(ui_font(13))
        self.mood_input.setFixedHeight(90)
        inp_layout.addWidget(self.mood_input)

        # 语音行
        vrow = QHBoxLayout()
        vrow.setSpacing(10)
        self.voice_btn = QPushButton(t("voice"))
        self.voice_btn.clicked.connect(self.on_voice_toggle)
        vrow.addWidget(self.voice_btn)

        mic_btn = QPushButton(t("mic_perm_btn"))
        mic_btn.setFixedWidth(40)
        mic_btn.clicked.connect(self._show_mic_permission_dialog)
        vrow.addWidget(mic_btn)

        vrow.addStretch()

        self.voice_status = QLabel("")
        self.voice_status.setStyleSheet(f"color: {get_theme_colors()['TEXT2']}; font-size: 12px;")
        vrow.addWidget(self.voice_status)
        vrow.addStretch()

        self.voice_autosave = QCheckBox(t("voice_autosave"))
        self.voice_autosave.setChecked(voice_mood.load_autosave_pref())
        self.voice_autosave.toggled.connect(
            lambda v: voice_mood.save_autosave_pref(v))
        vrow.addWidget(self.voice_autosave)
        inp_layout.addLayout(vrow)

        layout.addWidget(inp_card)

        # 快捷心情卡片网格
        grid_widget = type(self) and None or None
        from PySide6.QtWidgets import QWidget as _QW
        grid_widget = _QW()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(12)
        for i, (mood, emoji) in enumerate(MOOD_EMOJI.items()):
            card = self._mood_card(f"{emoji} {mood}", lambda m=mood: self.quick_mood(m))
            grid.addWidget(card, i // 2, i % 2)
        layout.addWidget(grid_widget)

        # 分析按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        analyze_btn = self._primary_btn(t("auto_analyze"), lambda: self.analyze_mood_ui())
        btn_row.addWidget(analyze_btn)
        self.mood_result = QLabel("")
        self.mood_result.setStyleSheet(f"color: {get_theme_colors()['GREEN']}; font-size: 14px; font-weight: 600;")
        btn_row.addWidget(self.mood_result)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 今日记录
        self._section_label(layout, t("today_records"))
        hist_card = self._card_frame()
        hist_layout = QVBoxLayout(hist_card)
        hist_layout.setContentsMargins(14, 14, 14, 14)
        self.mood_history = QPlainTextEdit()
        self.mood_history.setFont(mono_font(12))
        self.mood_history.setReadOnly(True)
        hist_layout.addWidget(self.mood_history)
        layout.addWidget(hist_card, stretch=1)

        self.nb.addTab(tab, t("tab_mood"))
        self.refresh_mood_history()

    def _mood_card(self, title, on_click):
        """心情卡片（对齐网页 .mood-card：圆点 + 标签，阴影无边框，hover 上浮）。"""
        T = get_theme_colors()
        dark = is_dark()
        # 卡片高度对齐网页端 --card-h（默认 52px，可在设置面板 44-160 间调节）
        from wiki_theme import get_ui_pref
        mood_h = get_ui_pref("mood_card_height", 52)
        card = QPushButton()
        card.clicked.connect(on_click)
        card.setProperty("card", True)
        card.setFixedHeight(mood_h)
        # 卡片内部布局：圆点 + 标签
        card_layout = QHBoxLayout(card)
        # 内边距跟随卡片高度自适应，避免在 52px 高度下文字溢出
        pad_v = max(6, int((mood_h - 23) / 2))
        card_layout.setContentsMargins(16, pad_v, 16, pad_v)
        card_layout.setSpacing(12)
        # 圆点
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {T['ACCENT']}; font-size: 10px; background: transparent; border: none;")
        dot.setFixedSize(8, 8)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(dot)
        # 标签
        label = QLabel(title)
        label.setStyleSheet(f"font-size: 15px; font-weight: 500; color: {T['TEXT']}; background: transparent; border: none;")
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(label)
        card_layout.addStretch()
        # 阴影
        apply_card_shadow(card, dark)
        return card

    def quick_mood(self, mood):
        """快捷心情一键记录。"""
        text = self.mood_input.toPlainText().strip()
        if not text:
            text = f"(quick: {mood})"
        save_mood(get_today(), mood, text, 1.0, "manual")
        self.mood_result.setText(f"{MOOD_EMOJI.get(mood, '')} {mood} ✓")
        self.mood_input.clear()
        self.refresh_mood_history()
        self.status_label.setText(t("mood_saved", m=mood))
        self.mood_input.setFocus()

    def analyze_mood_ui(self, acoustics=None):
        """自动分析：文本关键词 + 声学特征加权融合后保存。"""
        text = self.mood_input.toPlainText().strip()
        if not text and not acoustics:
            self.mood_result.setText(t("type_first"))
            self.mood_input.setFocus()
            return

        text_mood, text_conf, text_reason = ("平静", 0, "")
        if text:
            text_mood, text_conf, text_reason = analyze_mood(text)

        acou_mood, acou_conf, acou_detail = (None, 0, "")
        if acoustics:
            acou_mood, acou_conf, acou_detail = voice_mood.acoustics_to_mood(acoustics)

        if acou_mood and text:
            MOODS = list(MOOD_EMOJI.keys())
            combined = {m: 0 for m in MOODS}
            combined[text_mood] += text_conf * 0.6
            combined[acou_mood] += acou_conf * 0.4
            best_mood = max(combined, key=combined.get)
            best_conf = min(combined[best_mood], 1.0)
            parts = []
            if text_reason and text_reason != "未检测到明显情绪词":
                parts.append("文本: {}".format(text_reason))
            if acou_detail:
                parts.append("声音: {}".format(acou_detail))
            reason = " | ".join(parts) if parts else acou_detail or text_reason
        elif acou_mood and not text:
            best_mood = acou_mood
            best_conf = acou_conf
            reason = "声音分析: {}".format(acou_detail)
        else:
            best_mood = text_mood
            best_conf = text_conf
            reason = text_reason

        save_text = text if text else "(语音: {})".format((acou_detail or "")[:50])
        save_mood(get_today(), best_mood, save_text, best_conf, reason)
        emoji = MOOD_EMOJI.get(best_mood, "")
        detail = ""
        if acou_mood and text_mood and acou_mood != text_mood:
            detail = " (文本→{} 声音→{})".format(text_mood, acou_mood)
        self.mood_result.setText(f"{emoji} {best_mood} ({best_conf:.0%}){detail}")
        self.mood_input.clear()
        self.refresh_mood_history()
        self.status_label.setText(t("mood_saved", m=f"{best_mood} ({best_conf:.0%})"))
        self.mood_input.setFocus()

    # ==================== 语音功能 ====================
    def _voice_lang(self):
        return "zh-CN" if get_lang() == "zh" else "en-US"

    def on_voice_toggle(self):
        """语音按钮：缺失依赖时引导安装；录音中则停止。"""
        if not self.voice_deps_ok:
            ffmpeg_ok, sr_ok = voice_mood.deps_status()
            if not (ffmpeg_ok and sr_ok):
                need = []
                if not ffmpeg_ok:
                    need.append(t("voice_missing_ffmpeg"))
                if not sr_ok:
                    need.append(t("voice_missing_sr"))
                reply = QMessageBox.question(self, "语音依赖缺失",
                    t("voice_confirm_install").format(n="、".join(need)))
                if reply != QMessageBox.StandardButton.Yes:
                    return
                self._start_voice_install()
                return

        if self.voice_recorder.running:
            self.voice_recorder.stop()
            self.voice_btn.setText(t("voice"))
            self.voice_status.setText("识别中…")
            self.status_label.setText("停止录音，正在识别…")
            return

        self.voice_btn.setText(t("voice_stop"))
        self.voice_status.setText(t("voice_recording").format(n=voice_mood.MAX_SECONDS))
        self.status_label.setText(t("voice_recording").format(n=voice_mood.MAX_SECONDS))
        self.voice_recorder.start(lang=self._voice_lang())

    def _start_voice_install(self):
        """禁用按钮并后台安装语音依赖。"""
        self.voice_btn.setEnabled(False)
        self.voice_btn.setText(t("voice_installing"))
        self.voice_status.setText(t("voice_installing"))

        self._install_thread = threading.Thread(target=self._install_voice_deps, daemon=True)
        self._install_thread.start()
        QTimer.singleShot(200, self._poll_voice_install)

    def _install_voice_deps(self):
        try:
            self._voice_install_result = voice_mood.auto_install_deps()
        except Exception as e:
            self._voice_install_result = (False, False, ["安装异常：{}".format(e)])

    def _poll_voice_install(self):
        if not hasattr(self, '_voice_install_result') or self._voice_install_result is None:
            if hasattr(self, '_install_thread') and self._install_thread.is_alive():
                QTimer.singleShot(200, self._poll_voice_install)
                return
        if hasattr(self, '_voice_install_result') and self._voice_install_result:
            ffmpeg_ok, sr_ok, notes = self._voice_install_result
            self._voice_install_result = None
            self.voice_btn.setEnabled(True)
            ok = ffmpeg_ok and sr_ok
            self.voice_deps_ok = ok
            if ok:
                self.voice_status.setText(t("voice_install_ok"))
                self.status_label.setText(t("voice_install_ok"))
                self.on_voice_toggle()
            else:
                detail = t("voice_install_fail")
                if not ffmpeg_ok:
                    detail += "\n" + t("voice_need_ffmpeg")
                if not sr_ok:
                    detail += "\n" + t("voice_need_sr").format(py=sys.executable)
                if notes:
                    detail += "\n\n" + "\n".join(notes)
                QMessageBox.critical(self, "语音依赖安装失败", detail)

    def on_voice_result(self, text, acoustics=None):
        """识别结果回填 / 自动保存。"""
        if text:
            cur = self.mood_input.toPlainText().strip()
            if cur:
                self.mood_input.setPlainText(cur + "\n" + text)
            else:
                self.mood_input.setPlainText(text)

        self.voice_btn.setText(t("voice"))

        if text:
            display = text[:40] + ("…" if len(text) > 40 else "")
        elif acoustics:
            acou_mood, _, acou_detail = voice_mood.acoustics_to_mood(acoustics)
            display = "声音→{} ({})".format(acou_mood or "未知", (acou_detail or "")[:30])
        else:
            display = "未识别到内容"

        if self.voice_autosave.isChecked():
            self.voice_status.setText("已识别：{}".format(display))
            self.status_label.setText("已识别：{}".format(display))
            self.analyze_mood_ui(acoustics=acoustics)
        else:
            self.voice_status.setText("已填入：{}".format(display))
            self.status_label.setText(t("voice_filled"))
            self.mood_input.setFocus()

    def on_voice_acoustics(self, features):
        """声学特征实时提示。"""
        try:
            acou_mood, _, acou_detail = voice_mood.acoustics_to_mood(features)
            emoji = MOOD_EMOJI.get(acou_mood, "")
            self.voice_status.setText("声音特征: {} {} {}".format(
                emoji, acou_mood, (acou_detail or "")[:20]))
        except Exception:
            pass

    def on_voice_error(self, msg):
        """语音出错提示；麦克风权限问题自动弹帮助。"""
        self.voice_btn.setText(t("voice"))
        self.voice_status.setText(msg)
        self.status_label.setText(msg)
        low = (msg or "").lower()
        if "麦克风权限被拒绝" in (msg or "") or "microphone" in low or "operation not permitted" in low:
            self._show_mic_permission_dialog()

    def on_voice_status(self, state, msg):
        """语音状态按钮文案联动。"""
        if state == "recording":
            self.voice_btn.setText(t("voice_stop"))
        elif state in ("idle", "done"):
            self.voice_btn.setText(t("voice"))
        self.voice_status.setText(msg)

    def _show_mic_permission_dialog(self):
        """麦克风权限帮助对话框（含 macOS 一键重置）。"""
        dlg = QDialog(self)
        dlg.setWindowTitle(t("mic_perm_title"))
        dlg.setFixedWidth(420)
        dlg_layout = QVBoxLayout(dlg)
        help_lbl = QLabel(t("mic_perm_help"))
        help_lbl.setWordWrap(True)
        dlg_layout.addWidget(help_lbl)
        btn_row = QHBoxLayout()
        reset_btn = self._primary_btn(t("mic_perm_reset"), lambda: self._reset_mic_permission(dlg))
        btn_row.addWidget(reset_btn)
        close_btn = QPushButton(t("close"))
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)
        dlg_layout.addLayout(btn_row)
        dlg.exec()

    def _reset_mic_permission(self, dlg):
        """tccutil 重置麦克风授权（仅 macOS）。"""
        if sys.platform != "darwin":
            dlg.accept()
            QMessageBox.information(self, t("mic_perm_title"), t("mic_perm_only_mac"))
            return
        try:
            res = subprocess.run(["tccutil", "reset", "Microphone"],
                                 capture_output=True, text=True, timeout=20)
            ok = res.returncode == 0
        except Exception:
            ok = False
        dlg.accept()
        if ok:
            QMessageBox.information(self, t("mic_perm_title"), t("mic_perm_reset_ok"))
        else:
            QMessageBox.critical(self, t("mic_perm_title"), t("mic_perm_reset_fail"))

    def _stop_voice_if_running(self):
        """语言/主题切换前停掉录音，避免回调打到已销毁的控件。"""
        if self.voice_recorder and self.voice_recorder.running:
            try:
                self.voice_recorder.stop()
            except Exception:
                pass

    def refresh_mood_history(self):
        """刷新今日心情记录展示。"""
        records = load_moods(get_today())
        lines = []
        if records:
            for r in records:
                emoji = MOOD_EMOJI.get(r.get("mood", ""), "")
                conf = r.get("confidence", 0)
                line = f"[{r.get('time', '?')}] {emoji} {r.get('mood', '?')} ({conf:.0%}) - {r.get('text', '')[:40]}"
                lines.append(line)
        else:
            lines.append(t("no_records"))
        self.mood_history.setPlainText("\n".join(lines))
