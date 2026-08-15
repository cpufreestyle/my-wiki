# MyWiki v2.3.0 — 语义 RAG 检索引擎 🚀

本次更新为 MyWiki 带来了真正的语义检索能力（此前仅有子串文本匹配）。

## ✨ 新特性

- **语义 RAG 检索**：从子串匹配升级为语义相关性排序，更懂查询意图
- **零依赖开箱即用**：默认 BM25 模式，纯标准库实现，中文 bigram 分词 + IDF 排序
- **可选本地向量检索**：本机运行 Ollama + `nomic-embed-text` 时自动升级为 embedding 语义检索，完全离线、隐私友好
- **智能分块**：按段落/标题切分笔记，精准召回相关片段并给出打分
- **全链路集成**：
  - `wiki_tool.py search` 已升级为语义搜索（失败回退文本匹配）
  - `wiki_core.semantic_search()` 新增
  - MCP 工具 `wiki_semantic_search` 暴露，所有接入的 Agent（Claude / Cursor / OpenClaw 等）都能用上 RAG

## 🛠 使用方式

```bash
# 直接语义搜索
python rag.py "如何配置本地模型 ollama"

# 经 wiki_tool 入口（已升级为语义搜索）
python wiki_tool.py search "obsidian 如何同步多设备笔记"

# 启用本地向量检索（需 Ollama）
MYWIKI_RAG_MODE=ollama python rag.py "你的问题" --rebuild
```

## 🔧 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `MYWIKI_RAG_MODE` | 检索模式 `bm25` / `ollama` | `bm25` |
| `MYWIKI_OLLAMA_URL` | Ollama 服务地址 | `http://localhost:11434` |
| `MYWIKI_EMBED_MODEL` | 嵌入模型名 | `nomic-embed-text` |

## 📦 完整变更

- `rag.py`（新增）：语义检索引擎 RAGEngine
- `wiki_tool.py` / `wiki_core.py` / `mcp_server.py`：语义检索集成
- `.gitignore`：忽略 RAG 检索缓存 `wiki/.rag_index.json`
- `README.md`：新增「8. 语义 RAG 检索」章节
