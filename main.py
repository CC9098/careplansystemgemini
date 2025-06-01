
import os
# Set environment variables to avoid proxy issues
os.environ['HTTPX_DISABLE_PROXY'] = 'true'

import csv
import io
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file
import anthropic
from werkzeug.utils import secure_filename
import markdown
import re
from collections import defaultdict

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB file limit
app.config['UPLOAD_FOLDER'] = 'temp_uploads'

# Create temp folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Claude API
api_key = os.environ.get('CLAUDE')
if not api_key:
    raise ValueError("Please set CLAUDE in Secrets")

try:
    client = anthropic.Anthropic(api_key=api_key)
except Exception as e:
    print(f"Anthropic initialization error: {e}")
    client = None

# Allowed file formats
ALLOWED_EXTENSIONS = {'csv', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_daily_data(daily_log_content):
    """Extract structured data from daily logs"""
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
            
        # Find dates
        date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})', line)
        if date_match:
            current_date = date_match.group(1)
            if current_date not in data['dates']:
                data['dates'].append(current_date)
        
        if current_date:
            # Bowel movement records - more flexible pattern matching
            bowel_keywords = ['bowel', 'stool', 'defecation', 'bm', '排便', '大便']
            if any(keyword in line.lower() for keyword in bowel_keywords):
                # Look for numbers in the line (more flexible)
                numbers = re.findall(r'\b(\d{1,2})\b', line)
                for num in numbers:
                    count = int(num)
                    if 0 <= count <= 15:  # More reasonable range
                        data['bowel_movements'].append({'date': current_date, 'count': count})
                        break
            
            # Water intake - more flexible pattern matching
            water_keywords = ['water', 'fluid', 'drink', 'ml', 'liter', '飲水', '水分', '毫升']
            if any(keyword in line.lower() for keyword in water_keywords):
                # Look for numbers with ml or without unit
                water_matches = re.findall(r'(\d{2,4})(?:\s*(?:ml|毫升|liter|l))?', line.lower())
                for match in water_matches:
                    amount = int(match)
                    if 50 <= amount <= 5000:  # More reasonable range
                        data['water_intake'].append({'date': current_date, 'amount': amount})
                        break
            
            # Food intake (percentage) - more flexible pattern matching
            food_keywords = ['food', 'eat', 'meal', 'intake', 'consumption', '%', 'percent', '進食', '食量']
            if any(keyword in line.lower() for keyword in food_keywords):
                # Look for percentages or fractions
                percent_match = re.search(r'(\d{1,3})(?:%|percent)', line.lower())
                if percent_match:
                    percentage = int(percent_match.group(1))
                    if 0 <= percentage <= 100:
                        data['food_intake'].append({'date': current_date, 'percentage': percentage})
                else:
                    # Look for fractions like 3/4, 1/2
                    fraction_match = re.search(r'(\d+)/(\d+)', line)
                    if fraction_match:
                        numerator = int(fraction_match.group(1))
                        denominator = int(fraction_match.group(2))
                        if denominator > 0:
                            percentage = int((numerator / denominator) * 100)
                            data['food_intake'].append({'date': current_date, 'percentage': percentage})
            
            # Incidents
            incident_keywords = ['fall', 'incident', 'accident', 'injury', 'problem', 'concern', '跌倒', '異常', '問題', '事故', '受傷']
            if any(keyword in line.lower() for keyword in incident_keywords):
                severity = 'high' if any(s in line.lower() for s in ['severe', 'serious', 'emergency', 'injury', '嚴重', '緊急', '受傷']) else 'medium'
                data['incidents'].append({
                    'date': current_date,
                    'description': line,
                    'severity': severity
                })
    
    return data

def generate_care_plan(analysis_result, resident_name):
    """Generate new care plan"""
    care_plan_prompt = f"""Based on the following analysis results, generate a practical care plan for resident "{resident_name}" in checklist format:

{analysis_result}

Please generate a care plan in the following format:

# Care Plan - {resident_name}
Generated Date: {datetime.now().strftime('%Y-%m-%d')}

## 🔴 High Priority Tasks (Immediate Action)
- [ ] Task item 1
- [ ] Task item 2

## 🟡 Medium Priority Tasks (Complete this week)
- [ ] Task item 1
- [ ] Task item 2

## 🟢 Low Priority Tasks (Complete this month)
- [ ] Task item 1
- [ ] Task item 2

## 📋 Daily Care Checklist
### Daily Checks
- [ ] Check item 1
- [ ] Check item 2

### Weekly Checks
- [ ] Check item 1
- [ ] Check item 2

## 🏥 Medical Follow-up
- [ ] Medical task 1
- [ ] Medical task 2

## 📞 Contact Items
- [ ] Need to contact professionals or family members

## 📅 Next Review Date
Scheduled review date: {(datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')}

Please ensure all task items are specific, measurable and time-framed."""

    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.7,
            messages=[{"role": "user", "content": care_plan_prompt}]
        )
        return message.content[0].text
    except Exception as e:
        return f"Error generating care plan: {str(e)}"

def read_csv_flexible(file_path):
    """Flexibly read CSV files, auto-detect encoding and format"""
    encodings = ['utf-8', 'big5', 'gb2312', 'gbk', 'latin1']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()
                # Try to read as CSV
                file.seek(0)
                dialect = csv.Sniffer().sniff(file.read(1024))
                file.seek(0)
                reader = csv.reader(file, dialect)
                rows = list(reader)

                # Convert to readable format
                if rows:
                    headers = rows[0] if len(rows) > 0 else []
                    data_rows = rows[1:] if len(rows) > 1 else []

                    formatted_content = f"Columns: {', '.join(headers)}\n\n"
                    for i, row in enumerate(data_rows, 1):
                        formatted_content += f"Record {i}:\n"
                        for j, (header, value) in enumerate(zip(headers, row)):
                            if value.strip():  # Only show non-empty fields
                                formatted_content += f"  {header}: {value}\n"
                        formatted_content += "\n"

                    return formatted_content
                else:
                    return content

        except Exception as e:
            continue

    # If all encodings fail, return raw content
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    except:
        return "Unable to read file content"

def analyze_with_claude(daily_log, current_care_plan, resident_name):
    """Analyze using Claude API and generate recommendations"""

    prompt = f"""You are a senior nursing home care expert. Please provide professional care plan analysis and recommendations for resident "{resident_name}" based on the following data.

【Resident Monthly Log Records】
{daily_log}

【Current Care Plan】
{current_care_plan}

Please provide an analysis report in the following format:

# Care Plan Analysis Report - {resident_name}
Generated Date: {datetime.now().strftime('%Y-%m-%d')}

## 1. Monthly Key Observations Summary
(List 3-5 important behavioral patterns or changes discovered from the logs)

## 2. Current Care Plan Assessment
(Analyze the appropriateness of the existing plan, pointing out which aspects are still effective and which need adjustment)

## 3. Recommended Revision Points
(Provide specific revision recommendations based on the following categories)

### Personal Care
- Current Assessment:
- Revision Recommendations:

### Eating & Drinking
- Current Assessment:
- Revision Recommendations:

### Continence
- Current Assessment:
- Revision Recommendations:

### Mobility
- Current Assessment:
- Revision Recommendations:

### Health & Medication
- Current Assessment:
- Revision Recommendations:

### Daily Routine
- Current Assessment:
- Revision Recommendations:

### Skin Care
- Current Assessment:
- Revision Recommendations:

### Choice & Communication
- Current Assessment:
- Revision Recommendations:

### Behavior
- Current Assessment:
- Revision Recommendations:

### Other Areas of Concern
(If applicable, please specify)

## 4. Priority Action Items
(List 3-5 items that need immediate attention, ordered by urgency)

## 5. Recommended New Care Plan Outline
(Provide a framework for a new care plan that integrates all revision recommendations)

## 6. Follow-up Recommendations
(Including review cycles, professionals to consult, etc.)

Please ensure all recommendations are specific, feasible, and in the resident's best interest."""

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
        return f"AI analysis error: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        # Get form data
        resident_name = request.form.get('resident_name', 'Unnamed Resident')

        # Check files
        if 'daily_log' not in request.files or 'care_plan' not in request.files:
            return jsonify({'error': 'Please upload both files'}), 400

        daily_log_file = request.files['daily_log']
        care_plan_file = request.files['care_plan']

        if not daily_log_file or daily_log_file.filename == '' or not care_plan_file or care_plan_file.filename == '':
            return jsonify({'error': 'Please select files'}), 400

        if not allowed_file(daily_log_file.filename) or not allowed_file(care_plan_file.filename):
            return jsonify({'error': 'Only CSV or TXT files allowed'}), 400

        # Save files
        daily_log_path = os.path.join(app.config['UPLOAD_FOLDER'], 
                                      secure_filename(f"daily_{datetime.now().timestamp()}.csv"))
        care_plan_path = os.path.join(app.config['UPLOAD_FOLDER'], 
                                      secure_filename(f"care_{datetime.now().timestamp()}.csv"))

        daily_log_file.save(daily_log_path)
        care_plan_file.save(care_plan_path)

        # Read file content
        daily_log_content = read_csv_flexible(daily_log_path)
        care_plan_content = read_csv_flexible(care_plan_path)

        # Extract structured data
        structured_data = extract_daily_data(daily_log_content)
        
        # AI analysis
        analysis_result = analyze_with_claude(daily_log_content, care_plan_content, resident_name)
        
        # Generate new care plan
        new_care_plan = generate_care_plan(analysis_result, resident_name)

        # Convert Markdown to HTML
        html_result = markdown.markdown(analysis_result, extensions=['extra', 'nl2br'])
        care_plan_html = markdown.markdown(new_care_plan, extensions=['extra', 'nl2br'])

        # Clean up temp files
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
    """Download analysis report as Markdown file"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        resident_name = data.get('resident_name', 'Unnamed_Resident')

        # Create filename
        filename = f"Care_Plan_Analysis_{resident_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        # Create in-memory file
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
