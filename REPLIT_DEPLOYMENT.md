# AI Care Plan 管理系統 - Replit 部署指南

## 🚀 快速部署到 Replit

### 1. 導入項目到 Replit

1. 前往 [Replit.com](https://replit.com)
2. 點擊 "Create Repl"
3. 選擇 "Import from GitHub"
4. 輸入您的 GitHub 倉庫 URL: `https://github.com/CC9098/Careplanparrotv0.11.git`
5. 點擊 "Import from GitHub"

### 2. 環境變數設置

在 Replit 的 "Secrets" 面板中添加以下環境變數：

```
SECRET_KEY=your-secret-key-here
DEEPSEEK_API_KEY=your-deepseek-api-key
DATABASE_URL=sqlite:///care_buddy.db
FLASK_ENV=production
```

### 3. 自動配置

Replit 會自動：
- 檢測 Python 和 Node.js 環境
- 安裝 Python 依賴 (`requirements.txt`)
- 安裝 Node.js 依賴 (`package.json`)
- 構建 React 前端
- 啟動 Flask 後端

### 4. 手動構建前端（如需要）

如果前端沒有自動構建，在 Replit Shell 中運行：

```bash
npm install
npm run build
```

### 5. 啟動應用

點擊 Replit 的 "Run" 按鈕，應用將在 `https://your-repl-name.your-username.repl.co` 上運行。

## 🔧 故障排除

### 前端構建問題
如果遇到 npm 安裝問題：
```bash
rm -rf node_modules package-lock.json
npm install
npm run build
```

### 數據庫問題
Replit 會自動創建 SQLite 數據庫。如果需要重置：
```bash
rm -f care_buddy.db
python app.py
```

### 端口問題
Replit 會自動設置端口，無需手動配置。

## 📁 項目結構

```
├── app.py              # Flask 應用入口
├── models.py           # 數據模型
├── api/v1/endpoints.py # API 端點
├── src/                # React 前端源碼
├── build/              # 構建後的前端（自動生成）
├── requirements.txt    # Python 依賴
├── package.json        # Node.js 依賴
├── .replit            # Replit 配置
└── replit.nix         # Nix 包管理
```

## 🎯 功能特性

- ✅ **用戶認證** - 註冊、登入、會話管理
- ✅ **住民管理** - 添加、編輯住民信息
- ✅ **AI 分析** - DeepSeek API 集成
- ✅ **照護計劃** - 生成和管理照護計劃
- ✅ **分享功能** - 生成分享連結給家屬
- ✅ **響應式設計** - 支持手機和桌面

## 🔑 API 密鑰獲取

### DeepSeek API
1. 前往 [DeepSeek Platform](https://platform.deepseek.com/)
2. 註冊並獲取 API 密鑰
3. 在 Replit Secrets 中添加 `DEEPSEEK_API_KEY`

## 📞 支持

如有問題，請查看：
- [Flask 文檔](https://flask.palletsprojects.com/)
- [React 文檔](https://react.dev/)
- [Replit 文檔](https://docs.replit.com/) 