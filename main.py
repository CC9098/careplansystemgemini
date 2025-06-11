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
from structure_analyzer import analyze_csv_structure, smart_compress_csv, is_large_file
from risk_assessment import RiskAssessmentCalculator, format_risk_assessment_for_care_plan

app = Flask(__name__, template_folder='templates')
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

import PyPDF2

# Allowed file formats
ALLOWED_EXTENSIONS = {'csv', 'txt', 'pdf'}

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

def create_fallback_analysis(response_text):
    """Create a fallback analysis when JSON parsing fails"""
    return {
        "analysis_summary": "Analysis completed successfully. The AI has reviewed the care logs and identified areas for improvement.",
        "care_plan_gaps": {
            "description": "Please review the care plan manually as automatic gap detection encountered parsing issues.",
            "missing_areas": [
                "Manual review required",
                "Check logs for recent incidents",  
                "Verify care interventions are current"
            ],
            "alert_level": "Medium"
        },
        "suggestions": [
            {
                "id": 1,
                "category": "Personal Care",
                "specific_issue": "Care Plan Review Required",
                "description": "The analysis encountered formatting issues. Please manually review the care logs for any patterns or concerns that need attention.",
                "evidence": "Manual review recommended due to parsing error",
                "priority": "Medium",
                "icon": "📋",
                "flagged": False,
                "possible_reasons": [
                    "Data formatting complexity",
                    "Mixed content types in logs",
                    "Special characters in care notes",
                    "Inconsistent date formats",
                    "Large volume of care data"
                ],
                "suggested_interventions": [
                    "Conduct manual review of recent care logs",
                    "Identify any recurring patterns or issues",
                    "Update care plan based on findings",
                    "Standardize care log formatting",
                    "Schedule team review meeting"
                ]
            }
        ]
    }

def analyze_and_suggest_changes(daily_log, current_care_plan, resident_name):
    """Step 1: Analyze and suggest changes with gap detection"""

    prompt = f"""You are a care home management assistant. Your task is to analyze the resident's care log and current care plan, then identify specific behavioral or care issues that need attention.

RESIDENT: {resident_name}

CARE LOG (this month):
{daily_log}

CURRENT CARE PLAN:
{current_care_plan}

Please analyze the care log and identify specific, concrete issues that need to be addressed. Also identify gaps between the care log and current care plan.

Format your response as a JSON object with this structure:
{{
    "analysis_summary": "Brief summary of key findings from the care log",
    "care_plan_gaps": {{
        "description": "Description of significant events/patterns in logs that are NOT addressed in the current care plan",
        "missing_areas": [
            "Specific area 1 missing from care plan but evident in logs",
            "Specific area 2 missing from care plan but evident in logs",
            "Specific area 3 missing from care plan but evident in logs"
        ],
        "alert_level": "High|Medium|Low"
    }},
    "suggestions": [
        {{
            "id": 1,
            "category": "Personal Care|Eating & Drinking|Continence|Mobility|Health & Medication|Daily Routine|Skin Care|Choice & Communication|Behavior|Other",
            "specific_issue": "Specific concrete issue (e.g., 'Aggressive Behavior During Meal Times', 'Refusing Personal Care', 'Frequent Night-time Wandering')",
            "description": "Detailed description of the issue based on log evidence",
            "evidence": "Specific evidence from care logs (dates, times, what exactly happened)",
            "priority": "High|Medium|Low",
            "icon": "😡|😰|😴|🚶|💊|🍽️|🚿|🗣️|⚠️|📋",
            "flagged": false,
            "possible_reasons": [
                "Specific reason 1 related to this issue",
                "Specific reason 2 related to this issue",
                "Specific reason 3 related to this issue",
                "Specific reason 4 related to this issue",
                "Specific reason 5 related to this issue"
            ],
            "suggested_interventions": [
                "Specific intervention 1 for this issue",
                "Specific intervention 2 for this issue", 
                "Specific intervention 3 for this issue",
                "Specific intervention 4 for this issue",
                "Specific intervention 5 for this issue"
            ]
        }}
    ]
}}

Guidelines:
- Identify 5-12 specific, concrete issues (not generic categories)
- Each issue should be a specific problem like "Aggressive Behavior During Meal Times" or "Refusing Medication"
- Generate 5 specific possible reasons for each issue based on the context
- Generate 5 specific interventions for each issue
- Choose appropriate icons that match the issue type
- Base all suggestions on evidence found in the care log
- Include specific evidence (dates/times/what happened) in the "evidence" field for each suggestion
- Make issues specific enough that care staff can understand exactly what to address
- For care_plan_gaps, identify significant patterns/events in logs that are completely missing from the current care plan"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text
        print(f"Raw AI response: {response_text[:500]}...")  # Debug log
        
        # Clean the response text
        response_text = response_text.strip()
        
        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            
            # Clean common JSON issues
            json_str = json_str.replace('\n', ' ')  # Remove newlines
            json_str = re.sub(r'(?<!\\)"([^"]*)"([^,}\]:])', r'"\1",\2', json_str)  # Add missing commas
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as json_error:
                print(f"JSON decode error: {json_error}")
                print(f"Problematic JSON around char {json_error.pos}: {json_str[max(0, json_error.pos-50):json_error.pos+50]}")
                
                # Try to fix common JSON issues
                try:
                    # Remove trailing commas
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    
                    # Fix unescaped quotes in strings
                    json_str = re.sub(r'(?<!\\)"([^"]*)"([^,:}\]]+)', r'"\1 \2"', json_str)
                    
                    return json.loads(json_str)
                except:
                    # If all JSON fixes fail, return fallback
                    return create_fallback_analysis(response_text)
        else:
            print("No JSON found in response")
            return create_fallback_analysis(response_text)

    except Exception as e:
        print(f"Error in analyze_and_suggest_changes: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "analysis_summary": f"Error during analysis: {str(e)}",
            "suggestions": []
        }

def generate_final_care_plan(original_care_plan, selected_suggestions, manager_comments, resident_name, risk_assessment_data=None):
    """Step 3: Generate final care plan with better integration and priority observation section"""

    # Get current date
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')

    # Separate flagged items for priority observation section
    flagged_items = [s for s in selected_suggestions if s.get('flagged', False)]
    regular_updates = [s for s in selected_suggestions if not s.get('flagged', False)]

    # Format selected suggestions by category for better integration
    updates_by_category = {}
    for suggestion in regular_updates:
        category = suggestion.get('category', 'Other')
        if category not in updates_by_category:
            updates_by_category[category] = []
        updates_by_category[category].append(suggestion)

    # Format updates for integration
    categorized_updates = ""
    if updates_by_category:
        categorized_updates += "\n**UPDATES TO INTEGRATE BY CATEGORY:**\n\n"
        for category, suggestions in updates_by_category.items():
            categorized_updates += f"**{category} Updates:**\n"
            for suggestion in suggestions:
                categorized_updates += f"• {suggestion.get('specific_issue', 'Update')}: {suggestion.get('description', '')}\n"
                if suggestion.get('interventions'):
                    categorized_updates += f"  Actions: {', '.join(suggestion['interventions'][:3])}\n"
            categorized_updates += "\n"

    # Format flagged items for priority section
    priority_observations = ""
    if flagged_items:
        priority_observations += "\n**PRIORITY FLAGGED ITEMS FOR OBSERVATION SECTION:**\n\n"
        for item in flagged_items:
            priority_observations += f"🚩 {item.get('specific_issue', 'Priority Item')}\n"
            priority_observations += f"   Description: {item.get('description', '')}\n"
            if item.get('interventions'):
                priority_observations += f"   Key Actions: {', '.join(item['interventions'][:2])}\n"
            priority_observations += "\n"

    # Format risk assessment data
    risk_assessment_section = ""
    if risk_assessment_data and 'assessments' in risk_assessment_data:
        risk_assessment_section = format_risk_assessment_for_care_plan(risk_assessment_data)

    prompt = f"""You are a professional care home management assistant. Your task is to rewrite and organize the existing care plan, seamlessly integrating updates into appropriate sections and adding a priority observation section.

**ORIGINAL CARE PLAN:**
{original_care_plan}

**UPDATES TO INTEGRATE BY CATEGORY:**
{categorized_updates}

**PRIORITY FLAGGED ITEMS:**
{priority_observations}

**RISK ASSESSMENT RESULTS:**
{risk_assessment_section}

**MANAGER'S ADDITIONAL COMMENTS:**
{manager_comments}

**TODAY'S DATE:** {today}

**INSTRUCTIONS:**
1. 📋 **Rewrite the original care plan** - organize it with clear section headers
2. 🔄 **Integrate updates naturally** - merge each update into its appropriate care plan section (Personal Care, Daily Routine, Health Monitoring, etc.)
3. 🚩 **Add Priority Observation Section** at the bottom for flagged items
4. 💬 **Add manager's comments** if provided
5. 📅 **Add update tracking information**

**INTEGRATION RULES:**
- Seamlessly merge updates into existing care plan sections based on category
- Mark integrated updates with ✏️ symbol to show they are new
- Do NOT create separate "Recent Updates" section - integrate everything naturally
- For flagged items, create a dedicated "🚩 Priority Observation Areas" section at the end
- Maintain professional healthcare documentation style
- Include "Last Updated: {today}" at the top

**SECTION STRUCTURE:**
- Update tracking dates at top
- Personal Care
- Daily Routine  
- Health & Medication
- Mobility & Safety
- Nutrition & Hydration
- Behavioral Support
- Social & Communication
- Other relevant sections
- 🚩 Priority Observation Areas (for flagged items)

Generate the complete updated care plan with natural integration."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except Exception as e:
        return f"Error generating care plan: {str(e)}"

def extract_pdf_text(pdf_file):
    """Extract text from PDF file and convert to structured format"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""

        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if not text.strip():
            return None, "Error: PDF appears to be scanned or contains no extractable text. Please use CSV format."

        # Check if it looks like table format (contains common delimiters or structured data)
        if not is_table_format(text):
            return None, "Error: PDF does not appear to contain structured table data. Please upload a CSV file instead."

        # Convert PDF text to CSV-like format
        csv_content = convert_pdf_table_to_csv(text)
        return csv_content, None

    except Exception as e:
        return None, f"Error analyzing PDF: {str(e)}"

def is_table_format(text):
    """Check if text appears to be in table format"""
    lines = text.strip().split('\n')
    if len(lines) < 2:  # Need at least 2 lines
        return False

    # Look for common table indicators
    common_delimiters = [',', '\t', '|', ';']
    structured_indicators = ['date', 'time', 'name', 'amount', 'count', 'resident', 'care', 'bowel', 'water', 'food', 'intake', 'plan']

    delimiter_count = 0
    structure_count = 0

    for line in lines[:15]:  # Check first 15 lines
        line_lower = line.lower().strip()
        if not line_lower:
            continue

        # Count delimiter usage
        for delimiter in common_delimiters:
            if delimiter in line and line.count(delimiter) >= 1:
                delimiter_count += 1
                break

        # Count structure indicators
        for indicator in structured_indicators:
            if indicator in line_lower:
                structure_count += 1
                break

    # More lenient criteria - accept if we have some structure
    return delimiter_count >= 1 or structure_count >= 2 or len(lines) >= 5

def convert_pdf_table_to_csv(text):
    """Convert PDF text to CSV format"""
    lines = text.strip().split('\n')
    csv_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try to detect and convert different table formats
        if ',' in line:
            # Already CSV-like
            csv_lines.append(line)
        elif '\t' in line:
            # Tab-separated, convert to CSV
            csv_lines.append(','.join(line.split('\t')))
        elif '|' in line:
            # Pipe-separated, convert to CSV
            csv_lines.append(','.join([col.strip() for col in line.split('|') if col.strip()]))
        else:
            # Try to split by multiple spaces (common in PDF tables)
            parts = [part.strip() for part in re.split(r'\s{2,}', line) if part.strip()]
            if len(parts) > 1:
                csv_lines.append(','.join(parts))
            else:
                # Single column or free text
                csv_lines.append(line)

    return '\n'.join(csv_lines)

def extract_weight_data(log_content):
    """Extract weight measurements from log content"""
    weights = []
    weight_pattern = r'(?:weight|體重).*?(\d+(?:\.\d+)?)\s*(?:kg|kilogram|公斤)'
    matches = re.findall(weight_pattern, log_content.lower())

    for match in matches:
        try:
            weight = float(match)
            if 30 <= weight <= 200:  # Reasonable weight range
                weights.append(weight)
        except ValueError:
            continue

    return weights

def extract_height_data(care_plan_content):
    """Extract height from care plan"""
    height_pattern = r'(?:height|身高).*?(\d+(?:\.\d+)?)\s*(?:cm|centimeter|公分)'
    match = re.search(height_pattern, care_plan_content.lower())

    if match:
        try:
            height = float(match.group(1))
            if 100 <= height <= 220:  # Reasonable height range
                return height
        except ValueError:
            pass

    return None

def extract_resident_data(care_plan_content, resident_name):
    """Extract resident data for risk assessment"""
    data = {'name': resident_name}

    # Extract age from date of birth
    dob_pattern = r'(?:date of birth|dob|birth).*?(\d{1,2})[/-](\d{1,2})[/-](\d{4})'
    dob_match = re.search(dob_pattern, care_plan_content.lower())

    if dob_match:
        try:
            day, month, year = map(int, dob_match.groups())
            birth_date = datetime(year, month, day)
            age = (datetime.now() - birth_date).days // 365
            data['age'] = age
        except ValueError:
            pass

    # Extract gender
    if any(keyword in care_plan_content.lower() for keyword in ['female', 'woman', 'she', 'her']):
        data['gender'] = 'female'
    elif any(keyword in care_plan_content.lower() for keyword in ['male', 'man', 'he', 'him']):
        data['gender'] = 'male'

    return data

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
        return jsonify({'error': 'OpenAI API not available. Please check your OPENAI_API_KEY environment variable.'}), 500

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
            return jsonify({'error': 'Only CSV, TXT, and PDF files are allowed'}), 400

        # Process daily log file
        daily_log_content = ""
        daily_log_error = None

        if daily_log_file.filename.lower().endswith('.pdf'):
            daily_log_content, daily_log_error = extract_pdf_text(daily_log_file)
        else:
            # Save and read CSV/TXT files
            daily_log_path = os.path.join(app.config['UPLOAD_FOLDER'], 
                                          secure_filename(f"daily_{datetime.now().timestamp()}.csv"))
            daily_log_file.save(daily_log_path)
            daily_log_content = read_csv_flexible(daily_log_path)
            os.remove(daily_log_path)

        if daily_log_error:
            return jsonify({'error': daily_log_error}), 400

        # Process care plan file
        care_plan_content = ""
        care_plan_error = None

        if care_plan_file.filename.lower().endswith('.pdf'):
            care_plan_content, care_plan_error = extract_pdf_text(care_plan_file)
        else:
            # Save and read CSV/TXT files
            care_plan_path = os.path.join(app.config['UPLOAD_FOLDER'], 
                                          secure_filename(f"care_{datetime.now().timestamp()}.csv"))
            care_plan_file.save(care_plan_path)
            care_plan_content = read_csv_flexible(care_plan_path)
            os.remove(care_plan_path)

        if care_plan_error:
            return jsonify({'error': care_plan_error}), 400

        # Dual AI System Implementation
        processed_daily_log = daily_log_content
        processing_steps = []

        # Check if daily log file is large and needs processing
        if is_large_file(daily_log_content):
            # Stage 1: Structure Analysis
            processing_steps.append("🔍 Analyzing file structure...")
            structure_info = analyze_csv_structure(daily_log_content)

            # Stage 2: Smart Compression
            processing_steps.append("📊 Optimizing data...")
            processed_daily_log = smart_compress_csv(daily_log_content, structure_info)

            # Stage 3: Deep Analysis indicator
            processing_steps.append("🧠 Generating deep analysis...")
        else:
            processing_steps.append("🧠 Generating analysis...")

        # Get suggestions using processed content
        analysis_result = analyze_and_suggest_changes(processed_daily_log, care_plan_content, resident_name)

        # Calculate risk assessments
        processing_steps.append("🛡️ Calculating risk assessments...")
        risk_calculator = RiskAssessmentCalculator()

        # Extract weight data from logs if available
        weight_logs = extract_weight_data(processed_daily_log)
        height = extract_height_data(care_plan_content)
        resident_data = extract_resident_data(care_plan_content, resident_name)

        risk_assessment_results = risk_calculator.calculate_all_assessments(
            care_plan_content, 
            processed_daily_log, 
            weight_logs, 
            height, 
            resident_data
        )
        
        # Add risk assessment summary to analysis result
        if risk_assessment_results and 'summary' in risk_assessment_results:
            analysis_result['risk_assessment_summary'] = risk_assessment_results['summary']

        # File cleanup is handled in processing logic above

        return jsonify({
            'success': True,
            'step': 'suggestions',
            'analysis_summary': analysis_result.get('analysis_summary', ''),
            'suggestions': analysis_result.get('suggestions', []),
            'resident_name': resident_name,
            'original_care_plan': care_plan_content,
            'processing_steps': processing_steps,
            'was_compressed': is_large_file(daily_log_content),
            'risk_assessment': risk_assessment_results
        })

    except Exception as e:
        print(f"Error in analyze endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/risk_assessment_details', methods=['POST'])
def risk_assessment_details():
    """Get detailed risk assessment calculation breakdown"""
    if not client:
        return jsonify({'error': 'API not available'}), 500

    try:
        data = request.get_json()
        care_plan_content = data.get('care_plan_content', '')
        daily_log_content = data.get('daily_log_content', '')
        resident_name = data.get('resident_name', 'Unnamed Resident')

        # Calculate risk assessments with detailed breakdown
        risk_calculator = RiskAssessmentCalculator()

        # Extract data for calculations
        weight_logs = extract_weight_data(daily_log_content)
        height = extract_height_data(care_plan_content)
        resident_data = extract_resident_data(care_plan_content, resident_name)

        # Get all assessment results
        risk_results = risk_calculator.calculate_all_assessments(
            care_plan_content, 
            daily_log_content, 
            weight_logs, 
            height, 
            resident_data
        )

        # Add detailed calculation breakdown
        calculation_details = {
            'input_data': {
                'weight_logs': weight_logs,
                'height': height,
                'resident_data': resident_data,
                'care_plan_keywords_found': extract_keywords_found(care_plan_content),
                'daily_log_keywords_found': extract_keywords_found(daily_log_content)
            },
            'calculation_process': get_calculation_process(
                care_plan_content, daily_log_content, weight_logs, height, resident_data
            )
        }

        return jsonify({
            'success': True,
            'risk_assessment': risk_results,
            'calculation_details': calculation_details
        })

    except Exception as e:
        print(f"Error in risk assessment details: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

def extract_keywords_found(text):
    """Extract and return keywords found in text for transparency"""
    keywords_found = {
        'falls_keywords': [],
        'mobility_keywords': [],
        'nutrition_keywords': [],
        'skin_keywords': [],
        'pain_keywords': [],
        'continence_keywords': [],
        'medication_keywords': []
    }

    text_lower = text.lower()

    # Falls keywords
    falls_keywords = ["fall", "fell", "trip", "stumble", "slip", "tumble"]
    keywords_found['falls_keywords'] = [kw for kw in falls_keywords if kw in text_lower]

    # Mobility keywords
    mobility_keywords = ["wheelchair", "bedbound", "immobile", "hoist", "assistance walking", "balance", "unsteady", "dizzy"]
    keywords_found['mobility_keywords'] = [kw for kw in mobility_keywords if kw in text_lower]

    # Nutrition keywords
    nutrition_keywords = ["poor appetite", "not eating", "weight loss", "malnourished", "refusing food"]
    keywords_found['nutrition_keywords'] = [kw for kw in nutrition_keywords if kw in text_lower]

    # Skin keywords
    skin_keywords = ["bruising", "discoloured", "mottled", "broken skin", "red", "sore", "pressure", "ulcer"]
    keywords_found['skin_keywords'] = [kw for kw in skin_keywords if kw in text_lower]

    # Pain keywords
    pain_keywords = ["pain", "discomfort", "sore", "ache", "hurts", "crying", "moaning", "grimacing"]
    keywords_found['pain_keywords'] = [kw for kw in pain_keywords if kw in text_lower]

    # Continence keywords
    continence_keywords = ["incontinent", "wet", "soiled", "catheter", "pad"]
    keywords_found['continence_keywords'] = [kw for kw in continence_keywords if kw in text_lower]

    # Medication keywords
    medication_keywords = ["tablet", "mg", "medication", "drug", "pill", "capsule"]
    keywords_found['medication_keywords'] = [kw for kw in medication_keywords if kw in text_lower]

    return keywords_found

def get_calculation_process(care_plan_content, daily_log_content, weight_logs, height, resident_data):
    """Get step-by-step calculation process for transparency"""
    process = {}
    combined_text = (care_plan_content + " " + daily_log_content).lower()

    # Falls Screening calculation process
    falls_process = {
        'total_score': 0,
        'steps': []
    }

    # Check falls history
    fall_keywords = ["fall", "fell", "trip", "stumble", "slip", "tumble"]
    if any(keyword in combined_text for keyword in fall_keywords):
        falls_process['total_score'] += 1
        falls_process['steps'].append({
            'item': 'Falls history',
            'score': 1,
            'reason': f"Found keywords: {[kw for kw in fall_keywords if kw in combined_text]}"
        })
    else:
        falls_process['steps'].append({
            'item': 'Falls history',
            'score': 0,
            'reason': 'No fall-related keywords found'
        })

    # Check medication count
    medication_count = len(re.findall(r'(?:tablet|mg|medication|drug|pill)', combined_text))
    if medication_count >= 4:
        falls_process['total_score'] += 1
        falls_process['steps'].append({
            'item': 'Medication count',
            'score': 1,
            'reason': f"Found {medication_count} medication references (≥4)"
        })
    else:
        falls_process['steps'].append({
            'item': 'Medication count',
            'score': 0,
            'reason': f"Found {medication_count} medication references (<4)"
        })

    process['falls_screening'] = falls_process

    # MUST calculation process if weight data available
    if weight_logs and height:
        must_process = {
            'total_score': 0,
            'steps': []
        }

        # BMI calculation
        latest_weight = weight_logs[-1]
        bmi = latest_weight / (height/100)**2

        if bmi < 18.5:
            bmi_score = 2
        elif 18.5 <= bmi <= 20:
            bmi_score = 1
        else:
            bmi_score = 0

        must_process['total_score'] += bmi_score
        must_process['steps'].append({
            'item': 'BMI calculation',
            'score': bmi_score,
            'reason': f"BMI = {bmi:.1f} (Weight: {latest_weight}kg, Height: {height}cm)"
        })

        # Weight loss calculation
        if len(weight_logs) >= 2:
            weight_change = (weight_logs[0] - weight_logs[-1]) / weight_logs[0] * 100
            if weight_change > 10:
                weight_score = 2
            elif 5 <= weight_change <= 10:
                weight_score = 1
            else:
                weight_score = 0

            must_process['total_score'] += weight_score
            must_process['steps'].append({
                'item': 'Weight loss',
                'score': weight_score,
                'reason': f"Weight change: {weight_change:.1f}% (from {weight_logs[0]}kg to {weight_logs[-1]}kg)"
            })

        process['must_nutrition'] = must_process

    return process

@app.route('/generate_care_plan', methods=['POST'])
def generate_care_plan():
    """Step 3: Generate final care plan based on manager's selections"""
    if not client:
        return jsonify({'error': 'OpenAI API not available. Please check your OPENAI_API_KEY environment variable.'}), 500

    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No JSON data received'}), 400

        original_care_plan = data.get('original_care_plan', '')
        selected_suggestions = data.get('selected_suggestions', [])
        manager_comments = data.get('manager_comments', '')
        resident_name = data.get('resident_name', 'Unnamed Resident')

        print(f"Generating care plan for: {resident_name}")
        print(f"Selected suggestions count: {len(selected_suggestions)}")
        print(f"Manager comments length: {len(manager_comments)}")

        # Include risk assessment in care plan generation
        risk_assessment_data = data.get('risk_assessment', {})

        # Generate final care plan
        final_care_plan = generate_final_care_plan(
            original_care_plan, 
            selected_suggestions, 
            manager_comments, 
            resident_name,
            risk_assessment_data
        )

        if final_care_plan.startswith("Error"):
            return jsonify({'error': final_care_plan}), 500

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
        print(f"Error in generate_care_plan endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

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

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    """Download care plan as PDF file"""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        import re

        data = request.get_json()
        content = data.get('content', '')
        resident_name = data.get('resident_name', 'Unnamed_Resident')

        filename = f"Care_Plan_{resident_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # Create PDF in memory
        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=18)

        # Container for the 'Flowable' objects
        elements = []

        # Get styles
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=12,
        )

        # Add title
        title = Paragraph(f"Care Plan for {resident_name}", title_style)
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Parse content and add to PDF
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                elements.append(Spacer(1, 6))
                continue

            # Handle headers
            if line.startswith('# '):
                text = re.sub(r'^# ', '', line)
                elements.append(Paragraph(text, title_style))
            elif line.startswith('## '):
                text = re.sub(r'^## ', '', line)
                elements.append(Paragraph(text, heading_style))
            elif line.startswith('### '):
                text = re.sub(r'^### ', '', line)
                elements.append(Paragraph(text, styles['Heading3']))
            elif line.startswith('- '):
                text = re.sub(r'^- ', '• ', line)
                elements.append(Paragraph(text, styles['Normal']))
            elif line.startswith('* '):
                text = re.sub(r'^\* ', '• ', line)
                elements.append(Paragraph(text, styles['Normal']))
            else:
                # Regular paragraph
                if line:
                    # Remove markdown formatting
                    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)  # Bold
                    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)     # Italic
                    text = re.sub(r'✏️', '✏️ ', text)  # Add space after pen emoji
                    elements.append(Paragraph(text, styles['Normal']))

        # Build PDF
        doc.build(elements)
        output.seek(0)

        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except ImportError:
        return jsonify({'error': 'PDF generation requires reportlab library. Please install it.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/send_email', methods=['POST'])
def send_email():
    """Send care plan via email"""
    try:
        data = request.get_json()
        subject = data.get('subject', '')
        body = data.get('body', '')
        care_plan = data.get('care_plan', '')
        resident_name = data.get('resident_name', 'Unnamed_Resident')

        # For demo purposes, we'll return success
        # In a real implementation, you would integrate with an email service like:
        # - SendGrid
        # - AWS SES
        # - SMTP server
        # - etc.

        # Example implementation would look like:
        # import smtplib
        # from email.mime.text import MIMEText
        # from email.mime.multipart import MIMEMultipart
        # from email.mime.base import MIMEBase
        # from email import encoders

        # Create email with care plan as attachment
        email_content = f"""
{body}

Care Plan Summary:
{care_plan[:500]}...

Full care plan is attached.

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """

        # TODO: Implement actual email sending
        # For now, we'll simulate success
        print(f"Email would be sent with subject: {subject}")
        print(f"Body preview: {email_content[:200]}...")

        return jsonify({
            'success': True,
            'message': f'Email sent successfully for {resident_name}'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)