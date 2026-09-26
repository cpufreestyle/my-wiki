#!/bin/bash
# launch_web.sh — 启动 MyWiki 网页版并在默认浏览器打开
# 已在运行则直接打开浏览器；供桌面 .app 快捷方式调用，也可直接执行。
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${MYWIKI_PORT:-8082}"
URL="http://127.0.0.1:${PORT}/"

if [ -x "$REPO/.venv/bin/python" ]; then
  PY="$REPO/.venv/bin/python"
elif [ -x "/Users/a1-6/.local/bin/python3.12" ]; then
  PY="/Users/a1-6/.local/bin/python3.12"
else
  PY="/usr/bin/python3"
fi

if ! curl -s -o /dev/null --max-time 2 "$URL"; then
  echo "▶ 启动 MyWiki 网页版 (:$PORT) ..."
  cd "$REPO" || exit 1
  # nohup + disown：启动器（.app）退出后服务由 launchd 收养，继续运行。
  # 注意：macOS 没有 setsid 命令，勿用。
  nohup "$PY" web_server.py > /tmp/mywiki-web.log 2>&1 < /dev/null &
  disown 2>/dev/null || true
  for _ in $(seq 1 20); do
    sleep 0.5
    curl -s -o /dev/null --max-time 2 "$URL" && break
  done
fi

open "$URL"
osascript -e "display notification \"网页版已在浏览器打开：$URL\" with title \"MyWiki\"" 2>/dev/null || true
exit 0
