# AI Care Plan 管理系統

這是一個專為安老院設計的 AI 智能照護計劃管理平台，讓管理人員能夠快速生成個人化的照護計劃和任務，並與家屬分享。

## 功能特色

### 核心功能
- **AI 智能分析**：基於日常記錄和住民狀況，AI 自動生成專業照護建議
- **照護計劃管理**：創建、更新和版本控制照護計劃
- **任務管理**：自動生成和追蹤照護任務
- **家屬分享**：安全的連結分享系統，讓家屬隨時了解照護狀況

### 技術特色
- **前後端分離**：React 前端 + Flask API 後端
- **現代化 UI**：使用 Chakra UI 組件庫
- **RESTful API**：標準化的 API 設計
- **用戶驗證**：支援 Email/密碼登入和 Google OAuth
- **數據安全**：密碼加密和安全的分享機制

## 技術架構

### 後端 (Flask)
- **框架**：Flask 2.3.3
- **數據庫**：SQLite (開發) / PostgreSQL (生產)
- **認證**：Flask-Login + Session
- **API 設計**：RESTful API with Blueprint
- **AI 集成**：DeepSeek API

### 前端 (React)
- **框架**：React 18.2.0
- **UI 庫**：Chakra UI 2.8.2
- **路由**：React Router 6.8.1
- **HTTP 客戶端**：Axios 1.6.2
- **字體**：Noto Sans TC (繁體中文)

## 環境要求

- Python 3.8+
- Node.js 16+
- npm 或 yarn

## 安裝與運行

### 1. 克隆項目
```bash
git clone <repository-url>
cd V0Careplanparrot
```

### 2. 後端設置
```bash
# 安裝 Python 依賴
pip install -r requirements.txt

# 設置環境變數
export SECRET_KEY="your-secret-key-here"
export DEEPSEEK_API_KEY="your-deepseek-api-key"

# 創建數據庫（首次運行）
python -c "from app import app; from models import db; app.app_context().push(); db.create_all()"

# 運行後端服務器
python app.py
```

後端將在 `http://localhost:5000` 運行

### 3. 前端設置
```bash
# 安裝 Node.js 依賴
npm install

# 運行前端開發服務器
npm start
```

前端將在 `http://localhost:3000` 運行

## API 端點

### 認證
- `POST /api/v1/auth/register` - 用戶註冊
- `POST /api/v1/auth/login` - 用戶登入
- `POST /api/v1/auth/logout` - 用戶登出
- `GET /api/v1/auth/me` - 獲取當前用戶信息

### 住民管理
- `GET /api/v1/residents` - 獲取住民列表
- `POST /api/v1/residents` - 創建新住民
- `GET /api/v1/residents/{id}` - 獲取住民詳情
- `PUT /api/v1/residents/{id}` - 更新住民信息
- `DELETE /api/v1/residents/{id}` - 刪除住民

### AI 分析與照護計劃
- `POST /api/v1/analyze` - AI 分析日常記錄
- `POST /api/v1/generate-care-plan` - 生成照護計劃
- `GET /api/v1/residents/{id}/care-plan` - 獲取照護計劃
- `POST /api/v1/residents/{id}/care-plan` - 保存照護計劃

### 任務管理
- `POST /api/v1/residents/{id}/tasks` - 創建照護任務
- `PUT /api/v1/tasks/{id}` - 更新任務狀態

### 分享功能
- `POST /api/v1/shares` - 創建分享連結
- `GET /api/v1/shares/{token}/meta` - 獲取分享信息
- `POST /api/v1/shares/{token}/authenticate` - 驗證分享密碼
- `GET /api/v1/shares/{token}/dashboard` - 獲取分享內容

## 環境變數配置

創建 `.env` 文件：

```bash
# 應用配置
SECRET_KEY=your-super-secret-key-here
FLASK_ENV=development

# 數據庫配置
DATABASE_URL=sqlite:///care_buddy.db

# AI API 配置
DEEPSEEK_API_KEY=your-deepseek-api-key-here

# Google OAuth (可選)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

## 部署到 Railway

### 1. 準備部署文件
確保有以下文件：
- `Procfile`: `web: gunicorn app:app`
- `requirements.txt`: 包含所有 Python 依賴
- `package.json`: 包含所有 Node.js 依賴

### 2. 環境變數設置
在 Railway 儀表板中設置：
- `SECRET_KEY`
- `DEEPSEEK_API_KEY`
- `DATABASE_URL` (PostgreSQL)

### 3. 構建和部署
Railway 會自動檢測並構建 React 前端，然後運行 Flask 後端。

## 開發指南

### 項目結構
```
V0Careplanparrot/
├── app.py                 # Flask 應用入口
├── models.py              # 數據模型
├── requirements.txt       # Python 依賴
├── Procfile              # 部署配置
├── package.json          # Node.js 依賴
├── api/
│   └── v1/
│       └── endpoints.py  # API 端點
├── src/                  # React 前端源碼
│   ├── api/             # API 客戶端
│   ├── components/      # React 組件
│   ├── context/         # React Context
│   ├── pages/           # 頁面組件
│   ├── routing/         # 路由配置
│   └── theme/           # 主題配置
└── public/              # 靜態文件
```

### 新增 API 端點
1. 在 `api/v1/endpoints.py` 中添加新的路由函數
2. 確保使用 `api_response()` 函數返回標準化的 JSON 響應
3. 在前端 `src/api/client.js` 中添加對應的客戶端函數

### 新增頁面
1. 在 `src/pages/` 中創建新的頁面組件
2. 在 `src/routing/AppRouter.js` 中添加路由配置
3. 如需保護，使用 `ProtectedRoute` 組件包裝

## 問題排查

### 常見問題
1. **CORS 錯誤**：確保前後端端口配置正確
2. **數據庫錯誤**：檢查數據庫連接字符串和權限
3. **AI API 錯誤**：驗證 DEEPSEEK_API_KEY 是否正確設置

### 日誌查看
- 後端日誌：Flask 控制台輸出
- 前端日誌：瀏覽器開發者工具 Console

## 貢獻指南

1. Fork 項目
2. 創建功能分支
3. 提交更改
4. 創建 Pull Request

## 許可證

本項目採用 MIT 許可證。

## 聯繫方式

如有問題或建議，請聯繫開發團隊。 