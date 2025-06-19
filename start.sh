#!/bin/bash

# 確保所有依賴都已安裝
pip3 install -r requirements.txt

# 設置 Python 命令別名
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: No Python interpreter found!"
    exit 1
fi

# 嘗試使用 gunicorn，如果失敗則使用 Flask 開發服務器
if command -v gunicorn &> /dev/null; then
    echo "Starting with gunicorn..."
    exec gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 4
else
    echo "Gunicorn not found, starting with Flask development server..."
    exec $PYTHON_CMD app.py
fi 