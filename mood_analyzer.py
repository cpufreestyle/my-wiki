#!/usr/bin/env python3
"""
Mood Analyzer - 心情分析器（改进版）
使用改进的关键词匹配 + 否定词处理
"""
import json
import os
from datetime import datetime

MOOD_DIR = r"D:\Users\michael\MyWiki\mood"

# 改进的关键词库（移除歧义词）
MOOD_KEYWORDS = {
    "开心": ["开心", "高兴", "快乐", "喜悦", "顺利", "成功", "完美", "太好了", "哈哈", "精彩", "满意", "棒", "赞"],
    "平静": ["还行", "普通", "正常", "一般", "平静", "还好", "不错", "可以", "日常", "无特别"],
    "低落": ["难过", "伤心", "失望", "沮丧", "累", "困", "不舒服", "难受", "糟糕", "完蛋", "郁闷", "疲惫", "好累"],
    "兴奋": ["激动", "兴奋", "期待", "刺激", "太棒了", "厉害", "惊艳", "震撼", "太好了"],
    "焦虑": ["担心", "焦虑", "压力", "烦", "头疼", "麻烦", "纠结", "犹豫", "紧迫", "焦虑"]
}

# 否定词列表
NEGATION_WORDS = ["不", "没", "别", "无", "非", "不太", "不怎么"]

def analyze_mood(text):
    """
    分析文本情绪（改进的关键词匹配）
    返回: (mood, confidence, reason)
    """
    text_lower = text.lower()
    mood_scores = {mood: 0 for mood in MOOD_KEYWORDS}
    matched_keywords = {mood: [] for mood in MOOD_KEYWORDS}
    
    # 关键词匹配
    for mood, keywords in MOOD_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                # 检查是否有否定词
                idx = text_lower.find(keyword)
                context_before = text_lower[max(0, idx-4):idx]
                
                has_negation = any(neg in context_before for neg in NEGATION_WORDS)
                if not has_negation:
                    mood_scores[mood] += 1
                    matched_keywords[mood].append(keyword)
    
    # 找出得分最高的情绪
    max_mood = max(mood_scores.items(), key=lambda x: x[1])
    
    # 如果没有匹配到任何关键词，返回"平静"
    if max_mood[1] == 0:
        return "平静", 0.5, "未匹配到明显情绪"
    
    # 置信度计算（基于匹配关键词数量）
    confidence = min(max_mood[1] / 3.0, 1.0)
    reason = f"关键词: {', '.join(matched_keywords[max_mood[0]])}"
    
    return max_mood[0], confidence, reason

def save_mood(date, mood, text, confidence=1.0, reason=""):
    """
    保存心情记录
    """
    if not os.path.exists(MOOD_DIR):
        os.makedirs(MOOD_DIR)
    
    filename = f"{MOOD_DIR}/{date}.json"
    
    # 读取已有记录
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []
    
    # 添加新记录
    record = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "mood": mood,
        "text": text[:100],  # 保存前100字
        "confidence": round(confidence, 2),
        "reason": reason
    }
    records.append(record)
    
    # 保存
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    
    return record

def get_mood_emoji(mood):
    """返回心情对应的emoji"""
    emoji_map = {
        "开心": "😊",
        "平静": "😐",
        "低落": "😢",
        "兴奋": "🔥",
        "焦虑": "😰"
    }
    return emoji_map.get(mood, "😐")

if __name__ == "__main__":
    # 测试
    test_texts = [
        "今天我和小丑一起去做了杂技表演",
        "好累啊，不想动",
        "终于完成了，太棒了！",
        "今天有点焦虑，事情太多了",
        "不太开心，有点烦",
        "心情不错，顺利完成任务"
    ]
    
    print("Testing improved mood analyzer...")
    print()
    
    for text in test_texts:
        mood, confidence, reason = analyze_mood(text)
        # Avoid Windows console encoding issues
        print(f"{mood} ({confidence:.2f}): {text}")
        print(f"   {reason}")
        save_mood("2026-05-23", mood, text, confidence, reason)
    
    print()
    print("Results saved to mood/2026-05-23.json")
