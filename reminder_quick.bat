@echo off
chcp 65001 > nul
echo ===================================
echo   Quick Reminder - 快速提醒设置
echo ===================================
echo.

cd /d "%~dp0"
python reminder_ui.py

echo.
echo 提醒UI已关闭。
pause
