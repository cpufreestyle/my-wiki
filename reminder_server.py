#!/usr/bin/env python3
"""
Simple HTTP server for reminder web UI
"""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os
import sys
from datetime import datetime, timedelta
import threading
import time

# 添加wiki目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reminder_manager import add_reminder, load_reminders

class ReminderHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/reminders/pending':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            reminders = load_reminders()
            pending = [r for r in reminders if r['status'] == 'pending']
            self.wfile.write(json.dumps(pending, ensure_ascii=False).encode('utf-8'))
        else:
            # 默认返回静态文件
            super().do_GET()
    
    def do_POST(self):
        if self.path == '/api/reminders':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            remind_at = datetime.fromisoformat(data['remind_at'].replace('Z', '+00:00'))
            message = data['message']
            
            reminder = add_reminder(remind_at, message)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(reminder, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        # 静默日志
        pass

def run_server(port=8080):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = HTTPServer(('localhost', port), ReminderHandler)
    print(f"服务器启动：<INTERNAL_LINK_REMOVED>")
    server.serve_forever()

if __name__ == '__main__':
    run_server()
