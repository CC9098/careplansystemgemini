import os
# 設定環境變數來避免 proxy 問題
os.environ['HTTPX_DISABLE_PROXY'] = 'true'

import csv
import io
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
import anthropic
from werkzeug.utils import secure_filename
import markdown
import re
from collections import defaultdict

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB 檔案上限
app.config['UPLOAD_FOLDER'] = 'temp_uploads'

# 建立暫存資料夾
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 初始化 Claude API - 修正版本
api_key = os.environ.get('CLAUDE')
if not api_key:
    raise ValueError("請在 Secrets 中設定 CLAUDE")

try:
    client = anthropic.Anthropic(api_key=api_key)
except Exception as e:
    print(f"Anthropic 初始化錯誤: {e}")
    client = None

# 允許的檔案格式
ALLOWED_EXTENSIONS = {'csv', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_daily_data(daily_log_content):
    """從日誌中提取結構化數據"""
    data = {
        'bowel_movements': [],
        'water_intake': [],
        'food_intake': [],
        'incidents': [],
        'dates': []
    }
    
    lines = daily_log_content.split('\n')
    current_date = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 尋找日期
        date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})', line)
        if date_match:
            current_date = date_match.group(1)
            if current_date not in data['dates']:
                data['dates'].append(current_date)
        
        if current_date:
            # 排便記錄
            if any(keyword in line.lower() for keyword in ['排便', 'bowel', '大便', 'stool']):
                bowel_count = re.findall(r'(\d+)', line)
                if bowel_count:
                    data['bowel_movements'].append({'date': current_date, 'count': int(bowel_count[0])})
            
            # 飲水量
            if any(keyword in line.lower() for keyword in ['飲水', 'water', '水分', 'ml', '毫升']):
                water_amount = re.findall(r'(\d+)', line)
                if water_amount:
                    data['water_intake'].append({'date': current_date, 'amount': int(water_amount[0])})
            
            # 進食量 (百分比)
            if any(keyword in line.lower() for keyword in ['進食', 'eating', '食量', '%']):
                food_percent = re.findall(r'(\d+)%', line)
                if food_percent:
                    data['food_intake'].append({'date': current_date, 'percentage': int(food_percent[0])})
            
            # 異常事件
            if any(keyword in line.lower() for keyword in ['跌倒', 'fall', '異常', '問題', '事故', '受傷', 'incident']):
                severity = 'high' if any(s in line.lower() for s in ['嚴重', '緊急', '受傷']) else 'medium'
                data['incidents'].append({
                    'date': current_date,
                    'description': line,
                    'severity': severity
                })
    
    return data

def generate_care_plan(analysis_result, resident_name):
    """生成新的護理計劃"""
    care_plan_prompt = f"""根據以下分析結果，為住戶「{resident_name}」生成一個實用的護理計劃，格式為可執行的待辦清單：

{analysis_result}

請生成以下格式的護理計劃：

# 護理計劃 - {resident_name}
生成日期：{datetime.now().strftime('%Y年%m月%d日')}

## 🔴 高優先級任務（立即執行）
- [ ] 任務項目 1
- [ ] 任務項目 2

## 🟡 中優先級任務（本週內完成）
- [ ] 任務項目 1
- [ ] 任務項目 2

## 🟢 低優先級任務（本月內完成）
- [ ] 任務項目 1
- [ ] 任務項目 2

## 📋 日常護理檢查清單
### 每日檢查
- [ ] 檢查項目 1
- [ ] 檢查項目 2

### 每週檢查
- [ ] 檢查項目 1
- [ ] 檢查項目 2

## 🏥 醫療跟進
- [ ] 醫療任務 1
- [ ] 醫療任務 2

## 📞 聯絡事項
- [ ] 需要聯絡的專業人員或家屬

## 📅 下次檢討日期
預定檢討日期：{(datetime.now().replace(day=datetime.now().day + 30) if datetime.now().day <= 28 else datetime.now().replace(month=datetime.now().month + 1, day=1)).strftime('%Y年%m月%d日')}

請確保所有任務項目都具體、可測量且有時間框架。"""

    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.7,
            messages=[{"role": "user", "content": care_plan_prompt}]
        )
        return message.content[0].text
    except Exception as e:
        return f"生成護理計劃時發生錯誤：{str(e)}"

def read_csv_flexible(file_path):
    """靈活讀取CSV檔案，自動偵測編碼和格式"""
    encodings = ['utf-8', 'big5', 'gb2312', 'gbk', 'latin1']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()
                # 嘗試用CSV讀取
                file.seek(0)
                dialect = csv.Sniffer().sniff(file.read(1024))
                file.seek(0)
                reader = csv.reader(file, dialect)
                rows = list(reader)

                # 轉換為易讀格式
                if rows:
                    headers = rows[0] if len(rows) > 0 else []
                    data_rows = rows[1:] if len(rows) > 1 else []

                    formatted_content = f"欄位: {', '.join(headers)}\n\n"
                    for i, row in enumerate(data_rows, 1):
                        formatted_content += f"記錄 {i}:\n"
                        for j, (header, value) in enumerate(zip(headers, row)):
                            if value.strip():  # 只顯示有值的欄位
                                formatted_content += f"  {header}: {value}\n"
                        formatted_content += "\n"

                    return formatted_content
                else:
                    return content

        except Exception as e:
            continue

    # 如果所有編碼都失敗，返回原始內容
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    except:
        return "無法讀取檔案內容"

def analyze_with_claude(daily_log, current_care_plan, resident_name):
    """使用 Claude API 分析並生成建議"""

    prompt = f"""你是一位資深的安老院護理專家。請根據以下資料，為住戶「{resident_name}」提供專業的護理計劃分析和建議。

【住戶本月日誌記錄】
{daily_log}

【現有護理計劃 (Care Plan)】
{current_care_plan}

請按以下格式提供分析報告：

# 護理計劃分析報告 - {resident_name}
生成日期：{datetime.now().strftime('%Y年%m月%d日')}

## 1. 本月重點觀察摘要
（請列出3-5個從日誌中發現的重要行為模式或變化）

## 2. 現有護理計劃評估
（分析現有計劃的適切性，指出哪些方面仍然有效，哪些需要調整）

## 3. 建議修訂重點
（根據以下類別，提出具體的修訂建議）

### 個人護理 (Personal Care)
- 現況評估：
- 修訂建議：

### 飲食 (Eating & Drinking)
- 現況評估：
- 修訂建議：

### 失禁護理 (Continence)
- 現況評估：
- 修訂建議：

### 活動能力 (Mobility)
- 現況評估：
- 修訂建議：

### 健康與藥物 (Health & Medication)
- 現況評估：
- 修訂建議：

### 日常作息 (Daily Routine)
- 現況評估：
- 修訂建議：

### 皮膚護理 (Skin)
- 現況評估：
- 修訂建議：

### 選擇與溝通 (Choice & Communication)
- 現況評估：
- 修訂建議：

### 行為 (Behaviour)
- 現況評估：
- 修訂建議：

### 其他需要關注的範疇
（如適用，請說明）

## 4. 優先行動項目
（列出3-5個最需要立即處理的事項，按緊急程度排序）

## 5. 建議的新護理計劃大綱
（提供一個整合了所有修訂建議的新護理計劃框架）

## 6. 跟進建議
（包括檢討週期、需要諮詢的專業人員等）

請確保所有建議都具體、可行，並以住戶的最佳利益為依歸。"""

    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.7,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return message.content[0].text

    except Exception as e:
        return f"AI 分析時發生錯誤：{str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        # 獲取表單資料
        resident_name = request.form.get('resident_name', '未命名住戶')

        # 檢查檔案
        if 'daily_log' not in request.files or 'care_plan' not in request.files:
            return jsonify({'error': '請上傳兩個檔案'}), 400

        daily_log_file = request.files['daily_log']
        care_plan_file = request.files['care_plan']

        if not daily_log_file or daily_log_file.filename == '' or not care_plan_file or care_plan_file.filename == '':
            return jsonify({'error': '請選擇檔案'}), 400

        if not allowed_file(daily_log_file.filename) or not allowed_file(care_plan_file.filename):
            return jsonify({'error': '只允許上傳 CSV 或 TXT 檔案'}), 400

        # 儲存檔案
        daily_log_path = os.path.join(app.config['UPLOAD_FOLDER'], 
                                      secure_filename(f"daily_{datetime.now().timestamp()}.csv"))
        care_plan_path = os.path.join(app.config['UPLOAD_FOLDER'], 
                                      secure_filename(f"care_{datetime.now().timestamp()}.csv"))

        daily_log_file.save(daily_log_path)
        care_plan_file.save(care_plan_path)

        # 讀取檔案內容
        daily_log_content = read_csv_flexible(daily_log_path)
        care_plan_content = read_csv_flexible(care_plan_path)

        # 提取結構化數據
        structured_data = extract_daily_data(daily_log_content)
        
        # AI 分析
        analysis_result = analyze_with_claude(daily_log_content, care_plan_content, resident_name)
        
        # 生成新護理計劃
        new_care_plan = generate_care_plan(analysis_result, resident_name)

        # 轉換 Markdown 為 HTML
        html_result = markdown.markdown(analysis_result, extensions=['extra', 'nl2br'])
        care_plan_html = markdown.markdown(new_care_plan, extensions=['extra', 'nl2br'])

        # 清理暫存檔案
        os.remove(daily_log_path)
        os.remove(care_plan_path)

        return jsonify({
            'success': True,
            'markdown': analysis_result,
            'html': html_result,
            'structured_data': structured_data,
            'care_plan': {
                'markdown': new_care_plan,
                'html': care_plan_html
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    """下載分析報告為 Markdown 檔案"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        resident_name = data.get('resident_name', '未命名住戶')

        # 建立檔案
        filename = f"護理計劃分析_{resident_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        # 建立記憶體中的檔案
        output = io.BytesIO()
        output.write(content.encode('utf-8'))
        output.seek(0)

        return send_file(
            output,
            mimetype='text/markdown',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)