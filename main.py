
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
from data_validation_config import *

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB file limit
app.config['UPLOAD_FOLDER'] = 'temp_uploads'

# Create temp folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Claude API
api_key = os.environ.get('CLAUDE')
if not api_key:
    print("Warning: CLAUDE API key not found in environment variables")
    client = None
else:
    try:
        client = anthropic.Anthropic(api_key=api_key)
        print("Claude API client initialized successfully")
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
            # Bowel movement records
            if any(keyword in line.lower() for keyword in BOWEL_MOVEMENT_CONFIG['keywords']):
                numbers = re.findall(r'\b(\d{1,2})\b', line)
                for num in numbers:
                    count = int(num)
                    if is_valid_bowel_movement(count):
                        data['bowel_movements'].append({'date': current_date, 'count': count})
                        break
            
            # Water intake
            if any(keyword in line.lower() for keyword in WATER_INTAKE_CONFIG['keywords']):
                water_matches = re.findall(r'(\d{2,4})(?:\s*(?:ml|毫升|liter|l))?', line.lower())
                for match in water_matches:
                    amount = int(match)
                    if is_valid_water_intake(amount):
                        data['water_intake'].append({'date': current_date, 'amount': amount})
                        break
            
            # Food intake (percentage)
            if any(keyword in line.lower() for keyword in FOOD_INTAKE_CONFIG['keywords']):
                percent_match = re.search(r'(\d{1,3})(?:%|percent)', line.lower())
                if percent_match:
                    percentage = int(percent_match.group(1))
                    if is_valid_food_intake(percentage):
                        data['food_intake'].append({'date': current_date, 'percentage': percentage})
                else:
                    fraction_match = re.search(r'(\d+)/(\d+)', line)
                    if fraction_match:
                        numerator = int(fraction_match.group(1))
                        denominator = int(fraction_match.group(2))
                        if denominator > 0:
                            percentage = int((numerator / denominator) * 100)
                            if is_valid_food_intake(percentage):
                                data['food_intake'].append({'date': current_date, 'percentage': percentage})
            
            # Incidents
            if any(keyword in line.lower() for keyword in INCIDENT_CONFIG['general_keywords']):
                severity = get_incident_severity(line)
                data['incidents'].append({
                    'date': current_date,
                    'description': line,
                    'severity': severity
                })
    
    return data

def analyze_and_suggest_changes(daily_log, current_care_plan, resident_name):
    """Step 1: Analyze and suggest changes"""
    
    prompt = f"""You are a care home management assistant. Your task is to analyze the resident's care log and current care plan, then provide specific suggestions for updating the care plan.

RESIDENT: {resident_name}

CARE LOG (this month):
{daily_log}

CURRENT CARE PLAN:
{current_care_plan}

Please analyze the care log and current care plan, then provide a list of specific, actionable suggestions for updating the care plan.

Format your response as a JSON object with this structure:
{{
    "analysis_summary": "Brief summary of key findings from the care log",
    "suggestions": [
        {{
            "id": 1,
            "category": "Personal Care|Eating & Drinking|Continence|Mobility|Health & Medication|Daily Routine|Skin Care|Choice & Communication|Behavior|Other",
            "suggestion": "Specific, actionable suggestion text",
            "reason": "Brief explanation of why this change is needed based on the log data",
            "priority": "High|Medium|Low"
        }}
    ]
}}

Guidelines:
- Each suggestion should be specific and actionable
- Base suggestions only on evidence found in the care log
- Include 5-15 suggestions maximum
- Prioritize suggestions that address safety, health, or significant changes in behavior/needs
- Make suggestions suitable for checkbox selection by a manager"""

    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=3000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            # Fallback if JSON parsing fails
            return {
                "analysis_summary": "Analysis completed",
                "suggestions": []
            }
            
    except Exception as e:
        return {
            "analysis_summary": f"Error during analysis: {str(e)}",
            "suggestions": []
        }

def generate_final_care_plan(original_care_plan, selected_suggestions, manager_comments, resident_name):
    """Step 3: Generate final care plan based on selected suggestions"""
    
    # Format selected suggestions for the prompt
    selected_text = ""
    for suggestion in selected_suggestions:
        selected_text += f"- {suggestion['suggestion']} (Reason: {suggestion['reason']})\n"
    
    prompt = f"""You are a care home management assistant. Generate a new, comprehensive care plan for resident "{resident_name}" by updating the original care plan with the manager's selected suggestions and comments.

ORIGINAL CARE PLAN:
{original_care_plan}

MANAGER'S SELECTED SUGGESTIONS:
{selected_text}

MANAGER'S ADDITIONAL COMMENTS:
{manager_comments}

Please create a new, complete care plan that:
1. Incorporates all the selected suggestions
2. Includes the manager's additional comments
3. Maintains all relevant information from the original plan
4. Is professionally formatted and ready for daily use
5. Is clear and actionable for care staff

Format the care plan as a comprehensive document with appropriate sections. Do not include any process history - only the final care plan."""

    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
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
                file.seek(0)
                dialect = csv.Sniffer().sniff(file.read(1024))
                file.seek(0)
                reader = csv.reader(file, dialect)
                rows = list(reader)

                if rows:
                    headers = rows[0] if len(rows) > 0 else []
                    data_rows = rows[1:] if len(rows) > 1 else []

                    formatted_content = f"Columns: {', '.join(headers)}\n\n"
                    for i, row in enumerate(data_rows, 1):
                        formatted_content += f"Record {i}:\n"
                        for j, (header, value) in enumerate(zip(headers, row)):
                            if value.strip():
                                formatted_content += f"  {header}: {value}\n"
                        formatted_content += "\n"

                    return formatted_content
                else:
                    return content

        except Exception as e:
            continue

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    except:
        return "Unable to read file content"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if not client:
        return jsonify({'error': 'Claude API not available. Please check your CLAUDE environment variable.'}), 500
    
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

        # Extract structured data for charts
        structured_data = extract_daily_data(daily_log_content)
        
        # Step 1: Get suggestions
        analysis_result = analyze_and_suggest_changes(daily_log_content, care_plan_content, resident_name)

        # Clean up temp files
        os.remove(daily_log_path)
        os.remove(care_plan_path)

        return jsonify({
            'success': True,
            'step': 'suggestions',
            'analysis_summary': analysis_result.get('analysis_summary', ''),
            'suggestions': analysis_result.get('suggestions', []),
            'structured_data': structured_data,
            'resident_name': resident_name,
            'original_care_plan': care_plan_content
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate_care_plan', methods=['POST'])
def generate_care_plan():
    """Step 3: Generate final care plan based on manager's selections"""
    if not client:
        return jsonify({'error': 'Claude API not available. Please check your CLAUDE environment variable.'}), 500
    
    try:
        data = request.get_json()
        
        original_care_plan = data.get('original_care_plan', '')
        selected_suggestions = data.get('selected_suggestions', [])
        manager_comments = data.get('manager_comments', '')
        resident_name = data.get('resident_name', 'Unnamed Resident')
        
        # Generate final care plan
        final_care_plan = generate_final_care_plan(
            original_care_plan, 
            selected_suggestions, 
            manager_comments, 
            resident_name
        )
        
        # Convert to HTML for display
        care_plan_html = markdown.markdown(final_care_plan, extensions=['extra', 'nl2br'])
        
        return jsonify({
            'success': True,
            'care_plan': {
                'markdown': final_care_plan,
                'html': care_plan_html
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    """Download care plan as Markdown file"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        resident_name = data.get('resident_name', 'Unnamed_Resident')

        filename = f"Care_Plan_{resident_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

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
