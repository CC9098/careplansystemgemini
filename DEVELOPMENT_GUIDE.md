# 🚀 AI Care Plan 系統開發指南

## 🎯 快速啟動

### 1. 啟動後端服務 (Flask)
```bash
python3 app.py
```
- **端口**: 5001 (避免與 macOS ControlCenter 衝突)
- **API 基礎路徑**: http://localhost:5001/api/v1

### 2. 啟動前端服務 (React)
```bash
npm start
```
- **端口**: 3000
- **前端地址**: http://localhost:3000

### 3. 系統測試
```bash
python3 test_system.py
```

## 🔧 問題修復

### ✅ 已修復的問題

1. **Git 合併衝突** - 已解決
2. **按鈕無法點擊** - 已修復：
   - ✅ 創建了 `AddResidentModal` 組件
   - ✅ 更新了 `DashboardPage` 使用模態對話框
   - ✅ 修復了 API 連接問題
   - ✅ 更改後端端口為 5001

### 🎉 新功能

1. **新增住民功能**：
   - 點擊 "新增住民" 按鈕會開啟模態對話框
   - 包含完整的住民信息表單
   - 支持表單驗證和錯誤處理
   - 成功新增後自動刷新列表

2. **系統測試工具**：
   - `test_system.py` 可以檢查前後端狀態
   - 自動診斷連接問題

## 🔍 系統架構

### 後端 (Flask)
- **文件**: `app.py`
- **API 路由**: `api/v1/endpoints.py`
- **數據模型**: `models.py`
- **端口**: 5001

### 前端 (React)
- **入口**: `src/App.js`
- **頁面**: `src/pages/`
- **組件**: `src/components/`
- **API 客戶端**: `src/api/client.js`

## 🛠 開發工作流

1. **修改後端**：
   - 編輯 `api/v1/endpoints.py` 或 `models.py`
   - Flask 會自動重載 (debug 模式)

2. **修改前端**：
   - 編輯 `src/` 下的文件
   - React 會自動熱重載

3. **測試**：
   - 運行 `python3 test_system.py`
   - 在瀏覽器中測試功能

## 📝 API 端點

### 認證
- `POST /api/v1/auth/login` - 用戶登入
- `POST /api/v1/auth/register` - 用戶註冊
- `GET /api/v1/auth/me` - 獲取當前用戶

### 住民管理
- `GET /api/v1/residents` - 獲取住民列表
- `POST /api/v1/residents` - 創建新住民
- `GET /api/v1/residents/{id}` - 獲取住民詳情
- `PUT /api/v1/residents/{id}` - 更新住民信息

### AI 功能
- `POST /api/v1/analyze` - AI 分析
- `POST /api/v1/generate-care-plan` - 生成照護計劃

## 🎨 UI 組件

### 已實現
- ✅ `AddResidentModal` - 新增住民對話框
- ✅ `DashboardPage` - 儀表板頁面
- ✅ `Layout` - 頁面佈局
- ✅ `Header` - 頁面標題

### 待實現
- ⏳ `ResidentDetailPage` - 住民詳情頁面
- ⏳ `CareTaskModal` - 照護任務對話框
- ⏳ `ShareModal` - 分享功能對話框

## 🚨 常見問題

### Q: 按鈕點擊沒有反應？
A: 檢查：
1. 後端服務是否運行 (python3 app.py)
2. 前端服務是否運行 (npm start)
3. API 連接是否正確 (檢查 console 錯誤)

### Q: 端口衝突？
A: macOS 的 ControlCenter 占用了 5000 端口，我們使用 5001

### Q: API 返回 401 錯誤？
A: 正常現象，需要先登入認證

## 🎯 下一步開發

1. **完善認證系統**：
   - 實現登入/註冊頁面
   - 添加用戶 session 管理

2. **住民詳情頁面**：
   - 顯示住民完整信息
   - AI 分析和照護計劃生成

3. **照護任務管理**：
   - 任務列表顯示
   - 任務狀態更新

4. **分享功能**：
   - 生成分享連結
   - 家屬查看界面 