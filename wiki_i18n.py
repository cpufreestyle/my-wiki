#!/usr/bin/env python3
"""wiki_i18n.py — MyWiki 桌面版多语言文案

维护中英文界面文案与翻译函数 t()。
LANG 是运行时可切换的全局状态，外部统一通过 set_lang()/get_lang() 访问，
避免 `from wiki_i18n import LANG` 拿到导入时的快照。
"""

LANG = "zh"

I18N = {
    "zh": {
        "app_title": "我的知识库",
        "tab_diary": "  日记  ", "tab_mood": "  心情  ",
        "tab_reminder": "  提醒  ", "tab_share": "  共享  ",
        "ready": "就绪", "lang_btn": "EN",
        "template": "模板", "tags": "标签", "save": "  保存  ",
        "diary_saved": "日记已保存", "extracted_tags": "已提取 {n} 个标签",
        "no_tags": "未找到标签", "no_keywords": "未发现关键词",
        "mood_q": "  今天感觉如何？", "auto_analyze": "  自动分析  ",
        "today_records": "  今日记录", "no_records": "  今日暂无记录。",
        "type_first": "请先输入内容！", "mood_saved": "心情已保存：{m}",
        "voice": "🎤 语音", "voice_stop": "⏹ 停止",
        "voice_autosave": "识别后自动保存", "voice_filled": "已填入，请检查后保存",
        "voice_missing_ffmpeg": "ffmpeg（录音）", "voice_missing_sr": "SpeechRecognition（识别）",
        "voice_confirm_install": "缺少语音依赖：{n}\n\n是否自动安装？（需要联网，使用 pip）",
        "voice_installing": "正在安装语音依赖…", "voice_install_ok": "语音依赖已就绪",
        "voice_install_fail": "语音依赖安装失败，请手动安装：",
        "voice_recording": "正在聆听…（最多 {n} 秒）",
        "voice_recognizing": "识别中…", "voice_done": "已识别语音",
        "voice_cancel": "已取消", "voice_empty": "没听清，请再说一次。",
        "voice_netfail": "识别服务不可用（需联网）",
        "voice_need_ffmpeg": "语音功能需要 ffmpeg（用于录音）\n\n请先安装：\n  brew install ffmpeg\n\n安装后重试。",
        "voice_need_sr": "语音识别需要 Python 包 SpeechRecognition\n\n请安装：\n  {py} -m pip install SpeechRecognition\n\n识别使用 Google 在线接口，需要联网。",
        "mic_perm_btn": "🔧",
        "mic_perm_title": "麦克风权限",
        "mic_perm_help": "若录音失败或提示「麦克风权限被拒绝」：\n\n1) 打开「系统设置 › 隐私与安全性 › 麦克风」，给运行本程序的终端/应用开启权限；\n2) 或点击下方「一键重置」清空授权，重启后重新弹窗允许；\n3) 完全退出 MyWiki 后重新打开再试。",
        "mic_perm_reset": "🔄 一键重置麦克风权限",
        "mic_perm_reset_ok": "已重置麦克风授权。请完全退出 MyWiki 并重新打开，首次录音会重新请求权限，请点「允许」。",
        "mic_perm_reset_fail": "重置失败（可能无需重置，或需手动操作）。请手动到「系统设置 › 隐私与安全性 › 麦克风」开启权限。",
        "mic_perm_only_mac": "一键重置仅支持 macOS。请手动到「系统设置 › 隐私与安全性 › 麦克风」开启权限。",
        "close": "关闭",
        "quick_reminders": "  快捷提醒", "custom": "自定义：",
        "add": "添加", "pending": "  待提醒", "cancel_id": "取消编号：",
        "cancel": "取消", "no_pending": "  暂无待提醒。",
        "enter_msg": "请先输入提醒内容！", "bad_time": "时间格式错误（HH:MM）",
        "enter_id": "请输入有效编号", "reminder_set": "提醒已设置：{t} - {m}",
        "reminder_cancelled": "提醒 #{i} 已取消", "cannot_cancel": "无法取消 #{i}",
        "tmr9": "明天9点", "tmr18": "明天18点",
        "settings_btn": "⚙️", "settings_title": "界面设置",
        "settings_card_spacing": "卡片行间距：", "settings_card_padding": "卡片内边距：",
        "share_title": "🌐 共享知识库 — Obsidian × 所有 Agent",
        "refresh": "刷新", "start_server": "▶ 启动 MCP 服务",
        "open_obsidian": "🔭 在 Obsidian 打开", "broadcast": "🔔 通知 Agent",
        # 新增标签页
        "tab_todo": "  待办  ", "tab_search": "  搜索  ",
        "tab_tags": "  标签  ", "tab_report": "  报告  ",
        # 待办
        "todo_add": "  新增待办", "todo_list": "  待办清单",
        "todo_ph": "要做什么…", "todo_due_ph": "截止 YYYY-MM-DD",
        "todo_empty": "  暂无待办，添加一条吧。",
        "todo_need_text": "请先输入待办内容！", "todo_added": "待办已添加",
        "pri_high": "高", "pri_medium": "中", "pri_low": "低",
        # 搜索
        "search_ph": "搜索笔记…", "search_btn": "  搜索  ",
        "search_no_result": "  没有找到匹配的笔记。",
        "search_results": "  找到 {n} 条结果", "search_need_kw": "请输入搜索关键词！",
        # 标签
        "tags_title": "  标签云", "tags_empty": "  暂无标签。",
        "tags_notes": "  含标签「{tag}」的笔记", "tags_count": "{n} 篇",
        # 报告
        "report_title": "  周报 / 月报", "report_weekly": "周报（近 7 天）",
        "report_monthly": "月报（本月）", "report_generate": "  生成报告  ",
        "report_save": "  保存到知识库  ", "report_saved": "报告已保存：{p}",
        "report_copy": "  复制  ", "report_copied": "报告已复制到剪贴板",
    },
    "en": {
        "app_title": "My Wiki",
        "tab_diary": "  Diary  ", "tab_mood": "  Mood  ",
        "tab_reminder": "  Reminder  ", "tab_share": "  Share  ",
        "ready": "Ready", "lang_btn": "中",
        "template": "Template", "tags": "Tags", "save": "  Save  ",
        "diary_saved": "Diary saved", "extracted_tags": "Extracted {n} tags",
        "no_tags": "No tags found", "no_keywords": "No keywords found",
        "mood_q": "  How are you feeling?", "auto_analyze": "  Auto Analyze  ",
        "today_records": "  Today's Records", "no_records": "  No records today yet.",
        "type_first": "Type something first!", "mood_saved": "Mood saved: {m}",
        "voice": "🎤 Voice", "voice_stop": "⏹ Stop",
        "voice_autosave": "Auto-save after recognition", "voice_filled": "Filled in — review then save",
        "voice_missing_ffmpeg": "ffmpeg (recording)", "voice_missing_sr": "SpeechRecognition (recognition)",
        "voice_confirm_install": "Missing voice deps: {n}\n\nAuto-install now? (needs internet, uses pip)",
        "voice_installing": "Installing voice deps…", "voice_install_ok": "Voice deps ready",
        "voice_install_fail": "Voice deps install failed. Manual install:",
        "voice_recording": "Listening… (max {n}s)",
        "voice_recognizing": "Recognizing…", "voice_done": "Voice recognized",
        "voice_cancel": "Cancelled", "voice_empty": "Couldn't hear that, try again.",
        "voice_netfail": "Recognition service unavailable (needs internet)",
        "voice_need_ffmpeg": "Voice needs ffmpeg (for recording)\n\nInstall it:\n  brew install ffmpeg\n\nThen retry.",
        "voice_need_sr": "Voice recognition needs SpeechRecognition\n\nInstall:\n  {py} -m pip install SpeechRecognition\n\nUses Google's online API (needs internet).",
        "mic_perm_btn": "🔧",
        "mic_perm_title": "Microphone Permission",
        "mic_perm_help": "If recording fails or you see 'microphone permission denied':\n\n1) Open System Settings › Privacy & Security › Microphone and enable the app;\n2) Or click 'Reset' below to clear authorization;\n3) Fully quit MyWiki and reopen before retrying.",
        "mic_perm_reset": "🔄 Reset Microphone Permission",
        "mic_perm_reset_ok": "Microphone authorization reset. Fully quit MyWiki, reopen, and allow access when prompted.",
        "mic_perm_reset_fail": "Reset failed. Please enable microphone in System Settings › Privacy & Security › Microphone.",
        "mic_perm_only_mac": "One-click reset is macOS only. Please enable microphone manually.",
        "close": "Close",
        "quick_reminders": "  Quick Reminders", "custom": "Custom:",
        "add": "Add", "pending": "  Pending", "cancel_id": "Cancel ID:",
        "cancel": "Cancel", "no_pending": "  No pending reminders.",
        "enter_msg": "Enter a message first!", "bad_time": "Invalid time format (HH:MM)",
        "enter_id": "Enter valid ID", "reminder_set": "Reminder set: {t} - {m}",
        "reminder_cancelled": "Reminder #{i} cancelled", "cannot_cancel": "Cannot cancel #{i}",
        "tmr9": "Tomorrow 9am", "tmr18": "Tomorrow 6pm",
        "settings_btn": "⚙️", "settings_title": "UI Settings",
        "settings_card_spacing": "Card line spacing:", "settings_card_padding": "Card padding:",
        "share_title": "🌐 Shared Wiki — Obsidian × All Agents",
        "refresh": "Refresh", "start_server": "▶ Start MCP Server",
        "open_obsidian": "🔭 Open in Obsidian", "broadcast": "🔔 Notify Agents",
        # New tabs
        "tab_todo": "  Todo  ", "tab_search": "  Search  ",
        "tab_tags": "  Tags  ", "tab_report": "  Report  ",
        # Todo
        "todo_add": "  Add Todo", "todo_list": "  Todo List",
        "todo_ph": "What to do…", "todo_due_ph": "Due YYYY-MM-DD",
        "todo_empty": "  No todos yet. Add one!",
        "todo_need_text": "Enter todo text first!", "todo_added": "Todo added",
        "pri_high": "High", "pri_medium": "Medium", "pri_low": "Low",
        # Search
        "search_ph": "Search notes…", "search_btn": "  Search  ",
        "search_no_result": "  No matching notes found.",
        "search_results": "  {n} result(s)", "search_need_kw": "Enter a keyword!",
        # Tags
        "tags_title": "  Tag Cloud", "tags_empty": "  No tags yet.",
        "tags_notes": "  Notes tagged “{tag}”", "tags_count": "{n} notes",
        # Report
        "report_title": "  Weekly / Monthly", "report_weekly": "Weekly (last 7 days)",
        "report_monthly": "Monthly (this month)", "report_generate": "  Generate  ",
        "report_save": "  Save to Vault  ", "report_saved": "Report saved: {p}",
        "report_copy": "  Copy  ", "report_copied": "Report copied to clipboard",
    },
}


def set_lang(lang):
    """切换界面语言（'zh' / 'en'）。"""
    global LANG
    LANG = lang


def get_lang():
    """读取当前界面语言。"""
    return LANG


def t(key, **kw):
    """按当前语言取文案；缺失时回退中文，再缺失则原样返回 key。"""
    s = I18N.get(LANG, I18N["zh"]).get(key, key)
    return s.format(**kw) if kw else s
