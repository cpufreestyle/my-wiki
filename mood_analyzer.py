#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
心情分析器
基于关键词统计分析文本情绪
"""
import os
import json
import re
from datetime import datetime
from config import MOOD_DIR

# ===== 情绪词典 =====
POSITIVE_WORDS = [
    "开心", "快乐", "高兴", "兴奋", "激动", "满足", "幸福", "美好",
    "成功", "突破", "进步", "成长", "收获", "成就", "顺利", "圆满",
    "期待", "希望", "惊喜", "感恩", "感谢", "棒", "赞", "厉害",
    "解决", "完成", "优化", "提升", "创新", "漂亮"
]

NEGATIVE_WORDS = [
    "难过", "伤心", "沮丧", "失望", "郁闷", "焦虑", "压力", "疲惫",
    "累", "辛苦", "难", "烦", "糟", "差", "烂", "问题", "bug",
    "错误", "失败", "挫折", "拖延", "头疼", "无奈", "崩溃", "死机",
    "挂", "炸", "废", "慢", "卡", "难用", "坑"
]

MOOD_KEYWORDS = {
    "开心": ["开心", "快乐", "高兴", "happy", "joy", "棒", "赞", "厉害"],
    "悲伤": ["难过", "伤心", "sad", "depressed", "沮丧", "郁闷"],
    "焦虑": ["焦虑", "anxious", "worried", "紧张", "压力", "头疼"],
    "疲惫": ["累", "疲惫", "tired", "exhausted", "困", "疲惫"],
    "兴奋": ["兴奋", "excited", "激动", "期待", "兴奋"],
}

def analyze_mood(text):
    """分析文本情绪，返回 (mood, confidence, matched_keywords)"""
    text_lower = text.lower()
    matched_pos = [w for w in POSITIVE_WORDS if w in text]
    matched_neg = [w for w in NEGATIVE_WORDS if w in text]
    
    score = len(matched_pos) - len(matched_neg)
    
    if score > 0:
        mood = "positive"
        confidence = min(score * 0.2, 0.9)
    elif score < 0:
        mood = "negative"
        confidence = min(abs(score) * 0.2, 0.9)
    else:
        mood = "neutral"
        confidence = 0.5
    
    return mood, confidence, matched_pos + matched_neg

def save_mood(date, mood, confidence):
    """保存当日心情记录"""
    MOOD_DIR.mkdir(parents=True, exist_ok=True)
    filepath = MOOD_DIR / f"{date}.json"
    
    data = {
        "date": date,
        "mood": mood,
        "confidence": round(confidence, 2),
        "timestamp": datetime.now().isoformat()
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return data

def get_mood(date):
    """获取指定日期的心情记录"""
    filepath = MOOD_DIR / f"{date}.json"
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def get_recent_moods(days=7):
    """获取最近 N 天的心情记录"""
    moods = []
    today = datetime.now()
    
    for i in range(days):
        d = today - __import__('datetime').timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        mood = get_mood(date_str)
        if mood:
            moods.append(mood)
    
    return moods

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        mood, conf, kw = analyze_mood(text)
        print(f"心情: {mood}, 置信度: {conf:.2f}, 关键词: {kw}")
