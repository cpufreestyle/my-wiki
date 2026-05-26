# Deploy Guide / 部署指南

OpenClaw + Obsidian + MyWiki 快速部署教程

---

## Prerequisites / 前置要求

- **Windows 10/11** (64-bit)
- **Obsidian** (free, [obsidian.md](https://obsidian.md))
- **OpenClaw** (AI Agent, [qclaw.com](https://qclaw.com))
- **Python 3.11+** (optional, for source mode)

---

## Step 1: Install Obsidian / 安装 Obsidian

### Windows

1. Go to [obsidian.md/download](https://obsidian.md)
2. Download Windows installer / 下载 Windows 安装包
3. Run installer, follow prompts / 运行安装，按提示操作
4. Launch Obsidian / 启动 Obsidian

### Create Your Vault / 创建 Vault

1. Click **"Create new vault"** / 点击 **"Create new vault"**
2. Set vault name: `MyWiki` / 名称设为 `MyWiki`
3. Choose location: `D:\MyWiki` (or any path you like)
   - 推荐放在非系统盘，如 `D:\` 或 `E:\`
4. Click **Create** / 点击 **Create**

---

## Step 2: Install OpenClaw / 安装 OpenClaw

### Option A: Official Installer / 官方安装包

1. Go to [qclaw.com](https://qclaw.com) or download page
2. Download Windows installer (`.exe` or `.msi`)
3. Run installer / 运行安装
4. OpenClaw Gateway starts automatically / Gateway 自动启动

### Option B: Manual Install / 手动安装

```powershell
# Install via npm (requires Node.js 18+)
npm install -g openclaw

# Start gateway
openclaw gateway start
```

### Verify / 验证

```powershell
openclaw gateway status
# Should show: running / 应显示 running
```

### Connect to AI / 连接 AI

1. OpenClaw config file: `C:\Users\<YourName>\.qclaw\openclaw.json`
2. Configure your LLM provider (OpenAI, Anthropic, etc.)
3. Set your API key
4. Restart gateway: `openclaw gateway restart`

---

## Step 3: Setup MyWiki / 配置 MyWiki

### Download Pre-built App / 下载编译版

1. Go to [GitHub Releases](https://github.com/cpufreestyle/my-wiki/releases/latest)
2. Download `MyWiki.exe`
3. Place anywhere you like (e.g. `D:\MyWiki\MyWiki.exe`)
4. Double-click to run / 双击运行

### Or Run from Source / 或源码运行

```powershell
# Clone the repo
git clone https://github.com/cpufreestyle/my-wiki.git
cd my-wiki

# Install dependencies
pip install Pillow pywin32

# Run
python wiki_app.py
```

### Initialize Wiki Structure / 初始化目录结构

```
MyWiki/
├── daily/           ← Diary files / 日记
├── mood/            ← Mood data / 心情
├── reminders/       ← Reminders / 提醒
├── concepts/        ← Knowledge notes / 知识笔记
├── projects/        ← Project notes / 项目笔记
└── scripts/         ← Helper scripts / 辅助脚本
```

---

## Step 4: Connect OpenClaw to Your Vault / 连接 OpenClaw 和 Vault

### Tell OpenClaw Your Wiki Path

In OpenClaw chat, say:
在 OpenClaw 聊天中输入：

> "我的 Obsidian Vault 在 D:\MyWiki，日记在 daily/ 目录下，心情数据在 mood/ 目录下"

OpenClaw will remember this and can directly read/write your vault files.
OpenClaw 会记住这个路径，之后可以直接读写你的 Vault 文件。

### Test the Connection / 测试连接

> "打开今天的日记" / "Open today's diary"

If OpenClaw reads the file successfully, everything is connected ✅
如果 OpenClaw 成功读取了文件，说明连接正常 ✅

---

## Step 5: Open Vault in Obsidian / 在 Obsidian 中打开 Vault

1. Open Obsidian / 打开 Obsidian
2. Click **"Open folder as vault"** / 点击 **"Open folder as vault"**
3. Select `D:\MyWiki` / 选择 `D:\MyWiki`
4. All `.md` files appear in Obsidian / 所有 Markdown 文件立即可见

### (Optional) Install Recommended Plugins / (可选) 安装推荐插件

In Obsidian Settings → Community Plugins / 设置 → 社区插件：

| Plugin | Purpose | 推荐 |
|--------|---------|------|
| **Daily Notes** | Quick daily note creation | ⭐⭐⭐ |
| **Calendar** | Navigate daily notes by date | ⭐⭐⭐ |
| **Local REST API** | Let OpenClaw control Obsidian | ⭐⭐ |
| **Graph View** | Visualize note connections | ⭐⭐ |
| **Tag Wrangler** | Manage tags easily | ⭐ |

---

## Step 6: Set Up WeChat Notifications / 配置微信通知 (Optional)

If you want diary reminders and weekly summaries sent to WeChat:
如果你想在微信收到日记提醒和周报：

### Configure WeChat Channel in OpenClaw

1. Open OpenClaw config: `C:\Users\<YourName>\.qclaw\openclaw.json`
2. Add WeChat channel configuration
3. Restart gateway: `openclaw gateway restart`

### Cron Jobs / 定时任务

After setup, OpenClaw will automatically:
配置完成后，OpenClaw 会自动：

| Time | Action |
|------|--------|
| **Every day 18:00** | Send diary reminder to WeChat / 发送日记提醒 |
| **Every Sunday 20:00** | Send weekly summary to WeChat / 发送周报 |

---

## Quick Start Checklist / 快速启动清单

```
□ Obsidian installed                    □ Obsidian 已安装
□ Vault created at D:\MyWiki           □ Vault 已创建
□ OpenClaw installed and running       □ OpenClaw 已安装运行
□ AI provider configured               □ AI 服务已配置
□ MyWiki.exe downloaded or source run  □ MyWiki.exe 已下载或源码运行
□ Wiki path told to OpenClaw           □ Wiki 路径已告诉 OpenClaw
□ Test: open today's diary             □ 测试：打开今天日记
□ WeChat channel configured (opt.)     □ 微信通道已配置（可选）
□ Daily reminder active (opt.)         □ 每日提醒已启用（可选）
□ Weekly summary active (opt.)         □ 周报已启用（可选）
```

---

## Folder Structure After Setup / 部署后的目录结构

```
D:\MyWiki\                          ← Obsidian Vault
├── .obsidian\                      ← Obsidian config (auto-created)
├── daily\                          ← Daily diaries
│   ├── 2026-05-26.md
│   └── weekly-summary-2026-05-26.md
├── mood\                           ← Mood tracking
│   └── 2026-05-26.json
├── reminders\                      ← Reminder system
│   ├── reminders.json
│   └── pending_notifications.json
├── concepts\                       ← Knowledge base
├── projects\                       ← Project notes
├── scripts\                        ← Helper scripts
├── icon.ico                        ← App icon
└── wiki_app.py                     ← Main GUI (if source mode)

C:\Users\<You>\.qclaw\              ← OpenClaw config
└── openclaw.json                   ← Main config file
```

---

## Daily Workflow / 日常使用流程

```
Morning / 早上
  └─ Obsidian → Daily Notes → Write morning thoughts

Daytime / 白天
  └─ Talk to OpenClaw (WeChat/Web) → "记一下..." → Auto-saves to vault

Evening 18:00 / 晚上
  └─ WeChat reminder → "记得写日记 📝"
  └─ You tell OpenClaw → Diary written
  └─ Obsidian instantly shows the new entry

Sunday 20:00 / 周日
  └─ WeChat weekly summary → Review your week
  └─ Summary saved to vault
```

---

## Troubleshooting / 常见问题

| Problem | Solution |
|---------|----------|
| OpenClaw gateway won't start | Run `openclaw gateway status` to check, then `openclaw gateway start` |
| Obsidian can't find vault | Make sure path matches exactly / 确保路径完全匹配 |
| Can't connect to AI | Check API key in `openclaw.json` / 检查 API Key |
| WeChat not receiving | Check channel config in `openclaw.json` / 检查通道配置 |
| MyWiki.exe won't open | May need to install [VC++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) |
| File encoding issues | OpenClaw writes UTF-8, Obsidian reads UTF-8 — should work out of the box |

---

## Useful Links / 有用链接

- **Obsidian**: [obsidian.md](https://obsidian.md)
- **Obsidian Help**: [help.obsidian.md](https://help.obsidian.md)
- **MyWiki GitHub**: [github.com/cpufreestyle/my-wiki](https://github.com/cpufreestyle/my-wiki)
- **OpenClaw**: [qclaw.com](https://qclaw.com)
