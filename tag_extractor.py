#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标签提取器
从文本中智能提取标签
"""
import re
from config import WIKI_DIR

# ===== 内置标签库 =====
STOP_WORDS = {
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "它", "他", "她", "们", "这个", "那个", "什么", "怎么",
    "为", "而", "与", "或", "但", "如果", "因为", "所以", "可以", "这样", "那样"
}

DOMAIN_TAGS = {
    # 领域标签
    "AI/ML": ["AI", "机器学习", "深度学习", "神经网络", "GPT", "LLM", "大模型", "RAG", "NLP", "TensorFlow", "PyTorch"],
    "Python": ["Python", "pip", "venv", "Django", "Flask", "FastAPI", "PyQt", "asyncio"],
    "Web开发": ["HTML", "CSS", "JavaScript", "React", "Vue", "Angular", "Node.js", "API", "REST", "GraphQL"],
    "游戏开发": ["Unity", "Unreal", "Godot", "Pygame", "Shader", "3D", "2D", "物理引擎", "关卡设计"],
    "移动开发": ["Android", "iOS", "Flutter", "React Native", "Kotlin", "Swift", "小程序"],
    "DevOps": ["Docker", "Kubernetes", "CI/CD", "Jenkins", "GitHub Actions", "Linux", "Shell", "Nginx"],
    "数据库": ["MySQL", "PostgreSQL", "MongoDB", "Redis", "SQLite", "ORM", "数据库"],
    "嵌入式": ["Arduino", "ESP32", "Raspberry Pi", "STM32", "单片机", "GPIO", "嵌入式"],
    "工具": ["Git", "VSCode", "Vim", "Markdown", "正则", "正则表达式"],
    "阅读": ["读书", "书评", "Paper", "论文", "文章", "阅读", "技术文章"],
}

def extract_keywords(text, top_n=5):
    """提取高频实词作为关键词"""
    # 分词（简单按字符，保留2-4字词）
    words = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
    
    # 过滤停用词和单字
    filtered = [w for w in words if w not in STOP_WORDS]
    
    # 统计词频
    freq = {}
    for w in filtered:
        freq[w] = freq.get(w, 0) + 1
    
    # 返回 top_n
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:top_n]]

def extract_domain_tags(text):
    """匹配领域标签"""
    matched = []
    for domain, keywords in DOMAIN_TAGS.items():
        if any(kw in text for kw in keywords):
            matched.append(domain)
    return matched

def extract_hashtags(text):
    """提取 #标签 格式的标签"""
    tags = re.findall(r'#([^\s#]+)', text)
    return list(set(tags))

def extract_all(text, top_n=5):
    """综合提取所有类型的标签"""
    hashtags = extract_hashtags(text)
    domains  = extract_domain_tags(text)
    keywords = extract_keywords(text, top_n)
    
    return {
        "hashtags": hashtags,
        "domains": domains,
        "keywords": keywords,
        "all": list(set(hashtags + domains + keywords))[:10]
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        result = extract_all(text)
        print(f"标签: {result['all']}")
        print(f"领域: {result['domains']}")
        print(f"关键词: {result['keywords']}")
