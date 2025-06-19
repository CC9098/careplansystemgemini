# 使用官方 Python 3.11 鏡像
FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件
COPY requirements.txt .
COPY package.json .

# 安裝 Node.js (用於構建前端)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 安裝 Node.js 依賴並構建前端
RUN npm install
RUN npm run build

# 複製應用代碼
COPY . .

# 創建非 root 用戶
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 暴露端口
EXPOSE 8000

# 啟動命令
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app:app"] 