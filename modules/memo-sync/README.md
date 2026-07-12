# Memo Sync 模块

将 OpenClaw workspace 内容与本地 Memo (MemoAI) 应用双向同步。

## 依赖

- **Memo 应用**: macOS Electron 应用（MemoAI）
- **Python 3**: sqlite3 内置模块

## Memo 数据架构

- **数据库**: `~/Library/Application Support/Memo/storage/local.db` (SQLite)
- **工作区**: `~/Library/Application Support/Memo/temp/memo/<workspace-uuid>/`
- **表**: `doc`, `note`, `tag`, `folder`, `resource`, `download`
- **无 REST API**: 通过 Electron IPC 交互，外部直接操作 SQLite

## 使用

```bash
# 通过 wiki_tool.py
python wiki_tool.py memo-push <file.md> [--title "标题"]
python wiki_tool.py memo-list
python wiki_tool.py memo-search <keyword>
python wiki_tool.py memo-pull

# 直接调用
python modules/memo-sync/sync.py push <file.md> [--title "标题"]
python modules/memo-sync/sync.py list
python modules/memo-sync/sync.py search <keyword>
python modules/memo-sync/sync.py pull
```

## 功能

| 命令 | 说明 |
|:---|:---|
| `push` | 推送 Markdown 文件到 Memo doc 表 |
| `push-dir` | 批量推送目录下所有匹配文件 |
| `pull` | 从 Memo 拉取文档到 wiki |
| `list` | 列出 Memo 中的文档和笔记 |
| `search` | 搜索 Memo 内容 |

## 定时同步

通过 OpenClaw cron 每天 22:00 自动推送当日日记和报告到 Memo。

## 文件

- `sync.py`: 核心同步脚本
- `README.md`: 本文件
