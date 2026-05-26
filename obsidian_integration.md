# Obsidian + OpenClaw Integration / Obsidian 与 OpenClaw 联动指南

OpenClaw (龙虾) can directly read, create, and edit Markdown files in your Obsidian vault — giving you an AI-powered second brain.
OpenClaw (龙虾) 可以直接读取、创建和编辑 Obsidian Vault 中的 Markdown 文件，打造 AI 驱动的第二大脑。

---

## How It Works / 工作原理

```
┌─────────────┐     Markdown Files     ┌─────────────┐
│   OpenClaw   │ ◄────────────────────► │   Obsidian   │
│  (AI Agent)  │   D:\Users\michael\    │   (Vault)    │
│              │      MyWiki\           │              │
└─────────────┘                        └─────────────┘
```

- Obsidian manages and displays the Markdown files / Obsidian 管理和展示 Markdown 文件
- OpenClaw can read, write, search, and analyze those files / OpenClaw 可以读写、搜索、分析这些文件
- They share the same folder — no sync needed / 共享同一文件夹，无需同步

---

## Setup / 配置步骤

### Step 1: Open Vault in Obsidian / 在 Obsidian 中打开 Vault

1. Open Obsidian / 打开 Obsidian
2. Click **Open folder as vault** / 点击 **Open folder as vault**
3. Select `D:\Users\michael\MyWiki` / 选择 `D:\Users\michael\MyWiki`
4. Done! All notes are now visible / 完成！所有笔记立即可见

### Step 2: Verify the Connection / 验证连接

Ask OpenClaw in chat:
在聊天中告诉 OpenClaw：

> "打开今天的日记" / "Open today's diary"

OpenClaw will read `D:\Users\michael\MyWiki\daily\YYYY-MM-DD.md` directly.
OpenClaw 会直接读取日记文件。

---

## What You Can Do / 你能做什么

### 1. Write Diary via Voice / 语音写日记

Speak or type to OpenClaw:
对 OpenClaw 说话或打字：

> "记录一下今天的日记：今天去宝山万达看了现场演出，很开心" / "Write my diary: went to Baoshan Wanda, great live music today"

OpenClaw will:
- Create/update the diary file / 创建或更新日记文件
- Auto-extract tags / 自动提取标签
- Save to `daily/YYYY-MM-DD.md` / 保存到当天日记

### 2. Search Notes / 搜索笔记

> "搜索我之前写的关于股票的笔记" / "Find my notes about stocks"

OpenClaw searches all `.md` files and returns relevant content.
OpenClaw 搜索所有 Markdown 文件并返回相关内容。

### 3. Ask Questions About Your Notes / 对笔记提问

> "我上周的心情怎么样？" / "How was my mood last week?"

OpenClaw reads mood data and diary entries to answer.
OpenClaw 读取心情数据和日记来回答。

### 4. Create New Notes / 创建新笔记

> "创建一个关于学习计划的笔记" / "Create a note about my study plan"

OpenClaw creates the Markdown file with proper structure.
OpenClaw 创建结构完整的 Markdown 文件。

### 5. Edit Existing Notes / 编辑已有笔记

> "在今天的日记里加上晚上要去健身" / "Add 'going to gym tonight' to today's diary"

OpenClaw edits the file directly, changes appear in Obsidian immediately.
OpenClaw 直接编辑文件，Obsidian 中立即生效。

### 6. Open Note in Obsidian / 在 Obsidian 中打开笔记

> "用 Obsidian 打开今天的日记" / "Open today's diary in Obsidian"

OpenClaw sends the URI command:
OpenClaw 发送 URI 命令：

```powershell
Start-Process "obsidian://open?vault=MyWiki&file=daily/2026-05-26"
```

---

## Daily Reminder Integration / 每日提醒联动

A cron job sends a WeChat reminder at 18:00 every day:
每天 18:00 自动发送微信提醒：

1. **WeChat notification**: "记得写日记 📝"
2. **Auto-create diary file** if not exists
3. You reply to OpenClaw with voice/text → diary is written
4. The diary immediately shows up in Obsidian

```
18:00 → WeChat reminds you → You tell OpenClaw → Diary saved → Visible in Obsidian
18:00 → 微信提醒你 → 你告诉 OpenClaw → 日记保存 → Obsidian 立即可见
```

---

## File Locations / 文件位置

| Path | Description | Obsidian |
|------|-------------|----------|
| `daily/YYYY-MM-DD.md` | Daily diary / 每日日记 | ✅ Visible |
| `mood/YYYY-MM-DD.json` | Mood data / 心情数据 | ❌ JSON |
| `reminders/reminders.json` | Reminder list / 提醒列表 | ❌ JSON |
| `concepts/*.md` | Knowledge notes / 知识笔记 | ✅ Visible |
| `projects/*.md` | Project notes / 项目笔记 | ✅ Visible |

Only `.md` files appear in Obsidian. JSON files are managed by OpenClaw in the background.
只有 `.md` 文件在 Obsidian 中可见。JSON 文件由 OpenClaw 后台管理。

---

## Tips / 小贴士

- **Real-time sync**: Changes by OpenClaw appear in Obsidian instantly (no refresh needed)
  实时同步：OpenClaw 的修改在 Obsidian 中即时生效
- **No cloud needed**: Everything is local, fully private
  无需云端：全部本地存储，完全私密
- **Backup**: Your vault is at `D:\Users\michael\MyWiki`, back it up as any folder
  备份：Vault 在 `D:\Users\michael\MyWiki`，像普通文件夹一样备份
- **Templates**: Ask OpenClaw to create templates for recurring note types
  模板：让 OpenClaw 为常用笔记类型创建模板
- **Graph View**: Open Obsidian's Graph View to see connections between your notes
  关系图：打开 Obsidian 的 Graph View 查看笔记之间的关联

---

## Example Commands / 示例命令

| You say / 你说 | OpenClaw does / OpenClaw 做 |
|----------------|---------------------------|
| "写日记：今天..." | Creates diary entry / 创建日记 |
| "搜索关于XX的笔记" | Searches all notes / 搜索笔记 |
| "总结本周日记" | Reads & summarizes / 读取并总结 |
| "在Obsidian里打开XX" | Opens via URI / URI 打开 |
| "创建学习笔记：React Hooks" | Creates concept note / 创建知识笔记 |
| "我最近心情怎么样" | Analyzes mood data / 分析心情 |
| "加个提醒明天下午3点开会" | Creates Windows scheduled task / 创建计划任务 |
| "给日记打标签" | Auto-extracts tags / 自动提取标签 |

---

## Architecture / 架构

```
WeChat (微信)
    │
    ▼
OpenClaw (龙虾 AI Agent)
    │
    ├── Read/Write ──► D:\Users\michael\MyWiki\
    │                      ├── daily/      ◄── Obsidian Vault
    │                      ├── mood/
    │                      ├── concepts/
    │                      ├── projects/
    │                      └── reminders/
    │
    ├── URI Command ──► obsidian://open?vault=MyWiki&file=...
    │
    └── Windows Tasks ──► Reminder notifications
```

---

## Troubleshooting / 故障排除

| Problem | Solution |
|---------|----------|
| Obsidian can't find vault | Make sure vault name is **MyWiki** / 确保仓库名为 MyWiki |
| URI doesn't work | Check `obsidian://open?vault=MyWiki` format / 检查 URI 格式 |
| File not showing in Obsidian | File must be `.md` extension / 文件必须是 `.md` 格式 |
| Encoding issues | OpenClaw writes UTF-8, same as Obsidian default / OpenClaw 写 UTF-8 |
