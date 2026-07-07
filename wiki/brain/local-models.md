---
type: note
title: 本地模型支持指南
---

# 本地模型支持指南

> 如何使用本地运行的大语言模型（LLM）与你的 Personal Knowledge Wiki

---

## 📖 目录

- [为什么使用本地模型](#为什么使用本地模型)
- [支持的本地模型解决方案](#支持的本地模型解决方案)
- [快速开始](#快速开始)
- [详细配置](#详细配置)
- [使用场景](#使用场景)
- [性能优化](#性能优化)
- [故障排除](#故障排除)

---

## 🤔 为什么使用本地模型

### 优势

| 优势 | 说明 |
|------|------|
| **隐私** | 数据不离开本地，完全离线运行 |
| **成本** | 无 API 费用，一次性硬件投入 |
| **速度** | 无网络延迟，响应快 |
| **自定义** | 可以使用微调模型或特定领域模型 |
| **离线** | 无需互联网连接 |

### 劣势

| 劣势 | 说明 |
|------|------|
| **硬件要求** | 需要足够的 RAM 和 GPU |
| **模型质量** | 本地模型通常小于云端模型 |
| **设置复杂** | 需要配置环境和参数 |

---

## 🛠️ 支持的本地模型解决方案

### 1. Ollama（推荐）

**特点**：
- ✅ 开源、免费
- ✅ 简单易用（命令行）
- ✅ 支持多种模型（Llama 3, Mistral, Gemma 等）
- ✅ 提供 REST API（OpenAI 兼容）

**安装**：
```bash
# macOS
brew install ollama

# 或下载
# https://ollama.com/download

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# 下载 Windows 版本（测试中）
```

**快速开始**：
```bash
# 启动 Ollama 服务
ollama serve

# 拉取模型
ollama pull llama3        # Llama 3 (8B)
ollama pull mistral       # Mistral (7B)
ollama pull codellama     # Code Llama (7B)

# 运行模型
ollama run llama3 "Hello, world!"

# API 测试
curl http://localhost:11434/api/generate -d '{
  "model": "llama3",
  "prompt": "Why is the sky blue?"
}'
```

---

### 2. LM Studio

**特点**：
- ✅ 图形界面（GUI）
- ✅ 支持 macOS/Windows/Linux
- ✅ 自动下载模型
- ✅ 提供 Local Server（OpenAI 兼容 API）

**安装**：
1. 下载：https://lmstudio.ai
2. 安装并启动
3. 在 "Discover" 页面搜索并下载模型

**配置 Local Server**：
1. 点击左侧 **"Local Server"** 图标
2. 选择模型
3. 点击 **"Start Server"**
4. 默认 API 地址：`http://localhost:1234/v1`

---

### 3. GPT4All

**特点**：
- ✅ 开源、免费
- ✅ 图形界面
- ✅ 支持多种模型
- ✅ 提供 Python API

**安装**：
1. 下载：https://gpt4all.io
2. 安装并启动
3. 下载模型

**Python API**：
```python
from gpt4all import GPT4All

model = GPT4All("orca-mini-3b-gguf2-q4_0.gguf")
response = model.generate("Why is the sky blue?")
print(response)
```

---

### 4. llama.cpp（高级用户）

**特点**：
- ✅ 最底层、最灵活
- ✅ 支持 CPU 和 GPU 加速
- ✅ 多种绑定（Python, Node.js, Go 等）

**安装**：
```bash
# 克隆仓库
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# 编译（macOS with Metal）
make

# 下载模型
# 从 Hugging Face 下载 GGUF 格式模型

# 运行
./main -m models/llama-3-8b-q4.gguf -p "Why is the sky blue?"
```

---

## 🚀 快速开始

### 场景：使用 Ollama 与 OpenClaw

#### 步骤 1: 安装 Ollama

```bash
# macOS
brew install ollama

# 启动服务
ollama serve &
```

#### 步骤 2: 拉取模型

```bash
# 推荐模型（按大小排序）
ollama pull phi3:mini        # 3.8B - 最快
ollama pull llama3:8b        # 8B - 平衡
ollama pull llama3:70b       # 70B - 最强（需要大内存）

# 或 Mistral
ollama pull mistral:7b
```

#### 步骤 3: 配置 OpenClaw

编辑 OpenClaw 配置文件（通常在 `~/.config/openclaw/config.yaml`）：

```yaml
models:
  - name: "ollama-llama3"
    provider: "openai-compatible"
    base_url: "http://localhost:11434/v1"
    api_key: "dummy"  # Ollama 不需要 API key
    model: "llama3"
    default: true  # 设为默认模型
```

#### 步骤 4: 测试

```bash
# 测试 Ollama API
curl http://localhost:11434/api/tags

# 测试 OpenClaw
openclaw chat "Hello from local model!"
```

---

## ⚙️ 详细配置

### OpenClaw 配置（多模型）

编辑 `~/.config/openclaw/config.yaml`：

```yaml
models:
  # 云端模型（备用）
  - name: "qclaw/modelroute"
    provider: "qclaw"
    default: false

  # 本地模型（Ollama）
  - name: "local-llama3"
    provider: "openai-compatible"
    base_url: "http://localhost:11434/v1"
    api_key: "dummy"
    model: "llama3:8b"
    default: true
    options:
      temperature: 0.7
      num_ctx: 4096  # 上下文长度

  # 本地模型（LM Studio）
  - name: "local-lmstudio"
    provider: "openai-compatible"
    base_url: "http://localhost:1234/v1"
    api_key: "dummy"
    model: "mistral-7b"
    default: false
```

### 切换模型

```bash
# 在 OpenClaw 中切换模型
openclaw config set model local-llama3

# 或在对话中指定
"使用 local-llama3 模型回答：..."
```

---

### Obsidian 配合本地模型

如果你使用 Obsidian 的 AI 插件（如 Text Generator, Copilot），配置本地模型：

#### Text Generator 插件

1. 安装 Text Generator 插件
2. 设置 → Text Generator → Model
3. 选择 "OpenAI Compatible"
4. 填入：
   - Base URL: `http://localhost:11434/v1`
   - API Key: `dummy`
   - Model: `llama3`

#### Copilot 插件

1. 安装 Copilot 插件
2. 设置 → Copilot → Model
3. 选择 "Ollama"
4. 填入：
   - Model: `llama3`
   - API URL: `http://localhost:11434`

---

## 📋 使用场景

### 场景 1: 完全离线使用

```bash
# 1. 启动 Ollama
ollama serve &

# 2. 配置 OpenClaw 使用本地模型
# （见上方配置）

# 3. 正常使用
openclaw chat "总结今天的笔记"
```

---

### 场景 2: 混合使用（云端 + 本地）

```yaml
# config.yaml
models:
  - name: "cloud"
    provider: "openai"
    model: "gpt-4"
    default: false

  - name: "local"
    provider: "openai-compatible"
    base_url: "http://localhost:11434/v1"
    model: "llama3"
    default: true

# 敏感数据用本地模型
# 复杂任务用云端模型
```

---

### 场景 3: 自动化脚本使用本地模型

**示例：自动总结笔记**

```python
# scripts/summarize_with_local_model.py
import requests
import os

def summarize_with_ollama(text, model="llama3"):
    """使用 Ollama 本地模型总结文本"""
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": f"Summarize the following text:\n\n{text}",
            "stream": False
        }
    )
    return response.json()["response"]

# 使用示例
note_content = open("daily/2026-07-01.md").read()
summary = summarize_with_ollama(note_content)
print(summary)
```

---

## 🚀 性能优化

### 硬件建议

| 模型大小 | RAM 要求 | GPU 推荐 | 速度 |
|----------|----------|----------|------|
| 3B-7B | 8GB | 可选 | 快 |
| 13B-30B | 32GB | 推荐 | 中 |
| 70B+ | 64GB+ | 必需 | 慢 |

### 模型量化

使用量化模型可减少内存占用并提升速度：

```bash
# Ollama 支持量化版本
ollama pull llama3:8b-q4_0    # 4-bit 量化（最快）
ollama pull llama3:8b-q5_0    # 5-bit 量化（平衡）
ollama pull llama3:8b-q8_0    # 8-bit 量化（质量最好）

# 或使用 GGUF 格式（llama.cpp）
# Q4_K_M: 推荐（平衡）
# Q5_K_M: 高质量
# Q8_K: 最高质量
```

### 上下文长度

```bash
# Ollama 设置上下文长度
ollama run llama3 --num_ctx 4096

# 或在 Modelfile 中
FROM llama3
PARAMETER num_ctx 4096
```

---

## 🛠️ 故障排除

### 问题 1: Ollama 无法启动

**错误**：`Error: listen tcp 127.0.0.1:11434: bind: address already in use`

**解决**：
```bash
# 查找占用进程
lsof -i :11434

# 杀死进程
kill -9 <PID>

# 重新启动
ollama serve
```

---

### 问题 2: 模型响应慢

**原因**：
- 模型太大
- 未使用 GPU 加速
- 上下文长度太长

**解决**：
```bash
# 1. 使用更小的模型
ollama pull phi3:mini  # 3.8B

# 2. 启用 GPU（macOS Metal）
export OLLAMA_METAL=1
ollama serve

# 3. 减少上下文长度
ollama run llama3 --num_ctx 2048
```

---

### 问题 3: OpenClaw 无法连接本地模型

**错误**：`Connection refused`

**解决**：
1. 确认 Ollama/LM Studio 服务正在运行
2. 检查 API 地址是否正确
3. 测试 API：

```bash
# Ollama
curl http://localhost:11434/api/tags

# LM Studio
curl http://localhost:1234/v1/models
```

---

### 问题 4: 内存不足

**错误**：`Out of memory`

**解决**：
```bash
# 1. 使用量化模型
ollama pull llama3:8b-q4_0

# 2. 减少并发请求
# 3. 增加系统交换空间
```

---

## 📚 参考资料

- **Ollama 官方文档**: https://ollama.com/docs
- **LM Studio 文档**: https://lmstudio.ai/docs
- **GPT4All 文档**: https://gpt4all.io/documentation
- **llama.cpp**: https://github.com/ggerganov/llama.cpp
- **OpenAI Compatible APIs**: https://platform.openai.com/docs/api-reference

---

## 🎯 下一步

1. **选择本地模型解决方案**（推荐 Ollama）
2. **安装并配置**
3. **测试与 OpenClaw 的集成**
4. **优化性能**
5. **享受隐私保护的本地 AI！**

---

**最后更新**: 2026-07-01

**支持模型**: Ollama, LM Studio, GPT4All, llama.cpp
