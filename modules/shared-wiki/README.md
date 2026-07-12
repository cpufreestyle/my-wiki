# Shared Wiki 模块 — MyWiki × Obsidian × 所有 Agent 共享

把 MyWiki 变成一个**共享知识中枢**：Obsidian 直接读写同一个文件夹，电脑里运行的各种 AI Agent（OpenClaw、A2A 网络节点、Claude Desktop、Cursor、Memo…）通过统一的 API / MCP 协议读写同一个 Wiki。

```
┌─────────────┐   files (folder)   ┌──────────────────┐   MCP / API   ┌──────────────────┐
│  Obsidian   │ ◄────────────────► │   MyWiki 文件夹   │ ◄───────────► │  所有 AI Agent   │
│ (Vault)     │   共享 .md 文件     │  (单一事实源)     │  wiki_core.py │ OpenClaw/A2A/... │
└─────────────┘                    └──────────────────┘               └──────────────────┘
                                            │
                                            │  broadcast
                                            ▼
                                   agent_registry (发现/广播)
```

## 核心思想

- **单一事实源**：Wiki 文件夹就是全部知识，Obsidian 和 Agent 都读写它，不需要双向同步。
- **Agent 无关**：任何进程 import `wiki_core.py` 就能读写 Wiki，不绑定特定 Agent。
- **标准协议**：通过 MCP（Model Context Protocol）暴露，主流 Agent 宿主零代码接入。

## 文件

| 文件 | 作用 |
|------|------|
| `wiki_core.py` | 共享内核：读写、搜索、frontmatter、索引、清单导出 |
| `agent_registry.py` | 自动发现电脑里所有 Agent + 向它们广播知识更新 |
| `obsidian_bridge.py` | Obsidian Vault 发现、URI 打开、文件监听 |
| `mcp_server.py` | 把 Wiki 暴露为标准 MCP Server（stdio） |
| `registry.json` | 已发现/登记的 Agent 持久化（自动生成） |

## 快速使用

### 1. 让所有 Agent 共享 Wiki（启动 MCP Server）

```bash
python wiki_tool.py serve
```

然后在任意支持 MCP 的 Agent 宿主（Claude Desktop / Cursor / OpenClaw）配置：

```json
{
  "mcpServers": {
    "mywiki": {
      "command": "python",
      "args": ["/path/to/my-wiki/modules/shared-wiki/mcp_server.py"]
    }
  }
}
```

Agent 即可调用 `wiki_search` / `wiki_read` / `wiki_write` / `wiki_append` 等工具。

### 2. 发现电脑里所有的 Agent

```bash
python wiki_tool.py agents
# 或
python modules/shared-wiki/agent_registry.py
```

自动扫描 localhost 上常见的 Agent 端口（A2A 网络 10000-10005、Ollama、LM Studio）
和本地进程（OpenClaw / Claude / Cursor / Memo / Obsidian），并持久化到 `registry.json`。

### 3. 向所有 Agent 广播 Wiki 更新

```bash
python wiki_tool.py broadcast wiki.updated daily/2026-07-12.md
```

会把更新事件 POST 给所有在线且声明了 `wiki.read` 能力的 Agent。

### 4. Obsidian 桥接

```bash
python wiki_tool.py obsidian
```

发现本机 Obsidian Vault，并指出当前 wiki 对应的 vault 名称（供 `obsidian://` URI 使用）。

### 5. 在 Python 中直接调用（Agent 内部使用）

```python
from modules.shared_wiki import wiki_core as wc

# 搜索
hits = wc.search("股票")
# 读取
note = wc.read_note("daily/2026-07-12.md")
# 写入（自动补 frontmatter）
wc.write_note("concepts/Test.md", "## 内容...", {"title": "Test", "tags": ["test"]})
# 追加
wc.write_note("daily/2026-07-12.md", "- 新的一条", append=True)
# 今日日记
rel = wc.create_daily_note()
```

## 暴露给 Agent 的 MCP 工具

| 工具 | 说明 |
|------|------|
| `wiki_search` | 全文搜索，返回命中片段 |
| `wiki_read` | 按相对路径读取笔记 |
| `wiki_write` | 创建/覆盖笔记（自动 frontmatter） |
| `wiki_append` | 向笔记追加内容 |
| `wiki_list` | 列出笔记（可按分类过滤） |
| `wiki_daily` | 获取/创建今日日记 |
| `wiki_tags` | 按标签查询 |
| `wiki_agents` | 列出发现的 Agent |
| `wiki_index` | 重建 INDEX.md |

## 依赖

- 必需：`pyyaml`（frontmatter 解析）
- 可选：`mcp`（完整 MCP 协议）；未安装时自动降级为最小 JSON-RPC stdio，仍可被支持 MCP 的宿主调用
- 可选：`watchdog`（Obsidian 文件监听，未安装则退化为轮询）

```bash
pip install pyyaml mcp watchdog
```
