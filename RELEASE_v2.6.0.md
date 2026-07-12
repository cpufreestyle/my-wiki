# MyWiki v2.6.0 — 网页版功能扩展（草稿，待发布）

> 本文件记录 v2.6.0 的变更。核心目标：**把桌面端其余功能也做成网页版**，让提醒 / 日记 / 心情三大功能都能在浏览器里直接使用，且与桌面端共用同一套 Apple 风设计系统。

## 🌐 新特性：桌面功能网页化

- **日记网页版 `daily_web.html`**（对齐桌面 `wiki_app.py` 的「日记」标签 / `daily_ui.py`）
  - 今日日期头、Markdown 编辑区
  - 📝 模板插入（Done / Thoughts / Tomorrow）
  - 🏷 标签提取（复用桌面 `extract_tags` 的停用词表与领域词加权逻辑，纯 JS 移植）
  - 💾 保存（快捷键 Ctrl/Cmd+S）+ 状态栏反馈，演示态持久化到 `localStorage`
- **心情网页版 `mood_web.html`**（对齐桌面 `wiki_app.py` 的「心情」标签）
  - 💭 心情输入框 + 🔍 自动分析（复用桌面 `analyze_mood` 的关键词 / 否定词 / 置信度逻辑，纯 JS 移植）
  - 5 张快捷心情卡（开心 / 平静 / 低落 / 兴奋 / 焦虑，带 emoji）
  - 🎤 语音输入（基于浏览器 Web Speech API，不支持时优雅降级并提示）
  - 今日记录列表 + 识别后自动保存开关（偏好持久化到 `localStorage`）
- **统一体验**：`daily_web.html` / `mood_web.html` 与 `reminder_web.html` 共用同一套设计 token（浅灰 / 深灰背景、白 / 深卡、Apple 蓝强调）、右上角 🌙/☀️ 主题切换、Toast、深色模式与全局错误过滤器

## 🛠 工程改进

- **测试覆盖补齐**：原来 `tests/` 仅覆盖 `reminder_web.html`，现新增
  - `tests/test_daily_web.py` / `tests/test_mood_web.py`：结构 / 选择器一致性 + 关键 a11y 属性校验
  - `tests/daily_web.logic.test.mjs`：校验 `extract_tags` 的停用词过滤 / 领域词加权 / `top_n`
  - `tests/mood_web.logic.test.mjs`：校验 `analyze_mood` 的关键词命中 / 否定词处理 / 中性回退
- 全量测试：Python 29 个 + Node 15 个，全部通过

## 📌 仍待办（后续可选）

- **跨端主题真正同步**：目前桌面三端共享 `config/theme_pref.txt`，网页端仍用 `localStorage`；可让网页端也回写同一偏好，实现四端一致
- **网页端数据真正落地**：当前网页版在无后端时回退 `localStorage` 演示态；如需与桌面 `daily/*.md`、`mood/*.json` 共享，需提供 `/api/daily`、`/api/mood` 后端
- **RAG 增量更新**：`MYWIKI_RAG_MODE=ollama` 已验证生成向量索引，目前为全量 `--rebuild`

## 📦 完整变更

- 新增 `daily_web.html`：日记网页版
- 新增 `mood_web.html`：心情网页版
- 新增 `tests/test_daily_web.py`、`tests/test_mood_web.py`
- 新增 `tests/daily_web.logic.test.mjs`、`tests/mood_web.logic.test.mjs`
- 更新 `README.md`：文件树 / 主题统一章节 / 测试章节纳入两个新网页版

---

### 起草基线（v2.5.0 现状参考）

- 主窗口 `wiki_app.py` 已接入 `theme.py` 并支持浅/深色切换
- `reminder_web.html` 已有结构 + 日期逻辑单测与 GitHub Actions CI
- Ollama embedding 模式（nomic-embed-text，768 维）已实跑验证
- 已补充 MIT LICENSE 与 markdownlint 配置
