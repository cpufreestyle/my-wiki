# A2A Agent 模块

Google A2A (Agent-to-Agent) 协议本地 Agent 网络，将 OpenClaw 作为 A2A 节点接入。

## 架构

| Agent | 端口 | 模型/功能 |
|:---|:---|:---|
| Orchestrator | 10000 | 中央编排 + 智能路由 |
| LM Studio | 10001 | Gemma 4 12B 本地推理 |
| Ollama | 10002 | nomic-embed-text 嵌入 |
| Blender 3D | 10003 | 3D 渲染 |
| StepFun | 10004 | step-1-32k 云端 API |
| OpenClaw | 10005 | 工具调用 + 文件操作 + 搜索 |

## 通信协议

- JSON-RPC over HTTP
- Agent Card: `/.well-known/agent-card.json`
- 支持: 关键词路由、`@agent_name` 指定、broadcast 广播

## 使用

```bash
# 启动全部 Agent
cd ~/quest3-exploded/a2a-agents/
./start_all.sh

# 测试
curl http://localhost:10005/.well-known/agent-card.json
```

## 文件位置

A2A 项目不在 wiki 仓库内，位于 `~/quest3-exploded/a2a-agents/`。
此模块仅作为 wiki 的文档索引和联动说明。
