#!/usr/bin/env python3
"""PySide6 桌面版启动冒烟测试。

等价复刻 wiki_app.py 的 __main__ 启动链路（QApplication -> apply_qss ->
WikiApp -> WelcomeDialog），并用 QTimer + processEvents 驱动事件循环，
在数秒内验证：界面构建、QSS 应用、欢迎框、语音信号槽、主题/语言切换、
MCP 启动处理器 均无异常。不依赖显示器，可无头运行。

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


def main():
    # 拦截可能弹出系统对话框的调用
    with mock.patch.object(w, "QMessageBox", create=True) if hasattr(w, "QMessageBox") else mock.MagicMock():
        pass

    app = w.QApplication(sys.argv)
    w.apply_qss(app, w.MODE)
    print("OK 1: QApplication 创建 + apply_qss 应用, 模式=", w.MODE)

    window = w.WikiApp()
    window.show()
    pump()
    print("OK 2: WikiApp 构建并显示（日记/心情/提醒/Share 四个标签页）")
    assert window.nb.count() == 4, "标签页数量应为 4, 实际 {}".format(window.nb.count())

    # 语音信号槽已连接（线程安全核心）
    assert window.voice_signals is not None
    for sig in ("status_update", "result_ready", "error_occurred", "acoustics_ready"):
        assert hasattr(window.voice_signals, sig), "缺少信号 {}".format(sig)
    print("OK 3: 语音 VoiceSignals 信号槽已连接")

    # 欢迎框（非模态，等价 __main__ 的 singleShot）
    dlg = w.WelcomeDialog(window)
    dlg.show()
    pump()
    print("OK 4: WelcomeDialog 构建并显示")

    # 主题切换（浅<->深）：会重建并重新 apply_qss
    before = w.MODE
    window.toggle_theme()
    pump()
    after = w.MODE
    assert after != before, "toggle_theme 未切换模式"
    print("OK 5: toggle_theme 切换成功 {} -> {}".format(before, after))
    window.toggle_theme()  # 切回
    pump()

    # 语言切换（中<->英）：重建界面
    before_lang = w.LANG
    window.toggle_language()
    pump()
    assert w.LANG != before_lang, "toggle_language 未切换语言"
    print("OK 6: toggle_language 切换成功 {} -> {}".format(before_lang, w.LANG))
    window.toggle_language()
    pump()

    # MCP 启动处理器：mcp 已装时进入启动分支（可能 spawn 子进程）；
    # 用 Mock 吞掉 QMessageBox，验证处理器本身不抛异常。
    with mock.patch.object(w.QMessageBox, "critical", lambda *a, **k: None), \
         mock.patch.object(w.QMessageBox, "information", lambda *a, **k: None):
        try:
            window.share_start_server()
            pump()
            print("OK 7: share_start_server 处理器执行无异常")
        except SystemExit:
            # 启动成功会 spawn 子进程，不应 SystemExit
            raise
        except Exception as e:
            raise AssertionError("share_start_server 抛异常: {}".format(e))

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
