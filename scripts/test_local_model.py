#!/usr/bin/env python3
"""
测试本地模型连接和性能

支持的本地模型解决方案：
- Ollama (http://localhost:11434)
- LM Studio (http://localhost:1234)
- GPT4All (http://localhost:4891)
"""

import requests
import time
import json
from pathlib import Path

# 配置
OLLAMA_API = "http://localhost:11434"
LM_STUDIO_API = "http://localhost:1234"
GPT4ALL_API = "http://localhost:4891"

def test_ollama():
    """测试 Ollama 连接"""
    print("🧪 测试 Ollama...")
    print(f"   API: {OLLAMA_API}")
    
    try:
        # 检查服务
        response = requests.get(f"{OLLAMA_API}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"   ✅ Ollama 服务运行中")
            print(f"   📦 已安装模型: {[m['name'] for m in models]}")
            
            # 测试生成
            if models:
                model_name = models[0]['name']
                print(f"\n   🤖 测试生成 (模型: {model_name})...")
                
                start = time.time()
                gen_response = requests.post(
                    f"{OLLAMA_API}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "Hello, who are you?",
                        "stream": False
                    },
                    timeout=30
                )
                elapsed = time.time() - start
                
                if gen_response.status_code == 200:
                    result = gen_response.json()
                    print(f"   ✅ 生成成功")
                    print(f"   📝 响应: {result['response'][:100]}...")
                    print(f"   ⏱️  耗时: {elapsed:.2f}s")
                    print(f"   📊 Token/s: {result.get('eval_count', 0) / elapsed:.1f}")
                else:
                    print(f"   ❌ 生成失败: {gen_response.status_code}")
            else:
                print("   ⚠️  没有已安装的模型，请先运行: ollama pull llama3")
            
            return True
        else:
            print(f"   ❌ Ollama 服务异常: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ 无法连接到 Ollama (http://localhost:11434)")
        print(f"   💡 提示: 运行 'ollama serve' 启动服务")
        return False
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        return False

def test_lm_studio():
    """测试 LM Studio Local Server"""
    print("\n🧪 测试 LM Studio...")
    print(f"   API: {LM_STUDIO_API}")
    
    try:
        # 检查服务
        response = requests.get(f"{LM_STUDIO_API}/v1/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])
            print(f"   ✅ LM Studio Local Server 运行中")
            print(f"   📦 已加载模型: {[m['id'] for m in models]}")
            
            # 测试生成
            if models:
                model_id = models[0]['id']
                print(f"\n   🤖 测试生成 (模型: {model_id})...")
                
                start = time.time()
                gen_response = requests.post(
                    f"{LM_STUDIO_API}/v1/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": model_id,
                        "messages": [{"role": "user", "content": "Hello!"}],
                        "temperature": 0.7
                    },
                    timeout=30
                )
                elapsed = time.time() - start
                
                if gen_response.status_code == 200:
                    result = gen_response.json()
                    print(f"   ✅ 生成成功")
                    print(f"   📝 响应: {result['choices'][0]['message']['content'][:100]}...")
                    print(f"   ⏱️  耗时: {elapsed:.2f}s")
                else:
                    print(f"   ❌ 生成失败: {gen_response.status_code}")
            else:
                print("   ⚠️  没有已加载的模型，请在 LM Studio 中启动 Local Server")
            
            return True
        else:
            print(f"   ❌ LM Studio 服务异常: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ 无法连接到 LM Studio (http://localhost:1234)")
        print(f"   💡 提示: 在 LM Studio 中点击 'Local Server' → 'Start Server'")
        return False
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        return False

def test_gpt4all():
    """测试 GPT4All"""
    print("\n🧪 测试 GPT4All...")
    print(f"   API: {GPT4ALL_API}")
    
    try:
        response = requests.get(f"{GPT4ALL_API}/v1/models", timeout=5)
        if response.status_code == 200:
            print(f"   ✅ GPT4All 服务运行中")
            return True
        else:
            print(f"   ❌ GPT4All 服务异常: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ 无法连接到 GPT4All (http://localhost:4891)")
        print(f"   💡 提示: 在 GPT4All 中启用 API Server")
        return False
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        return False

def main():
    print("=" * 60)
    print("🧪 本地模型测试工具")
    print("=" * 60)
    print()
    
    results = {
        "ollama": test_ollama(),
        "lm_studio": test_lm_studio(),
        "gpt4all": test_gpt4all()
    }
    
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)
    
    for name, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {name.upper()}")
    
    print("\n💡 提示:")
    print("   - 如果所有测试都失败，请先安装并启动至少一个本地模型解决方案")
    print("   - Ollama: https://ollama.com")
    print("   - LM Studio: https://lmstudio.ai")
    print("   - GPT4All: https://gpt4all.io")
    print()
    
    # 保存结果
    result_file = Path.home() / ".qclaw" / "workspace" / "wiki" / "scripts" / "test_results.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(result_file, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": results
        }, f, indent=2)
    
    print(f"📝 结果已保存到: {result_file}")

if __name__ == "__main__":
    main()
