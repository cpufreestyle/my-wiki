#!/bin/bash
# Mac 设置脚本 - 为 my-wiki 配置 macOS 环境

set -e

echo "🍎 开始配置 macOS 环境..."
echo ""

# 检查 Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 未安装"
    echo "📥 正在安装 Python 3..."
    
    # 检查是否有 Homebrew
    if command -v brew &> /dev/null; then
        brew install python3
    else
        echo "⚠️  未找到 Homebrew，请从 https://python.org 下载安装 Python 3"
        echo "   或安装 Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
else
    echo "✅ Python 3 已安装: $(python3 --version)"
fi

# 检查 pip3
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 未安装"
    echo "📥 正在安装 pip3..."
    python3 -m ensurepip --upgrade
else
    echo "✅ pip3 已安装: $(pip3 --version)"
fi

# 安装 Python 依赖
echo ""
echo "📦 安装 Python 依赖..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
else
    echo "⚠️  未找到 requirements.txt，跳过依赖安装"
fi

# 使所有脚本可执行
echo ""
echo "🔧 设置脚本权限..."
find . -name "*.py" -exec chmod +x {} \;
find . -name "*.sh" -exec chmod +x {} \;
echo "✅ 脚本权限已设置"

# 检查 Obsidian
echo ""
if [ -d "/Applications/Obsidian.app" ]; then
    echo "✅ Obsidian 已安装"
else
    echo "⚠️  Obsidian 未安装"
    echo "📥 下载 Obsidian: https://obsidian.md"
    echo "   或使用 Homebrew: brew install --cask obsidian"
fi

# 创建必要的文件夹
echo ""
echo "📁 创建必要的文件夹..."
mkdir -p daily
mkdir -p mood
mkdir -p concepts
mkdir -p projects
mkdir -p reminders
mkdir -p scripts
mkdir -p stock-dashboard/data
mkdir -p attachments
echo "✅ 文件夹已创建"

# 添加 frontmatter 到现有笔记（如果脚本存在）
echo ""
echo "📝 为现有笔记添加 frontmatter..."
if [ -f "scripts/add_frontmatter.py" ]; then
    python3 scripts/add_frontmatter.py
else
    echo "⚠️  add_frontmatter.py 未找到，跳过"
    echo "   创建中..."
    
    cat > scripts/add_frontmatter.py << 'EOF'
#!/usr/bin/env python3
"""Add Obsidian-compatible frontmatter to existing markdown files."""

import os
import re
from pathlib import Path
from datetime import datetime

def extract_title_from_filename(filename):
    """Extract title from filename (remove date prefix and extension)."""
    name = filename.replace('.md', '')
    name = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', name)
    name = name.replace('-', ' ').title()
    return name

def extract_date_from_filename(filename):
    """Extract date from filename if it starts with YYYY-MM-DD."""
    match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return match.group(1)
    return datetime.now().strftime('%Y-%m-%d')

def detect_tags_from_path(file_path):
    """Detect tags based on file path."""
    tags = []
    path_str = str(file_path)
    
    if '/daily/' in path_str:
        tags.append('daily')
    if '/projects/' in path_str:
        tags.append('project')
    if '/concepts/' in path_str:
        tags.append('concept')
    
    return tags

def has_frontmatter(content):
    """Check if file already has YAML frontmatter."""
    return content.strip().startswith('---')

def add_frontmatter_to_file(file_path):
    """Add frontmatter to a single file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if has_frontmatter(content):
        return False
    
    filename = file_path.name
    title = extract_title_from_filename(filename)
    date = extract_date_from_filename(filename)
    tags = detect_tags_from_path(file_path)
    
    file_type = 'daily' if '/daily/' in str(file_path) else 'project' if '/projects/' in str(file_path) else 'note'
    
    frontmatter = f"""---
title: "{title}"
date: {date}
tags: {tags}
type: {file_type}
---

"""
    
    new_content = frontmatter + content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return True

def main():
    wiki_root = Path(__file__).parent.parent
    md_files = list(wiki_root.rglob('*.md'))
    
    exclude_patterns = ['.obsidian', 'node_modules', '.git']
    filtered_files = [f for f in md_files if not any(pattern in str(f) for pattern in exclude_patterns)]
    
    print(f"📝 Found {len(filtered_files)} markdown files")
    print(f"🔄 Adding frontmatter...\n")
    
    updated = 0
    skipped = 0
    
    for file_path in filtered_files:
        try:
            if add_frontmatter_to_file(file_path):
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
    
    print(f"\n✅ Complete!")
    print(f"   Updated: {updated} files")
    print(f"   Skipped: {skipped} files")

if __name__ == '__main__':
    main()
EOF
    
    chmod +x scripts/add_frontmatter.py
    python3 scripts/add_frontmatter.py
fi

# 更新索引
echo ""
echo "📊 更新 wiki 索引..."
if [ -f "scripts/update_index.py" ]; then
    python3 scripts/update_index.py
else
    echo "⚠️  update_index.py 未找到，跳过"
fi

echo ""
echo "✅ macOS 环境配置完成！"
echo ""
echo "📖 下一步："
echo "   1. 打开 Obsidian"
echo "   2. 选择 'Open folder as vault'"
echo "   3. 选择当前文件夹 ($(pwd))"
echo "   4. 开始使用！"
echo ""
echo "💡 提示："
echo "   - 使用 Cmd+P 打开命令面板"
echo "   - 每日笔记: Cmd+P → 'Daily Notes: Open today's note'"
echo "   - 插入模板: Cmd+P → 'Templates: Insert template'"
