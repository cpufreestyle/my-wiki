# MyWiki v2.8.0 — 稳定性、兼容性与工程化增强

> 本文件记录 v2.7.0 之后的累计修复与增强。本次为**维护性增强版本**：修复了 wiki-root 解析错误、Obsidian 检测在多盘符下的失效、网页卡片布局塌陷等问题，并补齐桌面端 CI 冒烟测试与可调 UI 偏好。

## 🐛 关键修复

- **wiki-root 解析修正**：`WIKI_DIR` 此前会解析到不存在的幻影目录；统一各模块（wiki_core / reminder / rag / web_server）的 wiki-root 解析逻辑，并对齐 Obsidian vault 实际位置（`31dad3b`、`5c0f729`）
- **Obsidian 检测兼容多盘符**：改用注册表反查真实安装路径，兼容安装在 `D:` 盘 / `Programs` 目录的情况（`8ace38b`）
- **网页卡片高度塌陷修复**：修复 `mood_web.html` / `reminder_web.html` / `daily_web.html` 中卡片高度塌缩问题，并支持手动拖拽调节卡片高度（`c222681`、`mood_web.html +60`、`reminder_web.html +48`、`daily_web.html +60`）
- **桌面端按钮样式修正**：修正 PySide6 桌面端按钮文字颜色/字号异常（`3726d6f`）
- **清理误提交文件**：移除误提交的非法路径文件与冗余 build/dist 产物（`72814cb`）

## 🎨 增强

- **可调 UI 偏好**：`theme.py` 新增 `load_ui_prefs` / `save_ui_prefs`，支持卡片行间距、内边距、卡片间距、标题/副文案字号、心情卡片高度等参数持久化到 `config/ui_pref.json`（默认值对齐网页端 `--card-h` 52px）
- **依赖声明补全**：`requirements.txt` 正式声明桌面 GUI 依赖 `PySide6>=6.5.0`，明确可用 PyQt6 替代
- **全新首页**：新增 `index.html` 项目入口页

## 🧪 工程化 / CI

- **桌面端冒烟测试接入 CI**：`.github/workflows/ci.yml` 新增 PySide6 安装与无头（`QT_QPA_PLATFORM=offscreen`）启动冒烟测试 `scripts/smoke_desktop_qt.py`，覆盖 macOS/Linux 桌面端可启动性（`3726d6f`）
- **测试扩充**：新增 `tests/test_index.py`、`tests/run_all.py`，并扩充 `test_reminder_web.py` / `test_mood_web.py` / `test_daily_web.py`

## 📦 完整变更清单

### 新增文件

- `index.html`：项目入口页
- `scripts/smoke_desktop_qt.py`：PySide6 桌面端无头冒烟测试
- `tests/test_index.py`、`tests/run_all.py`：索引测试与统一测试入口
- `config/ui_pref.json`：UI 偏好持久化文件
- `RELEASE_v2.8.0.md`：本发布文档

### 修改文件

- `theme.py`：新增 UI 偏好读取/写入（`load_ui_prefs` / `save_ui_prefs`）
- `requirements.txt`：声明 `PySide6>=6.5.0`
- `.github/workflows/ci.yml`：新增桌面端 PySide6 冒烟测试
- `wiki_app.py`：按钮样式修正（+701 行重构/调整）
- `mood_web.html` / `reminder_web.html` / `daily_web.html`：卡片高度塌陷修复 + 手动调节
- `modules/shared-wiki/wiki_core.py` / `rag.py` / `wiki_tool.py` / `modules/video-analysis/analyze.py`：wiki-root 解析对齐
- `README.md`：版本号更新至 v2.8.0
- 图标资源（`AppIcon.icns` / `icon.ico` / `icon.png` / `assets/AppIcon.source.png`）：更新

## ⚡ 升级指南

```bash
# 安装桌面端依赖（若尚未安装）
cd my-wiki
python -m pip install -r requirements.txt

# 启动应用
python wiki_app.py

# 或通过 macOS App
open MyWiki.app
```

---

### 历史版本参考

- v2.7.0：PySide6 迁移 + 语音声学分析增强
- v2.6.0：网页版功能扩展（日记/心情网页版）
- v2.5.0：三端配色对齐 + 录音权限修复
- v2.4.0：UI 主题统一（Apple 风浅/深色设计 token）
