#!/bin/bash
# MyWiki 一键启动（macOS）
# 每次都会先关闭已运行的旧实例，确保跑的是最新代码。

# 关闭旧实例（避免双击 app 那种"只聚焦旧窗口"的问题）
pkill -f "wiki_app.py" 2>/dev/null
sleep 1

cd "/Users/a1-6/AI Shared/repo/my-wiki" || exit 1

# 优先用项目虚拟环境 .venv（已装 mcp 等依赖），其次回退到系统 Python
VENV="/Users/a1-6/AI Shared/repo/my-wiki/.venv/bin/python"
if [ -x "$VENV" ]; then
  PY="$VENV"
else
  PY="/Users/a1-6/.local/bin/python3.12"
  [ -x "$PY" ] || PY="/usr/bin/python3"
fi

# 记住本终端窗口 ID，程序退出后关闭它（不再用 exec，以便脚本能继续执行收尾）
WID=$(osascript -e 'tell application "Terminal" to id of front window' 2>/dev/null)

echo "▶ 正在启动 MyWiki ..."
"$PY" wiki_app.py

# 程序已退出：关闭启动它的终端窗口
if [ -n "$WID" ]; then
  osascript -e "tell application \"Terminal\" to close window id $WID" 2>/dev/null
fi
