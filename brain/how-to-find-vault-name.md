---
type: note
title: 如何找到 Obsidian Vault 名称
---

# 如何找到 Obsidian Vault 名称

## 问题：Unable to find a vault for the URL

当你看到这个错误时，说明 URI 中的 vault 名称不正确。

## 解决方案

### 步骤 1: 在 Obsidian 中打开 wiki 文件夹

1. 打开 Obsidian
2. 点击左下角的 **"Open another vault"** (打开其他仓库)
3. 选择 **"Open folder as vault"** (打开文件夹作为仓库)
4. 导航到 `~/.qclaw/workspace/wiki`
5. 点击 **"Select folder"** (选择文件夹)
6. 给 vault 起一个名字，例如：
   - `my-wiki`
   - `wiki`
   - `MyWiki`
   - 或任何你喜欢的名字

### 步骤 2: 获取正确的 Vault 名称

**方法 1: 从 Obsidian 界面**
- 打开 vault 后，左下角会显示 vault 名称

**方法 2: 从配置文件**
```bash
cat ~/Library/Application\ Support/obsidian/obsidian.json
```

**方法 3: 使用命令行**
```bash
# 运行这个脚本生成正确的 URI
python3 scripts/generate_obsidian_uri.py <vault名称> <文件路径>
```

### 步骤 3: 使用正确的 URI

假设你的 vault 名称是 `my-wiki`，要打开 `daily/2026-05-22.md`：

**macOS 命令：**
```bash
open "obsidian://open?vault=my-wiki&file=daily/2026-05-22"
```

**在 Obsidian 中直接打开：**
- 使用 Quick Switcher（Cmd+O）
- 输入文件名 `2026-05-22`
- 按回车

## 示例

### 如果 vault 名称是 `my-wiki`：
```bash
open "obsidian://open?vault=my-wiki&file=daily/2026-05-22"
```

### 如果 vault 名称是 `wiki`：
```bash
open "obsidian://open?vault=wiki&file=daily/2026-05-22"
```

### 如果 vault 名称包含空格，需要 URL 编码：
例如 `My Wiki`：
```bash
open "obsidian://open?vault=My%20Wiki&file=daily/2026-05-22"
```

## 测试 URI

运行这个命令测试 URI 是否正确：
```bash
# 替换 <vault名称> 为你的实际 vault 名称
python3 ~/.qclaw/workspace/wiki/scripts/generate_obsidian_uri.py <vault名称> daily/2026-05-22
```

## 推荐的 Vault 名称

为了避免混淆，建议将 vault 命名为：
- `my-wiki`（推荐，简洁）
- `wiki`
- `knowledge-base`

## 自动化脚本

我已经创建了 `scripts/generate_obsidian_uri.py` 来生成正确的 URI。

使用方法：
```bash
python3 scripts/generate_obsidian_uri.py my-wiki daily/2026-05-22
```

输出：
```
📝 Obsidian URI:
obsidian://open?vault=my-wiki&file=daily/2026-05-22

🌐 在浏览器中打开或使用 'open' 命令:
open "obsidian://open?vault=my-wiki&file=daily/2026-05-22"
```

## 下一步

1. 在 Obsidian 中打开 `~/.qclaw/workspace/wiki` 文件夹
2. 记住你给 vault 起的名字
3. 使用上面生成的 URI 或用 Quick Switcher（Cmd+O）
