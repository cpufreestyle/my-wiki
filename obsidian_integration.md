# Obsidian 集成指南

## 自动检测

My Wiki v2.0 在启动时自动检测 Obsidian 安装路径，支持：

1. **winget 安装**：`%LOCALAPPDATA%\Obsidian\Obsidian.exe`
2. **安装器安装**：`%PROGRAMFILES%\Obsidian\Obsidian.exe`
3. **旧版路径**：`%APPDATA%\..\Local\Obsidian\Obsidian.exe`
4. **注册表检测**：`HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Obsidian`

检测成功后，侧边栏会出现「🔍 打开 Obsidian」按钮。

## 作为 Obsidian Vault 使用

My Wiki 的数据目录可直接作为 Obsidian Vault 打开：

```bash
# 在 Obsidian 中打开仓库
文件 → 打开仓库 → 选择 my-wiki 目录
```

### 推荐设置

1. **附件文件夹**：`attachments`
2. **新建笔记位置**：`daily`
3. **内部链接**：使用相对路径 `[[daily/2026-06-08]]`

## 双向同步

My Wiki 和 Obsidian 可以同时使用同一目录：

| 操作 | My Wiki | Obsidian |
|------|---------|----------|
| 创建日记 | ✅ 自动命名 | ✅ 任意命名 |
| 编辑内容 | ✅ 保存为 .md | ✅ 保存为 .md |
| 查看标签 | ✅ 自动提取 | ✅ tags 属性 |
| 心情记录 | ✅ JSON 存储 | ⚠️ 需刷新 |

## 注意事项

- My Wiki 使用 `YYYY-MM-DD.md` 格式命名日记
- Obsidian 的 `.obsidian/` 配置目录已被 `.gitignore` 排除
- 两个应用不要同时编辑同一文件
