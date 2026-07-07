# Obsidian Sync 模块

将 MyWiki 内容同步到多个 Obsidian Vault，保持双向一致。

## 支持的 Vault

| Vault | 路径 | 说明 |
|:---|:---|:---|
| Documents Vault | `~/Documents/Obsidian Vault/` | 主 Obsidian Vault |
| Wiki Vault | `~/.qclaw/workspace/wiki/wiki/` | workspace 内 Vault |

## 使用

```bash
# 通过 wiki_tool.py
python wiki_tool.py sync-obsidian          # 同步到所有 Vault
python wiki_tool.py sync-obsidian --vault documents  # 仅同步到 Documents
python wiki_tool.py sync-obsidian --vault wiki       # 仅同步到 Wiki

# 直接调用
python modules/obsidian-sync/sync.py
python modules/obsidian-sync/sync.py --vault documents
```

## 同步规则

1. **wiki → vault**: 将 wiki/ 下的内容同步到 Obsidian Vault
2. **目录映射**:
   - `daily/` → `daily/`
   - `projects/` → `projects/`
   - `concepts/` → `concepts/`
   - `people/` → `people/`
   - `modules/` 下的报告 → 按模块分类
3. **首页**: 自动生成 `首页.md`，带 `[[]]` 双链导航
4. **冲突策略**: wiki 版本优先（local wins）

## 文件

- `sync.py`: 同步脚本
- `README.md`: 本文件
