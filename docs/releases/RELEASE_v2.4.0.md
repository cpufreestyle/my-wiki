# MyWiki v2.4.0 — UI 主题统一（Apple 风浅 / 深色设计 token）🎨

本次更新将 MyWiki 多个界面的视觉风格统一为一套 Apple 风设计 token，并支持浅色 / 深色主题。

## ✨ 新特性

- **统一设计 token**：新增 `theme.py`，集中管理颜色 / 字体 / 圆角 / 阴影等设计变量，`reminder_web.html` / `reminder_ui.py` / `daily_ui.py` 三个界面共用同一套值，改一处即可整体换肤
- **浅色 / 深色主题**：Web 端 `reminder_web.html` 支持一键切换深色模式（偏好持久化到 `localStorage`）；桌面端 UI 同步适配统一 token
- **Figma 设计规格**：新增 `FIGMA_DESIGN_SPEC.md`，沉淀界面设计稿与规范，便于后续迭代与协作

## 🛠 使用方式

- **Web 端**：打开 `reminder_web.html`，点击右上角 🌙/☀️ 切换深 / 浅色主题，偏好自动记忆
- **换肤**：修改 `theme.py` 中的 `LIGHT` / `DARK` 字典即可整体调整配色
- **主题偏好（桌面端）**：存储在 `config/theme_pref.txt`（`light` / `dark`）

## 📦 完整变更

- `theme.py`（新增）：统一设计 token（Apple 风浅 / 深色）
- `daily_ui.py` / `reminder_ui.py`：适配统一主题
- `config/theme_pref.txt`（新增）：主题偏好存储
- `FIGMA_DESIGN_SPEC.md`（新增）：Figma 设计规格文档
- `reminder_web.html`：新增深色模式切换与全局错误过滤
- `.gitignore`：忽略 `generated-images/`、`wiki/.rag_index.json`

> 注：v2.3.0 的语义 RAG 检索引擎（BM25 / 可选 Ollama embedding）已包含在本版本之前的提交中。
