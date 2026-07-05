---
type: note
title: LM Studio 本地 Server 配置指南
---

# LM Studio 本地 Server 配置指南

## 步骤 1: 启动 Local Server

1. 打开 LM Studio
2. 点击左侧 **"Local Server"** 图标（箭头图标）
3. 在 **"Model"** 下拉菜单选择模型
4. 点击 **"Start Server"** 按钮

---

## 步骤 2: 配置参数

### Server Settings（服务器设置）

- **Port（端口）**: 默认 `1234`
- **Host（主机）**: 默认 `localhost`
- **CORS**: 启用（如果需要跨域访问）

### Model Settings（模型设置）

- **Context Length（上下文长度）**: 推荐 `4096` 或 `8192`
- **Temperature（温度）**: `0.7`（平衡创意和准确性）
- **Top P**: `0.9`
- **Frequency Penalty**: `0.0`
- **Presence Penalty**: `0.0`

---

## 步骤 3: 测试 API

### 检查 Server 状态

```bash
curl http://localhost:1234/v1/models
```

**预期响应：**
```json
{
  "data": [
    {
      "id": "mistral-7b-instruct",
      "object": "model",
      "owned_by": "lm-studio"
    }
  ]
}
```

### 测试生成

```bash
curl http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral-7b-instruct",
    "messages": [
      {"role": "user", "content": "Why is the sky blue?"}
    ],
    "temperature": 0.7
  }'
```

---

## 步骤 4: 配置 OpenClaw

编辑 `~/.config/openclaw/config.yaml`：

```yaml
models:
  - name: "local-lmstudio"
    provider: "openai-compatible"
    base_url: "http://localhost:1234/v1"
    api_key: "dummy"  # LM Studio 不需要 API key
    model: "mistral-7b-instruct"
    default: true
    options:
      temperature: 0.7
      num_ctx: 4096
```

---

## 步骤 5: 配置 Obsidian 插件

### Text Generator 插件

1. 安装 **Text Generator** 插件
2. 设置 → Text Generator → Model
3. 选择 **"OpenAI Compatible"**
4. 填入：
   - **Base URL**: `http://localhost:1234/v1`
   - **API Key**: `dummy`
   - **Model**: `mistral-7b-instruct`

### Copilot 插件

1. 安装 **Copilot** 插件
2. 设置 → Copilot → Model
3. 选择 **"OpenAI Compatible"**
4. 填入：
   - **Base URL**: `http://localhost:1234/v1`
   - **API Key**: `dummy`
   - **Model**: `mistral-7b-instruct`

---

## 常用模型推荐

| 模型 | 大小 | 速度 | 质量 | 推荐场景 |
|------|------|------|------|----------|
| **Mistral 7B Instruct** | 7B | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 通用 |
| **Llama 3 8B** | 8B | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 通用 |
| **Code Llama 7B** | 7B | ⭐⭐⭐ | ⭐⭐⭐⭐ | 代码 |
| **Phi-3 Mini** | 3.8B | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 快速 |

---

## 故障排除

### 问题 1: Server 无法启动

**解决**：
- 检查端口是否被占用：`lsof -i :1234`
- 尝试更改端口号

### 问题 2: 模型加载失败

**解决**：
- 检查系统内存（推荐 16GB+）
- 尝试更小的模型

### 问题 3: API 请求超时

**解决**：
- 增加 `num_ctx`（上下文长度）
- 降低 `temperature`
- 检查模型是否加载完成

---

## 相关链接

- LM Studio 官网：https://lmstudio.ai
- LM Studio 文档：https://lmstudio.ai/docs
- OpenAI API 兼容文档：https://platform.openai.com/docs/api-reference
