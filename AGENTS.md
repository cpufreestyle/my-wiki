# AGENTS.md — MyWiki Agent Guide

## 项目概述

**MyWiki** — Personal Knowledge Wiki

MyWiki 是一个个人知识管理系统，同时作为多个 AI Agent 的共享知识中枢。它提供：

- Markdown 笔记管理（日记、项目、概念、人物）
- Obsidian Vault 双向同步
- MCP 协议暴露，供各类 AI Agent 读写
- RSS 聚合、RAG 语义检索、知识图谱可视化
- 视频分析、Memo 同步等扩展模块

## 不可变目录（只读）

以下目录包含用户内容，**Agent 不得修改、创建或删除其中的文件**：

| 目录 | 说明 |
|------|------|
| `brain/` | 知识库核心内容（概念、日记、项目、人物等） |
| `daily/` | 每日笔记与 RSS 聚合结果 |
| `wiki/` | Obsidian Vault 数据（含 `.obsidian/` 配置） |

这些目录的内容由用户通过 Obsidian 或同步模块管理，Agent 仅可**读取**，不可写入。

## Python 代码约定

- **Python 版本**: 3.10+
- **编码**: UTF-8
- **风格**: 遵循 PEP 8，使用 4 空格缩进
- **依赖管理**: `requirements.txt`（通过 `pip install -r requirements.txt` 安装）
- **模块导入**: 使用相对路径或 `sys.path.insert` 引入 `modules/` 下的子模块
- **Frontmatter**: Markdown 文件使用 YAML frontmatter（需 `pyyaml`）
- **命令行入口**: 统一通过 `wiki_tool.py` 提供子命令
- **注释与文档**: 函数和模块需有 docstring，中文注释

## 测试命令

```bash
python tests/run_all.py
```

测试文件位于 `tests/` 目录，包含：

- `test_daily_web.py` — 日记 Web 逻辑测试
- `test_graph_web.py` — 知识图谱 Web 测试
- `test_index.py` — 索引测试
- `test_mood_web.py` — 情绪分析 Web 测试
- `test_rag_web.py` — RAG Web 测试
- `test_reminder_web.py` — 提醒 Web 测试
- `daily_web.logic.test.mjs` / `mood_web.logic.test.mjs` / `reminder_web.logic.test.mjs` — JS 端逻辑测试

## 模块边界说明

所有扩展模块位于 `modules/` 目录下，各子模块职责独立：

### `modules/shared-wiki/`
**共享知识内核**。提供 Wiki 读写 API（`wiki_core.py`）、Agent 自动发现（`agent_registry.py`）、Obsidian 桥接（`obsidian_bridge.py`）和 MCP Server（`mcp_server.py`）。这是所有 Agent 访问 Wiki 的统一入口。

### `modules/memo-sync/`
**Memo 双向同步**。将本地 Markdown 与 MemoAI 应用的 SQLite 数据库双向同步，支持 push / pull / list / search 操作。

### `modules/obsidian-sync/`
**Obsidian Vault 同步**。将 Wiki 内容同步到外部 Obsidian Vault（如 `~/Documents/Obsidian Vault/`），按目录映射保持一致，冲突时本地优先。

### `modules/a2a-agent/`
**A2A Agent 网络**。Google Agent-to-Agent 协议的本地节点，提供中央编排、本地推理、嵌入、3D 渲染等 Agent 的互联。项目代码不在本仓库内，此模块仅作文档索引。

### `modules/video-analysis/`
**视频分析**。通过 FFmpeg 提取关键帧，送入 Vision 模型逐帧分析，生成结构化 Markdown 报告并保存到 `daily/`。

### `modules/skills-loader/`
**技能加载器**。统一发现、查询、调用分布在 `~/AI Shared/skills` 下的各类 Agent 技能，提供 `list` / `show` / `run` 命令。
