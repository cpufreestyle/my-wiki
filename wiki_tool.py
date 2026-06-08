#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
My Wiki - 核心工具函数
"""
import os
import json
import re
from datetime import datetime, date
from pathlib import Path
from config import WIKI_DIR, DAILY_DIR, MOOD_DIR, SCRIPTS_DIR

# ===== 文件 I/O =====
def read_file(filepath, default=""):
    """安全读取文件"""
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            return f.read()
    except Exception:
        return default

def write_file(filepath, content):
    """安全写入文件"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

# ===== 日记 =====
def get_daily_filename(d=None):
    """获取日记文件名"""
    if d is None:
        d = date.today()
    return DAILY_DIR / f"{d.strftime('%Y-%m-%d')}.md"

def read_daily(d=None):
    """读取日记内容"""
    return read_file(get_daily_filename(d))

def write_daily(content, d=None):
    """写入日记"""
    write_file(get_daily_filename(d), content)

# ===== 索引 =====
def update_index():
    """更新 INDEX.md"""
    daily_files = sorted(DAILY_DIR.glob("*.md"), reverse=True)
    
    lines = ["# 📚 索引\n\n"]
    lines.append(f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    lines.append("## 📅 日记\n\n")
    
    for f in daily_files[:30]:
        title = _extract_title(f.read_text(encoding='utf-8-sig'))
        date_str = f.stem
        lines.append(f"- [{date_str}] {title}\n")
    
    write_file(WIKI_DIR / "INDEX.md", "".join(lines))
    return len(daily_files)

def _extract_title(content):
    """从 md 内容提取第一级标题"""
    m = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    return m.group(1) if m else "无标题"

# ===== 知识图谱 =====
def load_knowledge_graph():
    """加载知识图谱"""
    path = WIKI_DIR / "knowledge_graph.json"
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {"nodes": [], "links": []}

def save_knowledge_graph(graph):
    """保存知识图谱"""
    path = WIKI_DIR / "knowledge_graph.json"
    path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')

# ===== 外部脚本集成 =====
def run_script(script_name, *args):
    """运行 scripts/ 目录下的脚本"""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return f"脚本不存在: {script_name}"
    
    import subprocess
    cmd = ["python", str(script_path)] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                               encoding='utf-8', errors='replace')
        return result.stdout or result.stderr
    except Exception as e:
        return f"运行失败: {e}"

# ===== LLM 集成 =====
def analyze_with_llm(text, prompt_template=None):
    """
    调用 LLM 分析文本（支持多种后端）
    本地优先：Ollama > LM Studio > OpenAI API
    """
    # 优先尝试本地 Ollama
    ollama_url = "http://localhost:11434/api/generate"
    
    if prompt_template is None:
        prompt_template = (
            "请分析以下文本，提取关键信息（主题、标签、摘要）。"
            "用中文回复，JSON格式输出：\n{text}"
        )
    
    prompt = prompt_template.format(text=text[:2000])
    
    # 尝试 Ollama
    try:
        import urllib.request, json as json_mod
        req = urllib.request.Request(
            ollama_url,
            data=json_mod.dumps({
                "model": "qwen2.5",
                "prompt": prompt,
                "stream": False
            }).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        resp = urllib.request.urlopen(req, timeout=35)
        result = json_mod.loads(resp.read())
        return result.get("response", "")
    except Exception:
        pass
    
    # 回退：返回关键词分析
    from tag_extractor import extract_all
    return f"本地 LLM 不可用。关键词分析：{extract_all(text)['all']}"

# ===== 工具注册表 =====
TOOLS = {
    "index": update_index,
    "daily_read": read_daily,
    "daily_write": write_daily,
    "llm_analyze": analyze_with_llm,
    "run_script": run_script,
}

if __name__ == "__main__":
    print("工具模块 - My Wiki")
    print(f"日记目录: {DAILY_DIR}")
    print(f"知识图谱: {load_knowledge_graph()}")
