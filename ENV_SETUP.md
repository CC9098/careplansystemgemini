# 🔧 環境設定指南

## 📋 必要的環境變數

### 1. 後端環境變數
創建 `.env` 文件在項目根目錄：

```bash
# Flask 配置
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///care_buddy.db

# Google OAuth 配置
GOOGLE_CLIENT_ID=your-google-client-id-here

# DeepSeek AI 配置 (可選)
DEEPSEEK_API_KEY=your-deepseek-api-key-here
```

### 2. 前端環境變數
創建 `.env` 文件在項目根目錄：

```bash
# React 前端配置
REACT_APP_API_BASE_URL=http://localhost:5001/api/v1
REACT_APP_GOOGLE_CLIENT_ID=your-google-client-id-here
```

## 🔑 Google OAuth 設定

### 1. 創建 Google Cloud 項目
1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 創建新項目或選擇現有項目
3. 啟用 Google+ API

### 2. 創建 OAuth 2.0 憑證
1. 前往 APIs & Services > Credentials
2. 點擊 "Create Credentials" > "OAuth client ID"
3. 選擇 "Web application"
4. 設定授權來源：
   - `http://localhost:3000` (開發環境)
   - `http://localhost:5001` (後端)
5. 複製 Client ID

### 3. 開發者模式設定

#### 快速測試用的假 Client ID：
```bash
# 僅用於開發測試，不適用於生產環境
GOOGLE_CLIENT_ID=test-client-id-for-development
REACT_APP_GOOGLE_CLIENT_ID=test-client-id-for-development
```

#### 開發者模式後端配置：
在 `api/v1/endpoints.py` 中添加開發者模式：

```python
@api_v1.route('/auth/google-dev', methods=['POST'])
def google_auth_dev():
    """開發者模式 Google 認證"""
    if not current_app.config.get('FLASK_ENV') == 'development':
        return api_response(False, error={"message": "Development mode only"}, status_code=403)
    
    data = request.get_json()
    email = data.get('email', 'dev@example.com')
    name = data.get('name', 'Developer User')
    
    # 查找或創建開發者用戶
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            name=name,
            google_id='dev-' + email,
            is_google_user=True
        )
        db.session.add(user)
        db.session.commit()
    
    login_user(user)
    return api_response(True, data={"user": user.to_dict()})
```

## 🚀 啟動步驟

### 1. 安裝依賴
```bash
# 後端
pip3 install -r requirements.txt

# 前端
npm install
```

### 2. 設定環境變數
```bash
# 複製並編輯環境變數
cp ENV_SETUP.md .env
# 編輯 .env 文件，填入您的配置
```

### 3. 啟動服務
```bash
# 啟動後端 (終端 1)
python3 app.py

# 啟動前端 (終端 2)
npm start
```

### 4. 測試
- 前端：http://localhost:3000
- 後端 API：http://localhost:5001/api/v1
- 測試 Google 登入功能

## 🛠 開發者模式特殊功能

### 1. 跳過 Google 驗證
如果沒有設定 Google Client ID，系統會自動創建測試用戶。

### 2. 預設測試用戶
- Email: dev@example.com
- Name: Developer User
- 自動登入成功

### 3. 本地數據庫
使用 SQLite 數據庫，數據存儲在 `care_buddy.db` 文件中。

## ⚠️ 注意事項

1. **安全性**：開發者模式僅適用於本地開發
2. **生產環境**：必須設定真實的 Google Client ID
3. **數據庫**：生產環境建議使用 PostgreSQL
4. **HTTPS**：生產環境必須使用 HTTPS 