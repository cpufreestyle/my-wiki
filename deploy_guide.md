# My Wiki v2.0 部署指南

## 环境要求

- Python 3.10+（推荐 3.13）
- Windows 10/11
- 可选：Obsidian（用于 Markdown 可视化编辑）

## 快速安装

```bash
# 克隆仓库
git clone https://github.com/cpufreestyle/my-wiki.git
cd my-wiki

# 直接运行（无需安装依赖）
python wiki_app.py
```

## 模块说明

| 文件 | 说明 |
|------|------|
| `config.py` | 配置中心（路径、主题、Obsidian 检测）|
| `wiki_app.py` | 主程序（Tkinter GUI）|
| `wiki_tool.py` | 工具函数库 |
| `mood_analyzer.py` | 心情分析器 |
| `tag_extractor.py` | 标签提取器 |
| `reminder_manager.py` | 提醒管理器 |
| `send_reminder.py` | 提醒发送脚本（被任务计划调用）|

## 目录结构

```
my-wiki/
├── config.py           # 配置
├── wiki_app.py         # 主程序
├── wiki_tool.py        # 工具函数
├── mood_analyzer.py    # 心情分析
├── tag_extractor.py    # 标签提取
├── reminder_manager.py # 提醒管理
├── send_reminder.py    # 提醒发送
├── daily/              # 日记
├── mood/               # 心情记录
├── reminders/          # 提醒数据
├── concepts/           # 概念笔记
├── people/             # 人物笔记
├── projects/           # 项目笔记
├── scripts/            # 辅助脚本
└── attachments/        # 附件
```

## LLM 集成

支持本地 Ollama 自动检测：
- 启动 Ollama 服务：`ollama serve`
- 拉取模型：`ollama pull qwen2.5`
- 在日记界面点击「🤖 LLM 分析」即可使用

## PyInstaller 打包

```bash
pip install pyinstaller
pyinstaller MyWiki.spec
# 产物在 dist/MyWiki.exe
```

## 快捷键

- `Ctrl+S` — 保存日记
- `Ctrl+N` — 新建日记（跳转今天）

## 常见问题

**Q: Obsidian 没有检测到？**
A: 确认 Obsidian 安装在以下路径之一：
- `%LOCALAPPDATA%\Obsidian\Obsidian.exe`（winget 安装）
- `%PROGRAMFILES%\Obsidian\Obsidian.exe`

**Q: 提醒不生效？**
A: 检查 Windows 任务计划中是否有 `MyWiki_Reminder_*` 任务。
