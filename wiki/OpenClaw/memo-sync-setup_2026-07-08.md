# Memo 联动设置

**时间**: 2026-07-08 00:22 GMT+8

## 背景
用户要求将 OpenClaw workspace 与本地 Memo (MemoAI) 应用联动。

## Memo 应用架构
- **应用**: /Applications/Memo.app (Electron 应用)
- **数据库**: `~/Library/Application Support/Memo/storage/local.db` (SQLite)
- **工作区**: `~/Library/Application Support/Memo/temp/memo/<workspace-uuid>/`
- **端口**: 41122 (realtime-stt 静态服务器), 50712 (Electron 内部)
- **无 REST API**: 数据交互通过 Electron IPC，外部只能直接操作 SQLite

## 数据库结构
- `workspace`: 工作区（默认 MemoAI, uuid=0aea3836-...）
- `doc`: 文档（title, content, localFilename, workspaceId）
- `note`: 笔记/转录（ogFilename, summary, convertResult, filePath）
- `tag` / `doc_tag` / `note_tag`: 标签系统
- `resource`: 资源文件
- `download`: 下载记录
- `folder`: 文件夹

## 联动方案

### 脚本: `~/.qclaw/workspace/memo_sync.py`

#### 功能
1. **push**: 将 Markdown 文件推送到 Memo doc 表
2. **push-dir**: 批量推送目录下所有匹配文件
3. **pull**: 从 Memo 拉取文档到 workspace
4. **list**: 列出 Memo 中的文档和笔记
5. **search**: 搜索 Memo 内容

#### 用法
```bash
python3 ~/.qclaw/workspace/memo_sync.py push <file.md> [--title "标题"]
python3 ~/.qclaw/workspace/memo_sync.py push-dir <directory> [--pattern "*.md"]
python3 ~/.qclaw/workspace/memo_sync.py pull [--limit 10]
python3 ~/.qclaw/workspace/memo_sync.py list [--limit 20]
python3 ~/.qclaw/workspace/memo_sync.py search <keyword>
```

### 定时任务
- **Cron**: `memo-sync-push` 每天 22:00 Asia/Shanghai
  - 推送当天和前一天的日记 + 分析报告到 Memo
  - sessionTarget: isolated
  - Job ID: 3384c203-27d8-4331-9f5c-2bf81be868b9

## 测试结果
- push 单文件 ✅ (视频分析报告)
- push 单文件 ✅ (Skill创建记录)
- push-dir 批量 ✅ (5个日记文件)
- list ✅ (7个文档)
- search ✅ (搜索"视频"命中2条)

## 初始同步内容
1. `aipmday-analysis_2026-07-07.md` — AI PM 共学营视频分析
2. `video-analysis-skill_2026-07-08.md` — Video Analysis Skill 创建记录
3. `memory/2026-07-02.md` ~ `2026-07-06.md` — 5天日记

## 注意事项
- Memo 应用必须在运行时数据库才能被访问（SQLite WAL 模式）
- 推送的文档会同时保存为文件到 Memo workspace 的 docs/ 目录
- `content` 字段存储文件名而非完整内容（varchar(255) 限制）
- 完整内容保存在文件中: `<workspace>/docs/<localFilename>.md`
