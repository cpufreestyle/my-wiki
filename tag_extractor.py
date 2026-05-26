#!/usr/bin/env python3
"""
Tag Extractor - 标签提取器
从日记文本中自动提取关键词/标签
"""
import re
import json
import os
from datetime import datetime
from collections import Counter

DAILY_DIR = r"D:\Users\michael\MyWiki\daily"

# 停用词列表（常见无意义词）
STOP_WORDS = set([
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这",
    "今天", "明天", "昨天", "然后", "这个", "那个", "什么", "怎么", "为什么", "哪", "哪里", "什么时候",
    "觉得", "感觉", "想", "觉得", "认为", "知道", "可以", "可能", "应该", "需要",
    "一下", "一点", "一些", "几个", "多少", "许多", "很多", "非常", "特别", "真的", "真是",
    "还是", "但是", "不过", "而且", "或者", "因为", "所以", "如果", "虽然", "即使",
    "已经", "正在", "将要", "曾经", "一直", "总是", "从来", "刚刚", "刚才", "现在", "以后", "之前",
    "里面", "外面", "上面", "下面", "左边", "右边", "前面", "后面", "这里", "那里",
    "事情", "东西", "地方", "时候", "样子", "方面", "问题", "办法", "原因", "结果",
    "比较", "更", "最", "太", "挺", "蛮", "稍微", "有点", "一点", "越来越",
    "开始", "继续", "结束", "完成", "进行", "发生", "出现", "变得", "变得", "变得"
])

# 领域关键词（优先提取）
DOMAIN_KEYWORDS = [
    # 地点
    "万达", "商场", "公园", "医院", "学校", "公司", "家", "办公室", "餐厅", "咖啡厅",
    # 活动
    "唱歌", "跳舞", "看电影", "逛街", "购物", "运动", "健身", "跑步", "游泳", "打球",
    # 工作
    "开会", "加班", "写代码", "调试", "测试", "部署", "上线", "修复", "优化",
    # 人物
    "朋友", "同事", "家人", "老板", "客户", "老师", "同学",
    # 情绪
    "开心", "难过", "兴奋", "焦虑", "平静", "愤怒", "惊讶",
    # 技术相关
    "Python", "JavaScript", "React", "Vue", "Node", "Git", "Docker", "AI", "LLM", "GPT"
]

def extract_keywords(text, top_n=5):
    """
    从文本中提取关键词
    返回: [(keyword, score), ...]
    """
    # 简单分词（按标点和空格分割）
    words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', text)
    
    # 过滤停用词、单字、纯数字、过长词
    words = [w for w in words if w not in STOP_WORDS and len(w) >= 2 and len(w) <= 4 and not w.isdigit()]
    
    # 统计词频
    word_counts = Counter(words)
    
    # 优先提取领域关键词
    domain_keywords_found = []
    for keyword in DOMAIN_KEYWORDS:
        if keyword in text:
            domain_keywords_found.append((keyword, 10))  # 领域关键词高分
    
    # 普通关键词（按词频）
    normal_keywords = [(word, count) for word, count in word_counts.most_common(top_n * 2)]
    
    # 合并并排序
    all_keywords = domain_keywords_found + normal_keywords
    all_keywords = sorted(all_keywords, key=lambda x: x[1], reverse=True)
    
    # 返回前 top_n 个
    return all_keywords[:top_n]

def add_tags_to_daily(date, tags):
    """
    在日记文件开头添加标签
    """
    filename = f"{DAILY_DIR}/{date}.md"
    
    if not os.path.exists(filename):
        print(f"Error: {filename} not found")
        return False
    
    # 读取现有内容
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 检查是否已有标签
    if content.startswith("#标签:"):
        print(f"Tags already exist in {filename}")
        return False
    
    # 添加标签到开头
    tag_line = f"#标签: {', '.join([t[0] for t in tags])}\n\n"
    new_content = tag_line + content
    
    # 保存
    with open(filename, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"Tags added to {filename}: {[t[0] for t in tags]}")
    return True

def extract_and_save_tags(date):
    """
    从日记提取标签并保存
    """
    filename = f"{DAILY_DIR}/{date}.md"
    
    if not os.path.exists(filename):
        print(f"Error: {filename} not found")
        return []
    
    # 读取日记内容
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 提取关键词
    keywords = extract_keywords(content, top_n=5)
    
    if not keywords:
        print(f"No keywords found in {filename}")
        return []
    
    # 添加标签到日记
    add_tags_to_daily(date, keywords)
    
    return keywords

if __name__ == "__main__":
    # 测试
    print("Testing tag extractor...")
    print()
    
    # 提取今天的标签
    today = datetime.now().strftime("%Y-%m-%d")
    keywords = extract_and_save_tags(today)
    
    if keywords:
        print(f"\nExtracted keywords for {today}:")
        for keyword, score in keywords:
            print(f"  - {keyword} (score: {score})")
    else:
        print(f"No keywords extracted for {today}")
