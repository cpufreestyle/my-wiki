# MyWiki v2.7.0 — PySide6 迁移 + 语音声学分析增强

> 本文件记录 v2.7.0 的变更。两大核心改动：**桌面端 GUI 从 Tkinter 迁移到 PySide6**，以及**语音心情录制新增声学分析**。

## 🔄 核心改动一：Tkinter → PySide6 全量迁移

### 背景

桌面端 `wiki_app.py` 原本基于 Tkinter，在 macOS 上存在多个长期痛点：

- **跨线程回调不可靠**：Tkinter 从子线程调用 `root.after()` 在 macOS 上经常不执行，导致录音识别后 UI 卡在"识别中…"
- **深色模式按钮失效**：`tk.Button` 的 `bg`/`fg` 在 macOS 系统深色外观下被 Aqua 主题接管，自定义按钮几乎不可见
- **模态对话框锁死输入**：`tk.Toplevel` + `grab_set()` 在 macOS 下会拦截主窗口全部输入
- **ScrolledText 在 Notebook 内失焦**：macOS 自带 Tk 8.5 (Carbon) 下键盘输入异常

### 迁移成果

| 方面 | Tkinter 旧版 | PySide6 新版 |
|------|-------------|-------------|
| 线程安全 | 手动队列轮询 (`_ui_queue` + `_poll_ui_queue` + `after(100)`) | 信号槽机制天然线程安全 (`VoiceSignals` + `Signal` + 自动队列连接) |
| 样式 | 逐控件设 `bg`/`fg`，用 `Label` 模拟按钮 | 全局 QSS 样式表（类 CSS），属性选择器 `QPushButton[primary="true"]` |
| 对话框 | `Toplevel` + 手动 `grab_set`（锁死主窗口） | `QDialog` + `exec()`，原生模态不锁主窗口 |
| 快捷键 | `root.bind("<Control-s>")` | `QShortcut(QKeySequence("Ctrl+S"))` |
| 可拖拽分隔 | `tk.PanedWindow` | `QSplitter` |
| 代码量 | 1802 行 | ~1050 行（更简洁） |

### 文件变更

- `wiki_app.py`：完全重写，使用 PySide6（QMainWindow / QTabWidget / QPlainTextEdit / QSplitter / Signal-Slot）
- `MyWiki.app/Contents/MacOS/mywiki`：启动器简化，移除 Tk 版本检测逻辑，改为检测 PySide6
- 依赖：新增 `PySide6`（已安装到 `.venv`）

### 测试

自动化功能测试 **46 项全部通过**，覆盖：
- 核心逻辑：心情分析（开心/低落/平静）、标签提取、日记/心情/提醒存储、中英文 i18n、主题色
- GUI 界面：4 个标签页、所有控件、保存日记、心情分析、语言切换、主题切换

## 🎤 核心改动二：语音声学分析增强

### 声学特征提取

- **桌面端** (`voice_mood.py`)：新增 `analyze_voice_acoustics` 与 `acoustics_to_mood`，使用 `wave`/`struct`/`math` 本地提取音频特征（能量、过零率、基频、频谱质心、静音比），映射到心情
- **网页端** (`voice-controller.js`)：集成 Web Audio API (`AnalyserNode`) 进行浏览器端实时声学分析
- **后端** (`web_server.py`：新增)：为非浏览器环境提供录音/识别 API，集成 `voice_mood.analyze_voice_acoustics`

### 融合策略

文本分析（权重 0.6）+ 声学分析（权重 0.4）加权融合：
- 两者都有 → 加权融合取最高分心情
- 仅声学（文字识别失败）→ 使用声学结果
- 仅文本 → 使用文本结果

### 其他语音改进

- 修复录音停止后 UI 卡死（竞态条件 + 跨线程回调）
- 麦克风权限一键重置对话框
- 识别后自动保存开关（偏好持久化）
- 网页端复用单一 `SpeechRecognition` 对象，避免重复弹授权提示
- `mood_web.html` 融合文本+声学结果，扩展心情关键词

## 📦 完整变更清单

### 新增文件
- `web_server.py`：语音录音/识别后端 API
- `RELEASE_v2.7.0.md`：本发布文档

### 修改文件
- `wiki_app.py`：Tkinter → PySide6 全量重写
- `voice_mood.py`：新增声学分析、调试日志、竞态修复
- `voice-controller.js`：Web Audio API 声学分析、麦克风流复用
- `mood_web.html`：融合文本+声学结果、关键词扩展
- `MyWiki.app/Contents/MacOS/mywiki`：启动器适配 PySide6
- `MyWiki.app/Contents/Resources/AppIcon.icns`：更新应用图标
- `assets/AppIcon.icns`、`icon.ico`、`icon.png`：更新图标资源
- `README.md`：版本号更新至 v2.7.0

### 依赖
- 新增：`PySide6` (6.11.1)
- 已有：`SpeechRecognition`、`static-ffmpeg`

## ⚡ 升级指南

```bash
# 安装 PySide6 依赖
cd my-wiki
.venv/bin/python -m pip install PySide6

# 启动应用
.venv/bin/python wiki_app.py

# 或通过 macOS App
open MyWiki.app
```

---

### 历史版本参考

- v2.6.0：网页版功能扩展（日记/心情网页版）
- v2.5.0：三端配色对齐 + 录音权限修复
- v2.4.0：UI 主题统一（Apple 风浅/深色设计 token）
