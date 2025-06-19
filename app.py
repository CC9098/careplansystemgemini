#!/usr/bin/env python3
import os
from flask import Flask, send_from_directory
from flask_login import LoginManager
from flask_cors import CORS
from models import db, User
from datetime import timedelta

# 從新的 Blueprint 檔案中導入 api_v1
from api.v1.endpoints import api_v1

def create_app():
    # 檢查是否存在 build 文件夾（生產環境）
    static_folder = 'build' if os.path.exists('build') else 'public'
    app = Flask(__name__, static_folder=static_folder, static_url_path='/')

    # --- Configuration ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # 處理數據庫 URL 格式（支持 PostgreSQL 和 SQLite）
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///care_buddy.db')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
    
    # Session configuration
    app.config['SESSION_COOKIE_SECURE'] = True if 'DATABASE_URL' in os.environ else False # Production: True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

    # --- DeepSeek Client Initialization ---
    deepseek_api_key = os.environ.get('DEEPSEEK_API_KEY')
    if deepseek_api_key:
        app.config['DEEPSEEK_CLIENT'] = {
            'api_key': deepseek_api_key,
            'base_url': 'https://api.deepseek.com/v1/chat/completions',
            'headers': {
                'Authorization': f'Bearer {deepseek_api_key}',
                'Content-Type': 'application/json'
            }
        }
    else:
        app.config['DEEPSEEK_CLIENT'] = None
        print("Warning: DEEPSEEK_API_KEY not found. AI features will be disabled.")

    # --- Extensions Initialization ---
    db.init_app(app)
    
    # CORS 配置
    CORS(app, 
         origins=['http://localhost:3000'],  # 允許前端域名
         supports_credentials=True,          # 支持 cookies
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    
    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    @login_manager.unauthorized_handler
    def unauthorized():
        # For API requests, return 401 Unauthorized
        return {"success": False, "error": {"message": "Authentication required"}}, 401

    # --- Register Blueprints ---
    app.register_blueprint(api_v1, url_prefix='/api/v1')

    # --- React Frontend Serving ---
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    return app

# --- Main Execution ---
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # 創建資料庫表格
    
    # 獲取端口號，支持 Replit、Railway 等平台的 PORT 環境變數
    # 本地開發使用 5001 避免與 macOS ControlCenter 衝突
    port = int(os.environ.get('PORT', 5001))
    
    # 設置開發環境
    flask_env = os.environ.get('FLASK_ENV', 'development')
    app.config['FLASK_ENV'] = flask_env
    debug = flask_env == 'development'
    
    print(f"🚀 Starting Flask app on port {port}")
    print(f"🔧 Debug mode: {debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug) 