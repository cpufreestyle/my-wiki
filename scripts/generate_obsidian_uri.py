#!/usr/bin/env python3
"""Generate correct Obsidian URI for opening notes."""

import sys
from pathlib import Path

def generate_obsidian_uri(vault_name, file_path):
    """Generate Obsidian URI for opening a file."""
    # URL encode the file path
    import urllib.parse
    encoded_path = urllib.parse.quote(file_path, safe='/')
    
    uri = f"obsidian://open?vault={vault_name}&file={encoded_path}"
    return uri

def main():
    if len(sys.argv) < 3:
        print("用法: python3 generate_obsidian_uri.py <vault_name> <file_path>")
        print("示例: python3 generate_obsidian_uri.py my-wiki daily/2026-05-22")
        sys.exit(1)
    
    vault_name = sys.argv[1]
    file_path = sys.argv[2]
    
    uri = generate_obsidian_uri(vault_name, file_path)
    
    print(f"📝 Obsidian URI:")
    print(f"{uri}")
    print(f"\n🌐 在浏览器中打开或使用 'open' 命令:")
    print(f"open \"{uri}\"")

if __name__ == '__main__':
    main()
