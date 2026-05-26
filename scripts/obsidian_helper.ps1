# Obsidian Wiki 助手脚本
# 用法：
#   .\obsidian_helper.ps1 open                    # 打开 Obsidian (wiki vault)
#   .\obsidian_helper.ps1 new "笔记标题"         # 创建新笔记
#   .\obsidian_helper.ps1 search "关键词"         # 在 Obsidian 中搜索
#   .\obsidian_helper.ps1 daily                   # 打开今日日记
#   .\obsidian_helper.ps1 open-file "daily/2026-05-25"  # 打开指定文件

$WIKI_PATH = "C:\Users\michael\.qclaw\workspace\wiki"
$OBSIDIAN_URI = "obsidian://open?vault=wiki"

function Open-Obsidian {
    Start-Process "obsidian://"
}

function Open-DailyNote {
    $date = Get-Date -Format "yyyy-MM-dd"
    $filePath = "$WIKI_PATH\daily\$date.md"
    
    # 如果今日笔记不存在，创建模板
    if (-not (Test-Path $filePath)) {
        $template = "# $date`n`n## 日志`n`n## 待办`n- [ ] `n`n## 想法`n"
        New-Item -Path $filePath -ItemType File -Force | Out-Null
        Set-Content -Path $filePath -Value $template -Encoding UTF8
        Write-Output "✅ 创建今日笔记: $date.md"
    }
    
    # 用 Obsidian URI 打开
    $uri = "obsidian://open?vault=wiki&file=daily/$date"
    Start-Process $uri
    Write-Output "📝 已打开今日笔记"
}

function New-Note {
    param([string]$Title)
    
    if (-not $Title) {
        $Title = Read-Host "请输入笔记标题"
    }
    
    # 生成文件名（移除特殊字符）
    $fileName = $Title -replace '[\\/:*?"<>|]', '' -replace '\s+', '-'
    $filePath = "$WIKI_PATH\$fileName.md"
    
    # 如果文件不存在，创建
    if (-not (Test-Path $filePath)) {
        $content = "# $Title`n`n创建时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm')`n`n---\`n`n"
        New-Item -Path $filePath -ItemType File -Force | Out-Null
        Set-Content -Path $filePath -Value $content -Encoding UTF8
        Write-Output "✅ 创建笔记: $fileName.md"
    }
    
    # 打开
    $uri = "obsidian://open?vault=wiki&file=$fileName"
    Start-Process $uri
}

function Search-Obsidian {
    param([string]$Query)
    
    if (-not $Query) {
        $Query = Read-Host "请输入搜索关键词"
    }
    
    $encoded = [System.Uri]::EscapeDataString($Query)
    $uri = "obsidian://search?vault=wiki&query=$encoded"
    Start-Process $uri
    Write-Output "🔍 在 Obsidian 中搜索: $Query"
}

function Open-File {
    param([string]$FilePath)
    
    if (-not $FilePath) {
        $FilePath = Read-Host "请输入文件路径（相对于 wiki/）"
    }
    
    # 移除 .md 后缀（如果有）
    $FilePath = $FilePath -replace '\.md$', ''
    
    $uri = "obsidian://open?vault=wiki&file=$FilePath"
    Start-Process $uri
    Write-Output "📂 已打开: $FilePath"
}

# 主逻辑
param(
    [string]$Action = "daily",
    [string]$Argument = ""
)

switch ($Action) {
    "open"    { Open-Obsidian }
    "daily"   { Open-DailyNote }
    "new"     { New-Note -Title $Argument }
    "search"  { Search-Obsidian -Query $Argument }
    "open-file" { Open-File -FilePath $Argument }
    default    { 
        Write-Output "用法:"
        Write-Output "  .\obsidian_helper.ps1 open              # 打开 Obsidian"
        Write-Output "  .\obsidian_helper.ps1 daily             # 打开今日日记"
        Write-Output "  .\obsidian_helper.ps1 new '标题'       # 创建新笔记"
        Write-Output "  .\obsidian_helper.ps1 search '关键词'   # 搜索"
        Write-Output "  .\obsidian_helper.ps1 open-file 'path' # 打开指定文件"
    }
}
