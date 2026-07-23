<#
.SYNOPSIS
    MyWiki Obsidian 助手 - 增强版

.DESCRIPTION
    双击打开 Obsidian · 创建/搜索/同步笔记 · 每日模板 · 快捷热键

.USAGE
    .\obsidian_helper.ps1 <action> [args]

.ACTIONS
    open            打开 Obsidian vault
    daily           打开/创建今日日记（自动模板）
    new <标题>      新建笔记
    search <关键词>  在 Obsidian 搜索
    sync            双向同步 wiki → Obsidian
    graph           生成知识图谱
    review          生成周回顾报告
    index           重建知识索引
    serve           启动 HTTP 服务（方便其他设备访问）
#>

param(
    [string]$Action = "daily",
    [string]$Argument = ""
)

# ===== 配置 =====
$WIKI_PATH   = "D:\Users\michael\MyWiki"
$OBS_URI     = "obsidian://open?vault=MyWiki"
$DAILY_TPL   = @"
# {{date}}

> {{time}}

## 📋 今日要点


## ✅ 待办
- [ ] 

## 💡 想法


## 📖 阅读/学习


## 🔗 关联
> `[[` 然后选择关联页面

---
标签: #{{date_short}}
"@

$NOTE_TPL = @"
# {{title}}

> 创建于 {{datetime}}

---

## 概述


## 细节


## 关联
> - [[]]

---
标签: #{{date_short}}
"@

# ===== 辅助函数 =====
function Get-DateTokens {
    @{
        date       = (Get-Date -Format "yyyy-MM-dd")
        date_short = (Get-Date -Format "yyyyMMdd")
        datetime   = (Get-Date -Format "yyyy-MM-dd HH:mm")
        time       = (Get-Date -Format "HH:mm")
        year_month = (Get-Date -Format "yyyy-MM")
    }
}

function Expand-Template {
    param([string]$Template, [hashtable]$Tokens)
    $result = $Template
    foreach ($k in $Tokens.Keys) {
        $result = $result -replace "\{\{$k\}\}", $Tokens[$k]
    }
    return $result
}

function New-MyWikiNote {
    param([string]$Title, [string]$Type = "note")
    $tokens = Get-DateTokens
    $tokens["title"] = $Title

    if ($Type -eq "daily") {
        $fileName = "$($tokens.date).md"
        $filePath = Join-Path $WIKI_PATH "daily" $fileName
        $content  = Expand-Template $DAILY_TPL $tokens

        if (-not (Test-Path $filePath)) {
            # 确保目录存在
            New-Item -Path (Split-Path $filePath) -ItemType Directory -Force | Out-Null
            New-Item -Path $filePath -ItemType File -Force | Out-Null
            Set-Content -Path $filePath -Value $content -Encoding UTF8
            Write-Host "✅ 今日日记已创建: $fileName" -ForegroundColor Green
        } else {
            Write-Host "📝 今日日记已存在: $fileName" -ForegroundColor Cyan
        }

        $encodedFile = [System.Uri]::EscapeDataString("$($tokens.year_month)/$($tokens.date)")
        $uri = "obsidian://open?vault=MyWiki&file=daily/$($tokens.date)"
    } else {
        $safeName = $Title -replace '[\\/:*?"<>|]', '' -replace '\s+', '-'
        $filePath = Join-Path $WIKI_PATH "$safeName.md"
        $content  = Expand-Template $NOTE_TPL $tokens

        if (-not (Test-Path $filePath)) {
            New-Item -Path $filePath -ItemType File -Force | Out-Null
            Set-Content -Path $filePath -Value $content -Encoding UTF8
            Write-Host "✅ 笔记已创建: $safeName.md" -ForegroundColor Green
        }

        $uri = "obsidian://open?vault=MyWiki&file=$safeName"
    }

    Start-Process $uri
}

function Search-MyWiki {
    param([string]$Query)
    $encoded = [System.Uri]::EscapeDataString($Query)
    $uri = "obsidian://search?vault=MyWiki&query=$encoded"
    Start-Process $uri
    Write-Host "🔍 搜索: $Query" -ForegroundColor Yellow
}

function Run-PythonScript {
    param([string]$ScriptName, [string]$Arg2 = "")
    $scriptPath = Join-Path $WIKI_PATH "scripts" $ScriptName
    if (-not (Test-Path $scriptPath)) {
        Write-Host "❌ 脚本不存在: $scriptPath" -ForegroundColor Red
        return
    }
    Write-Host "🔧 运行 $ScriptName ..." -ForegroundColor Cyan
    python $scriptPath $Arg2
}

function Sync-WikiObsidian {
    Write-Host "🔄 双向同步 MyWiki ←→ Obsidian ..." -ForegroundColor Cyan
    # 确保所有目录存在
    @("daily", "projects", "concepts", "people", "attachments") | ForEach-Object {
        $dir = Join-Path $WIKI_PATH $_
        if (-not (Test-Path $dir)) {
            New-Item -Path $dir -ItemType Directory -Force | Out-Null
            Write-Host "  📁 创建目录: $_" -ForegroundColor Gray
        }
    }
    Write-Host "✅ 目录结构同步完成" -ForegroundColor Green
}

function Serve-Wiki {
    $port = 8765
    Write-Host "🌐 启动 MyWiki HTTP 服务: http://localhost:$port" -ForegroundColor Cyan
    Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Gray
    python -m http.server $port --directory $WIKI_PATH
}

# ===== 主逻辑 =====
switch ($Action.ToLower()) {
    "open"        { Start-Process "obsidian://"; Write-Host "📂 Obsidian 已打开" -ForegroundColor Green }
    "daily"       { New-MyWikiNote -Title "DailyNote" -Type "daily" }
    "new"         { New-MyWikiNote -Title $Argument -Type "note" }
    "search"      { Search-MyWiki -Query $Argument }
    "sync"        { Sync-WikiObsidian }
    "graph"       { Run-PythonScript "generate_graph.py" }
    "review"      { Run-PythonScript "weekly_review.py" }
    "index"       { Run-PythonScript "update_index.py" }
    "fetch"       { Run-PythonScript "auto_fetch.py" }
    "rss"         { Run-PythonScript "fetch_rss.py" }
    "serve"       { Serve-Wiki }
    default {
        Write-Host ""
        Write-Host "📖 MyWiki Obsidian 助手 - 用法" -ForegroundColor White
        Write-Host "=" * 45
        Write-Host "  .\obsidian_helper.ps1 open          打开 Obsidian" -ForegroundColor Gray
        Write-Host "  .\obsidian_helper.ps1 daily         今日日记" -ForegroundColor Gray
        Write-Host "  .\obsidian_helper.ps1 new '标题'   新建笔记" -ForegroundColor Gray
        Write-Host "  .\obsidian_helper.ps1 search '关键词' 搜索" -ForegroundColor Gray
        Write-Host "  .\obsidian_helper.ps1 sync          同步目录结构" -ForegroundColor Gray
        Write-Host "  .\obsidian_helper.ps1 graph         生成知识图谱" -ForegroundColor Gray
        Write-Host "  .\obsidian_helper.ps1 review        周回顾报告" -ForegroundColor Gray
        Write-Host "  .\obsidian_helper.ps1 index         重建索引" -ForegroundColor Gray
        Write-Host "  .\obsidian_helper.ps1 fetch         运行 auto-fetch" -ForegroundColor Gray
        Write-Host "  .\obsidian_helper.ps1 serve         HTTP 服务(8765)" -ForegroundColor Gray
        Write-Host ""
    }
}
