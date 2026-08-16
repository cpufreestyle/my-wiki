#!/usr/bin/env python3
"""wiki_data.py — MyWiki 桌面版业务逻辑（无 GUI 依赖）

包含情绪关键词、标签提取与日记 / 心情 / 提醒的数据读写，
可独立于 PySide6 导入使用（便于单元测试）。

命名注意：不可叫 wiki_core —— modules/shared-wiki/ 下已有同名模块，
Share 标签页经 sys.path.insert 动态加载，重名会被 sys.modules 缓存遮蔽。
"""
import json
import os
import re
from collections import Counter
from datetime import datetime

from wiki_paths import DAILY_DIR, MOOD_DIR, REMINDER_DIR, REMINDER_FILE

# ==================== MOOD KEYWORDS ====================
MOOD_KEYWORDS = {
    "开心": ["开心", "高兴", "快乐", "喜悦", "顺利", "成功", "完美", "太好了", "哈哈", "精彩", "满意", "棒", "赞", "好玩", "有趣", "好吃", "舒服", "放松", "享受", "愉快", "不错", "挺好的", "喜欢", "爱", "谢", "感谢", "酷", "帅", "美", "值得", "收获"],
    "平静": ["还行", "普通", "正常", "一般", "平静", "还好", "日常", "无特别", "没什么", "老样子", "照常", "平淡", "安静", "稳定", "规律"],
    "低落": ["难过", "伤心", "失望", "沮丧", "累", "困", "不舒服", "难受", "糟糕", "完蛋", "郁闷", "疲惫", "好累", "无聊", "烦闷", "心痛", "委屈", "倒霉", "不顺", "挫折", "失败", "放弃", "孤独", "寂寞", "想哭", "哭", "累死", "不想"],
    "兴奋": ["激动", "兴奋", "期待", "刺激", "太棒了", "厉害", "惊艳", "震撼", "太好了", "哇", "牛", "强", "爽", "燃", "沸腾", "迫不及待", "终于"],
    "焦虑": ["担心", "焦虑", "压力", "烦", "头疼", "麻烦", "纠结", "犹豫", "紧迫", "急", "紧张", "害怕", "恐惧", "慌", "不安", "心烦", "烦躁", "压力大", "赶", "来不及", "怎么办"]
}
NEGATION_WORDS = ["不", "没", "别", "无", "非", "不太", "不怎么"]
MOOD_EMOJI = {"开心": "😊", "平静": "😐", "低落": "😢", "兴奋": "🔥", "焦虑": "😰"}

STOP_WORDS = set([
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也",
    "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这",
    "今天", "明天", "昨天", "然后", "这个", "那个", "什么", "怎么", "为什么",
    "觉得", "感觉", "想", "认为", "知道", "可以", "可能", "应该", "需要",
    "一下", "一点", "一些", "几个", "多少", "很多", "非常", "特别", "真的",
    "还是", "但是", "不过", "而且", "或者", "因为", "所以", "如果", "虽然",
    "已经", "正在", "将要", "曾经", "一直", "总是", "刚刚", "刚才", "现在",
    "里面", "外面", "上面", "下面", "这里", "那里",
    "事情", "东西", "地方", "时候", "样子", "方面", "问题",
    "比较", "更", "最", "太", "挺", "蛮", "稍微", "有点",
    "开始", "继续", "结束", "完成", "进行", "发生", "出现", "变得"
])

DOMAIN_KEYWORDS = [
    "万达", "商场", "公园", "医院", "学校", "公司", "家", "办公室", "餐厅",
    "唱歌", "跳舞", "看电影", "逛街", "购物", "运动", "健身", "跑步", "游泳",
    "开会", "加班", "写代码", "调试", "测试", "部署", "上线", "修复", "优化",
    "朋友", "同事", "家人", "老板", "客户", "老师", "同学",
    "开心", "难过", "兴奋", "焦虑", "平静", "愤怒",
    "Python", "JavaScript", "React", "Vue", "Git", "Docker", "AI", "LLM"
]

# ==================== CORE FUNCTIONS ====================
def get_today():
    """今天的日期字符串（YYYY-MM-DD）。"""
    return datetime.now().strftime("%Y-%m-%d")


def get_now():
    """当前时间字符串（HH:MM:SS）。"""
    return datetime.now().strftime("%H:%M:%S")


def load_daily(date):
    """读取指定日期的日记，不存在时返回模板。"""
    path = os.path.join(DAILY_DIR, f"{date}.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"# {date} Diary\n\n"


def save_daily(date, content):
    """保存指定日期的日记。"""
    os.makedirs(DAILY_DIR, exist_ok=True)
    path = os.path.join(DAILY_DIR, f"{date}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def analyze_mood(text):
    """基于关键词的情绪分析，返回 (情绪, 置信度, 命中词说明)。"""
    mood_scores = {m: 0 for m in MOOD_KEYWORDS}
    matched = {m: [] for m in MOOD_KEYWORDS}
    for mood, keywords in MOOD_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                idx = text.find(kw)
                ctx = text[max(0, idx - 4):idx]
                if not any(neg in ctx for neg in NEGATION_WORDS):
                    mood_scores[mood] += 1
                    matched[mood].append(kw)
    best = max(mood_scores.items(), key=lambda x: x[1])
    if best[1] == 0:
        return "平静", 0.3, "未检测到明显情绪词"
    conf = min(best[1] / 3.0, 1.0)
    return best[0], conf, ", ".join(matched[best[0]])


def save_mood(date, mood, text, confidence, reason):
    """追加一条心情记录到 mood/<date>.json。"""
    os.makedirs(MOOD_DIR, exist_ok=True)
    path = os.path.join(MOOD_DIR, f"{date}.json")
    records = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
    records.append({
        "time": get_now(), "mood": mood, "text": text[:100],
        "confidence": round(confidence, 2), "reason": reason
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def load_moods(date):
    """读取指定日期的心情记录列表。"""
    path = os.path.join(MOOD_DIR, f"{date}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def extract_tags(text, top_n=5):
    """从文本提取标签：领域词优先 + 词频统计。"""
    words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', text)
    words = [w for w in words if w not in STOP_WORDS and 2 <= len(w) <= 4 and not w.isdigit()]
    counts = Counter(words)
    domain = [(kw, 10) for kw in DOMAIN_KEYWORDS if kw in text]
    normal = counts.most_common(top_n * 2)
    all_kw = sorted(domain + normal, key=lambda x: x[1], reverse=True)
    return [t[0] for t in all_kw[:top_n]]


def load_reminders():
    """读取提醒列表。"""
    if os.path.exists(REMINDER_FILE):
        with open(REMINDER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_reminders(reminders):
    """保存提醒列表。"""
    os.makedirs(REMINDER_DIR, exist_ok=True)
    with open(REMINDER_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)


def add_reminder(remind_at, message):
    """新增一条提醒并落盘，返回新建的提醒 dict。"""
    reminders = load_reminders()
    rid = max([r["id"] for r in reminders], default=0) + 1
    reminder = {
        "id": rid,
        "remind_at": remind_at.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending",
    }
    reminders.append(reminder)
    save_reminders(reminders)
    return reminder


def cancel_reminder(rid):
    """取消一条待提醒记录，返回是否成功。"""
    reminders = load_reminders()
    for r in reminders:
        if r["id"] == rid and r["status"] == "pending":
            r["status"] = "cancelled"
            save_reminders(reminders)
            return True
    return False
