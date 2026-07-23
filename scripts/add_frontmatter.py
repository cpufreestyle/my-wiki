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
