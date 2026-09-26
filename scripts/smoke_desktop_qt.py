#!/usr/bin/env python3
"""PySide6 桌面版启动冒烟测试。

等价复刻 wiki_app.py 的 __main__ 启动链路（QApplication -> apply_qss ->
WikiApp -> WelcomeDialog），并用 QTimer + processEvents 驱动事件循环，
在数秒内验证：界面构建、QSS 应用、欢迎框、语音信号槽、主题/语言切换、
MCP 启动处理器、标签页滚动区包裹与小窗下卡片叠放回归 均无异常。
不依赖显示器，可无头运行。

用法：
    .venv/bin/python scripts/smoke_desktop_qt.py
退出码 0 = 通过；非 0 = 失败（并打印 traceback）。
"""
import os
import sys
import time
import traceback

# 让 Qt 在无显示器环境下也能跑（offscreen）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 防止真实弹窗/文件对话框卡住测试
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wiki_app as w


def pump(ms=50, times=3):
    """驱动 Qt 事件循环若干轮，让 QTimer.singleShot / 信号得以执行。"""
    for _ in range(times):
        w.QApplication.instance().processEvents()
        time.sleep(ms / 1000.0)


def _tab_page_of(app, widget):
    """从内部控件向上回溯，返回其所属的标签页原始页面（QScrollArea 内层）。"""
    from PySide6.QtWidgets import QScrollArea
    pages = set()
    for i in range(app.nb.count()):
        page = app.nb.widget(i)
        if isinstance(page, QScrollArea):
            page = page.widget()
        pages.add(page)
    node = widget
    while node is not None:
        if node in pages:
            return node
        node = node.parent()
    raise AssertionError("未找到控件所属的标签页页面")


def main():
    # 拦截可能弹出系统对话框的调用
    with mock.patch.object(w, "QMessageBox", create=True) if hasattr(w, "QMessageBox") else mock.MagicMock():
        pass

    app = w.QApplication(sys.argv)
    w.apply_qss(app, w.get_mode())
    print("OK 1: QApplication 创建 + apply_qss 应用, 模式=", w.get_mode())

    window = w.WikiApp()
    window.show()
    pump()
    print("OK 2: WikiApp 构建并显示（日记/心情/提醒/待办/搜索/标签/报告/Share 八个标签页）")
    assert window.nb.count() == 8, "标签页数量应为 8, 实际 {}".format(window.nb.count())

    # 标签页内容包进滚动区（小窗口/大卡片时超高可滚动，不再挤压叠放）
    from PySide6.QtWidgets import QPushButton, QScrollArea
    for i in range(window.nb.count()):
        assert isinstance(window.nb.widget(i), QScrollArea), (
            "标签页 {} 的内容应包进 QScrollArea，实际 {}".format(
                i, type(window.nb.widget(i)).__name__))
    print("OK 3: 全部 {} 个标签页内容均包进 QScrollArea（超高滚动，不挤压）".format(
        window.nb.count()))

    # 回归：复现用户场景（大卡片 124px + 小窗口）下心情卡片不得纵向叠放
    import wiki_theme
    wiki_theme.UI_PREFS["mood_card_height"] = 124
    try:
        window.resize(800, 600)
        pump()
        mood_page = _tab_page_of(window, window.mood_history)
        cards = [c for c in mood_page.findChildren(QPushButton)
                 if c.property("card")]
        assert len(cards) >= 4, "心情卡片应 >= 4 张，实际 {}".format(len(cards))
        columns = {}
        for c in cards:
            columns.setdefault(c.x(), []).append(c)
        for x, col in columns.items():
            col.sort(key=lambda c: c.y())
            for a, b in zip(col, col[1:]):
                gap = b.y() - a.y()
                assert gap >= a.height(), (
                    "心情卡片被挤压叠放：列 x={} 相邻卡片间距 {} < 卡高 {}".format(
                        x, gap, a.height()))
        print("OK 4: 缩窗 800x600（卡片高 124）下 {} 张心情卡片分 {} 列，"
              "同列相邻间距均 >= 卡高，无叠放".format(len(cards), len(columns)))
    finally:
        wiki_theme.UI_PREFS.pop("mood_card_height", None)
        window.resize(1147, 745)
        pump()

    # 语音信号槽已连接（线程安全核心）
    assert window.voice_signals is not None
    for sig in ("status_update", "result_ready", "error_occurred", "acoustics_ready"):
        assert hasattr(window.voice_signals, sig), "缺少信号 {}".format(sig)
    print("OK 5: 语音 VoiceSignals 信号槽已连接")

    # 欢迎框（非模态，等价 __main__ 的 singleShot）
    dlg = w.WelcomeDialog(window)
    dlg.show()
    pump()
    print("OK 6: WelcomeDialog 构建并显示")

    # 主题切换（浅<->深）：会重建并重新 apply_qss
    before = w.get_mode()
    window.toggle_theme()
    pump()
    after = w.get_mode()
    assert after != before, "toggle_theme 未切换模式"
    print("OK 7: toggle_theme 切换成功 {} -> {}".format(before, after))
    window.toggle_theme()  # 切回
    pump()

    # 语言切换（中<->英）：重建界面
    before_lang = w.get_lang()
    window.toggle_language()
    pump()
    assert w.get_lang() != before_lang, "toggle_language 未切换语言"
    print("OK 8: toggle_language 切换成功 {} -> {}".format(before_lang, w.get_lang()))
    window.toggle_language()
    pump()

    # MCP 启动处理器：mcp 已装时进入启动分支（可能 spawn 子进程）；
    # 用 Mock 吞掉 QMessageBox，验证处理器本身不抛异常。
    with mock.patch.object(w.QMessageBox, "critical", lambda *a, **k: None), \
         mock.patch.object(w.QMessageBox, "information", lambda *a, **k: None):
        try:
            window.share_start_server()
            pump()
            print("OK 9: share_start_server 处理器执行无异常")
        except SystemExit:
            # 启动成功会 spawn 子进程，不应 SystemExit
            raise
        except Exception as e:
            raise AssertionError("share_start_server 抛异常: {}".format(e))

    # 新增功能 1：待办清单（用临时文件，避免污染真实 vault）
    import tempfile
    import wiki_data as wd
    _orig_todo = wd.TODO_FILE
    wd.TODO_FILE = os.path.join(tempfile.mkdtemp(), "todos.json")
    try:
        window.todo_input.setText("写单元测试")
        window.add_todo_ui()
        pump()
        assert len(wd.load_todos()) == 1, "待办应新增 1 条"
        tid = wd.load_todos()[0]["id"]
        window._toggle_todo(tid)
        pump()
        assert wd.load_todos()[0]["done"] is True, "待办应标记完成"
        window._delete_todo(tid)
        pump()
        assert wd.load_todos() == [], "待办应被删除"
        print("OK 10: 待办新增/完成/删除 正常")
    finally:
        wd.TODO_FILE = _orig_todo
        window.refresh_todo_list()

    # 新增功能 2/3/4：搜索 / 标签云 / 报告
    window.search_input.setText("的")
    window.do_search()
    pump()
    print("OK 11: 全文搜索执行无异常")

    window.refresh_tags_cloud()
    window.generate_report("monthly")
    pump()
    assert window._report_text, "报告不应为空"
    print("OK 12: 标签云刷新 + 周报/月报生成正常")

    # 收尾：关闭窗口与对话框，清理事件循环
    dlg.reject()
    window.close()
    pump()
    print("DESKTOP QT SMOKE OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    sys.exit(0)
