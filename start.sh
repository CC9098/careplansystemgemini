#!/bin/bash

# 確保所有依賴都已安裝
pip install -r requirements.txt

# 嘗試使用 gunicorn，如果失敗則使用 Flask 開發服務器
if command -v gunicorn &> /dev/null; then
    echo "Starting with gunicorn..."
    exec gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 4
else
    echo "Gunicorn not found, starting with Flask development server..."
    exec python app.py
fi 