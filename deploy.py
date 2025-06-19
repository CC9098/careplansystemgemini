#!/usr/bin/env python3
"""
Railway 部署啟動腳本
確保所有依賴正確安裝並啟動應用
"""
import os
import sys
import subprocess

def install_dependencies():
    """安裝 Python 依賴"""
    print("Installing Python dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Dependencies installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        sys.exit(1)

def start_app():
    """啟動 Flask 應用"""
    print("Starting Flask application...")
    
    # 設置環境變數
    os.environ.setdefault('FLASK_APP', 'app.py')
    os.environ.setdefault('FLASK_ENV', 'production')
    
    # 獲取端口
    port = os.environ.get('PORT', '5000')
    
    try:
        # 嘗試使用 gunicorn
        subprocess.check_call(['which', 'gunicorn'])
        print("Using gunicorn...")
        subprocess.check_call([
            'gunicorn', 
            'app:app',
            '--bind', f'0.0.0.0:{port}',
            '--workers', '4'
        ])
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Gunicorn not available, using Flask development server...")
        # 直接運行 app.py
        subprocess.check_call([sys.executable, 'app.py'])

if __name__ == '__main__':
    install_dependencies()
    start_app() 