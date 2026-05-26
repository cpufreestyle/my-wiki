# Obsidian 联动配置

## 方案选择

### ✅ 推荐：Local REST API（最强大）
- 安装 Obsidian 插件：Local REST API
- 支持完整的 CRUD 操作
- 可以通过 HTTP API 自动化

### ⚡ 快速：Obsidian URI Scheme
```powershell
# 打开笔记
Start-Process "obsidian://open?vault=MyWiki&file=daily/2026-05-26"

# 搜索
Start-Process "obsidian://search?vault=MyWiki&query=股票"
```

### 📁 当前：直接文件操作
- wiki/ 目录就是标准的 Markdown 文件
- 可以直接用文件读写操作
- 无需额外工具

## 配置步骤

### 1. 将 wiki/ 作为 Obsidian Vault 打开
1. 打开 Obsidian 应用
2. 点击左侧栏"打开其他仓库" → "打开文件夹作为仓库"
3. 选择 `D:\Users\michael\MyWiki`
4. 完成！所有笔记立即可见

### 2. （可选）安装 Local REST API 插件
1. 在 Obsidian 设置 → 第三方插件 → 浏览
2. 搜索 "Local REST API"
3. 安装并启用
4. 记录 API key（用于自动化）

### 3. 测试 URI 打开
```powershell
# 测试：打开今天的日记
Start-Process "obsidian://open?vault=MyWiki&file=daily/2026-05-26"
```

## 自动化脚本示例

### 创建每日笔记
```powershell
$date = Get-Date -Format "yyyy-MM-dd"
$file = "D:\Users\michael\MyWiki\daily\$date.md"
if (-not (Test-Path $file)) {
    "# $date`n`n## 日志`n`n## 待办`n" | Out-File -FilePath $file -Encoding UTF8
}
Start-Process "obsidian://open?vault=MyWiki&file=daily/$date"
```

### 快速搜索
```powershell
$query = Read-Host "搜索关键词"
Start-Process "obsidian://search?vault=MyWiki&query=$query"
```

## 当前状态
- [ ] Obsidian 应用已安装
- [ ] MyWiki 已作为 Vault 打开
- [ ] Local REST API 插件已安装（可选）
- [ ] 测试 URI 打开成功
