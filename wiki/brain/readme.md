---
type: index
title: GBrain 知识图谱
date: 2026-07-06
tags:
  - gbrain
  - knowledge-graph
---

# GBrain 知识图谱

> 此目录由 GBrain 自动导出生成，包含语义索引和知识图谱关联。

## 统计

- **Pages**: 109
- **Chunks**: 261
- **Embedded**: 261 (100%)
- **Links**: 37
- **Sources**: 2 (default + my-wiki)

## 核心节点

### 人物
- [[people/michael_qiu|Michael Qiu]] — 用户/开发者，拥有 6 个项目

### 项目
- [[projects/stock-crewai|Stock CrewAI]] — 股票自动交易系统 v4.0
- [[projects/psvr2-panel|PSVR2 Panel]] — PSVR2 设备管理工具 v4.0
- [[projects/sanguosha-mobile-updates|三国杀手游]]
- [[projects/my-wiki-updates|My Wiki]]

### 概念
- [[concepts/llm_wiki|LLM Wiki 知识库构建模式]]
- [[concepts/rag_vs_wiki|RAG vs Wiki 对比]]

## 知识图谱关联

```
Michael Qiu
├── owns → stock-crewai
├── owns → psvr2-panel
├── owns → sanguosha-mobile
├── owns → my-wiki
├── interested_in → llm_wiki
└── interested_in → rag_vs_wiki

llm_wiki ←→ rag_vs_wiki (related_to)
llm_wiki → readme (described_in)
stock-crewai → stock-crewai-updates (tracked_by)
psvr2-panel → psvr2-panel-updates (tracked_by)
```

## 使用方式

```bash
# 语义搜索
gbrain query "你的问题"

# 手动同步 wiki
gbrain sync --source my-wiki

# 重新导出知识图谱
gbrain export --dir wiki/brain/

# 查看某个节点的图谱
gbrain graph people/michael_qiu --depth 3
```

## 自动同步

- **Cron**: 每 30 分钟自动同步 my-wiki → GBrain
- **Job ID**: `544763f1-8512-4dfd-9219-1512af929396`
- **Embedding**: nomic-embed-text (Ollama, 本地)
