# Obsidian Sync 模块

将 Vault 内容同步到外部 Obsidian Vault，保持一致。

## 支持的 Vault

| Vault | 路径 | 说明 |
|:---|:---|:---|
| Documents Vault | `~/Documents/Obsidian Vault/` | 外部 Obsidian Vault |

> **注意**: Vault root 本身就是 Obsidian Vault，无需再同步到自身。

## 使用

```bash
# 通过 wiki_tool.py
python wiki_tool.py sync-obsidian          # 同步到所有外部 Vault
python wiki_tool.py sync-obsidian --vault documents  # 仅同步到 Documents

# 直接调用
python modules/obsidian-sync/sync.py
python modules/obsidian-sync/sync.py --vault documents
```

## 同步规则

1. **vault root → Documents Vault**: 将 vault root 下的知识文件同步到外部 Obsidian Vault
2. **目录映射**:
   - `daily/` → `daily/`
   - `projects/` → `projects/`
   - `concepts/` → `concepts/`
   - `people/` → `people/`
   - `brain/` → `brain/`
   - `AI产品经理共学营/` → `AI产品经理共学营/`
   - `OpenClaw/` → `OpenClaw/`
3. **首页**: 自动生成 `首页.md`，带 `[[]]` 双链导航
4. **冲突策略**: vault root 版本优先（local wins）

## 文件

- `sync.py`: 同步脚本
- `README.md`: 本文件
