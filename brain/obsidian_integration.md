---
type: note
title: Obsidian_Integration
date: '2026-07-01T00:00:00.000Z'
---

# Obsidian + OpenClaw Integration / Obsidian 与 OpenClaw 联动指南

OpenClaw (龙虾) can directly read, create, and edit Markdown files in your Obsidian vault — giving you an AI-powered second brain.
OpenClaw (龙虾) 可以直接读取、创建和编辑 Obsidian Vault 中的 Markdown 文件，打造 AI 驱动的第二大脑。

---

## How It Works / 工作原理

```
┌─────────────┐     Markdown Files     ┌─────────────┐
│   OpenClaw   │ ◄────────────────────► │   Obsidian   │
│  (AI Agent)  │   Vault Folder         │   (Vault)    │
│              │                        │              │
└─────────────┘                        └─────────────┘
```

- Obsidian manages and displays the Markdown files / Obsidian 管理和展示 Markdown 文件
- OpenClaw can read, write, search, and analyze those files / OpenClaw 可以读写、搜索、分析这些文件
- They share the same folder — no sync needed / 共享同一文件夹，无需同步

---

## Setup / 配置步骤

### macOS Setup / macOS 配置

1. Open Obsidian / 打开 Obsidian
2. Click **Open folder as vault** / 点击 **Open folder as vault**
3. Select your wiki folder:
   - Default: `~/.qclaw/workspace/wiki`
   - Or: `/path/to/my-wiki`
4. Done! All notes are now visible / 完成！所有笔记立即可见

**Run Mac setup script / 运行 Mac 设置脚本:**
```bash
cd /path/to/my-wiki
./scripts/setup-mac.sh
```

### Windows Setup / Windows 配置

1. Open Obsidian / 打开 Obsidian
2. Click **Open folder as vault** / 点击 **Open folder as vault**
3. Select `D:\Users\michael\MyWiki` / 选择 `D:\Users\michael\MyWiki`
4. Done! All notes are now visible / 完成！所有笔记立即可见

### Step 2: Name Your Vault / 命名你的 Vault

⚠️ **重要**: When opening the folder in Obsidian, you need to give the vault a name. Remember this name for URI commands.
⚠️ **重要**: 在 Obsidian 中打开文件夹时，需要给 vault 起个名字。记住这个名字用于 URI 命令。

**Recommended vault names / 推荐的 vault 名称:**
- `my-wiki` (推荐)
- `wiki`
- `knowledge-base`

### Step 3: Verify the Connection / 验证连接

Ask OpenClaw in chat:
在聊天中告诉 OpenClaw：

> "打开今天的日记" / "Open today's diary"

OpenClaw will read the diary file directly.
OpenClaw 会直接读取日记文件。

**macOS path / macOS 路径:** `~/.qclaw/workspace/wiki/daily/YYYY-MM-DD.md`
**Windows path / Windows 路径:** `D:\Users\michael\MyWiki\daily\YYYY-MM-DD.md`

### Step 4: Test Obsidian URI / 测试 Obsidian URI

To open a note in Obsidian via URI:
通过 URI 在 Obsidian 中打开笔记：

**macOS:**
```bash
# Replace <vault-name> with your actual vault name
# 将 <vault-name> 替换为你的实际 vault 名称
open "obsidian://open?vault=<vault-name>&file=daily/2026-05-22"
```

**If you see "Unable to find a vault" error:**
**如果看到 "Unable to find a vault" 错误：**
- Check `HOW-TO-FIND-VAULT-NAME.md` for troubleshooting
- 查看 `HOW-TO-FIND-VAULT-NAME.md` 了解故障排除

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

**macOS:**
```bash
# Make sure to replace <vault-name> with your actual vault name
# 确保将 <vault-name> 替换为你的实际 vault 名称
open "obsidian://open?vault=<vault-name>&file=daily/2026-06-30"
```

**Windows:**
```powershell
Start-Process "obsidian://open?vault=<vault-name>&file=daily/2026-06-30"
```

**⚠️ Important: Vault Name / 重要：Vault 名称**
- The `<vault-name>` must match exactly what you named your vault in Obsidian
- `<vault-name>` 必须与你在 Obsidian 中命名的 vault 完全一致
- If you see "Unable to find a vault" error, check `HOW-TO-FIND-VAULT-NAME.md`
- 如果看到 "Unable to find a vault" 错误，查看 `HOW-TO-FIND-VAULT-NAME.md`

**Alternative: Use Quick Switcher / 替代方法：使用快速切换器**
- Press `Cmd+O` (macOS) or `Ctrl+O` (Windows)
- 按 `Cmd+O` (macOS) 或 `Ctrl+O` (Windows)
- Type the file name / 输入文件名
- Press Enter / 按回车

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

## Cross-Platform Paths / 跨平台路径

### macOS
- Wiki folder: `~/.qclaw/workspace/wiki`
- Or: `~/Documents/my-wiki`
- Scripts: `python3 scripts/script_name.py`

### Windows
- Wiki folder: `D:\Users\michael\MyWiki`
- Scripts: `python scripts\script_name.py`

### Path Handling in Scripts / 脚本中的路径处理

All Python scripts use `pathlib.Path` for cross-platform compatibility:
所有 Python 脚本使用 `pathlib.Path` 实现跨平台兼容：

```python
from pathlib import Path

# Works on both macOS and Windows
wiki_root = Path(__file__).parent.parent
daily_folder = wiki_root / "daily"
```

---

## Mac Setup Script / Mac 设置脚本

Use the provided setup script for macOS:
使用提供的 Mac 设置脚本：

```bash
./scripts/setup-mac.sh
```

This script will / 此脚本会：
- Check Python 3 installation / 检查 Python 3 安装
- Install dependencies / 安装依赖
- Make scripts executable / 设置脚本权限
- Add frontmatter to notes / 为笔记添加 frontmatter
- Update wiki index / 更新 wiki 索引

---

## Tips / 小贴士

- **Real-time sync**: Changes by OpenClaw appear in Obsidian instantly (no refresh needed)
  实时同步：OpenClaw 的修改在 Obsidian 中即时生效
- **Cross-platform**: Works on both macOS and Windows
  跨平台：同时支持 macOS 和 Windows
- **No cloud needed**: Everything is local, fully private
  无需云端：全部本地存储，完全私密
- **Backup**: Your vault is a regular folder, back it up as any folder
  备份：Vault 是普通文件夹，像普通文件夹一样备份
- **Templates**: Ask OpenClaw to create templates for recurring note types
  模板：让 OpenClaw 为常用笔记类型创建模板
- **Graph View**: Open Obsidian's Graph View to see connections between your notes
  关系图：打开 Obsidian 的 Graph View 查看笔记之间的关联
- **Frontmatter**: All notes include YAML frontmatter for better Obsidian compatibility
  Frontmatter：所有笔记包含 YAML frontmatter，提升 Obsidian 兼容性

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
| "加个提醒明天下午3点开会" | Creates reminder notification / 创建提醒通知 |
| "给日记打标签" | Auto-extracts tags / 自动提取标签 |

---

## Architecture / 架构

```
WeChat (微信) / Telegram / Webchat
    │
    ▼
OpenClaw (龙虾 AI Agent)
    │
    ├── Read/Write ──► Wiki Folder/
    │                      ├── daily/      ◄── Obsidian Vault
    │                      ├── mood/
    │                      ├── concepts/
    │                      ├── projects/
    │                      └── reminders/
    │
    ├── URI Command ──► obsidian://open?vault=my-wiki&file=...
    │
    └── Cron Jobs ──► Reminder notifications / 提醒通知
```

---

## Troubleshooting / 故障排除

| Problem | Solution |
|---------|----------|
| Obsidian can't find vault | Make sure to select the correct folder / 确保选择正确文件夹 |
| URI doesn't work | Check `obsidian://open?vault=my-wiki` format / 检查 URI 格式 |
| File not showing in Obsidian | File must be `.md` extension / 文件必须是 `.md` 格式 |
| Encoding issues | OpenClaw writes UTF-8, same as Obsidian default / OpenClaw 写 UTF-8 |
| Scripts don't run on Mac | Run `chmod +x scripts/*.py` or use `setup-mac.sh` / 运行 setup-mac.sh |
| Python not found on Mac | Install Python 3: `brew install python3` / 安装 Python 3 |

---

## Obsidian Plugins Recommendation / 推荐 Obsidian 插件

- **Templates**: Create and use note templates / 创建和使用笔记模板
- **Daily Notes**: Quick access to daily notes / 快速访问每日笔记
- **Calendar**: Calendar view for daily notes / 每日笔记的日历视图
- **Dataview**: Query and display data from notes / 查询和显示笔记数据
- **Tag Pane**: Better tag management / 更好的标签管理
- **Outline**: Outline view of current note / 当前笔记的大纲视图

---

## Advanced: Frontmatter / 高级：Frontmatter

All notes now include YAML frontmatter for better Obsidian compatibility:
所有笔记现在包含 YAML frontmatter 以提升 Obsidian 兼容性：

```yaml
---
title: "2026-06-30"
date: 2026-06-30
tags: [daily]
type: daily
---
```

This enables:
- Better sorting and filtering / 更好的排序和过滤
- Dataview queries / Dataview 查询
- Template support / 模板支持
- Obsidian mobile app compatibility / Obsidian 移动端兼容
