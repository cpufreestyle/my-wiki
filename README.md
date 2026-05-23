# Personal Knowledge Wiki

基于 Karpathy 的 LLM Wiki 理念构建的个人知识库

## 核心思想

传统 RAG：每次查询重新检索和推理
LLM Wiki：增量构建持久化知识结构，知识累积而非重复推导

## 目录结构

```
wiki/
├── README.md          # 本文件
├── INDEX.md           # 知识索引
├── people/            # 人物页面
├── projects/          # 项目页面
├── concepts/          # 概念/技术页面
├── daily/             # 每日笔记
└── attachments/       # 附件
```

## 使用方式

1. **添加新信息**：告诉 LLM 新信息，它会自动更新相关 wiki 页面
2. **查询知识**：直接问 LLM，它会从 wiki 中综合回答
3. **浏览知识**：用任意 Markdown 编辑器打开 wiki 目录

## 维护原则

- LLM 负责：总结、交叉引用、更新页面
- 人类负责：提供信息源、提出问题、审核结果
- 每次对话后：LLM 更新相关 wiki 页面
- 每周：LLM 生成知识图谱摘要

## 当前状态

- 创建时间：2026-05-22
- 初始知识：从 MEMORY.md 和 memory/*.md 迁移
- 工具：OpenClaw
