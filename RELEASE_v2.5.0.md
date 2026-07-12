# MyWiki v2.5.0 — 主窗口主题统一 + 测试与 CI 保障 🧪

本次更新把主桌面窗口纳入统一设计系统，并补齐自动化测试与持续集成，提升长期可维护性。

## ✨ 新特性

- **主窗口主题统一**：`wiki_app.py` 接入 `theme.py`，主桌面窗口（Wiki / Daily / Mood 等页签）正式支持浅色 / 深色一键切换，偏好写入 `config/theme_pref.txt`，与 `reminder_ui.py` / `daily_ui.py` / `reminder_web.html` 三个界面实时同步
- **Ollama embedding 实跑验证**：本地运行 `nomic-embed-text`（768 维）成功生成向量索引 `wiki/.rag_index.json`（322 个语义块），确认 `MYWIKI_RAG_MODE=ollama` 走 cosine 语义检索而非 BM25

## 🧪 测试与 CI

- **结构 / 选择器一致性测试**（`tests/test_reminder_web.py`，Python 标准库）：校验脚本每个 `#id` / `.class` 选择器都能命中真实元素、`data-key` 与 `getPresetTime` 分支一致、`aria-modal` / `role` 等 a11y 属性在位——专门防住此前 `getBoundingClientRect` / null 引用一类根因
- **纯日期逻辑测试**（`tests/reminder_web.logic.test.mjs`，Node 内置 test runner）：用 `vm` 沙箱从 HTML 抽取 `getPresetTime` / `computeRemindAt` 运行，不复制逻辑、不改 HTML
- **GitHub Actions CI**（`.github/workflows/ci.yml`）：push / PR 到 `main` 自动跑 Python + Node 测试及 RAG / theme 冒烟检查

## 🛠 工程化

- **MIT LICENSE**：补充开源许可证（README 许可证徽章已指向 `LICENSE`）
- **markdownlint 配置**：新增 `.markdownlint.json`，关闭 MD013 / MD033 / MD036 / MD041 / MD051 等规则，并据此修正 `README.md` 格式

## 📦 完整变更

- `wiki_app.py`：接入 `theme.py`，新增 `apply_theme()` / `toggle_theme()` 与主题切换按钮
- `tests/test_reminder_web.py`（新增）：结构 / 选择器一致性测试
- `tests/reminder_web.logic.test.mjs`（新增）：日期逻辑测试
- `.github/workflows/ci.yml`（新增）：持续集成工作流
- `LICENSE`（新增）：MIT 许可证
- `.markdownlint.json`（新增）：markdownlint 配置
- `README.md`：新增「测试 & CI」章节，按 markdownlint 修正格式

> 注：v2.4.0 已统一 `reminder_ui` / `daily_ui` / `reminder_web` 三端主题；v2.5.0 将其补齐到主窗口并加上测试 / CI 护栏。
