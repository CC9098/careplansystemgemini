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

def analyze_and_suggest_changes(daily_log, current_care_plan, resident_name):
    """Step 1: Analyze and suggest changes"""

    prompt = f"""You are a care home management assistant. Your task is to analyze the resident's care log and current care plan, then identify specific behavioral or care issues that need attention.

RESIDENT: {resident_name}

CARE LOG (this month):
{daily_log}

CURRENT CARE PLAN:
{current_care_plan}

Please analyze the care log and identify specific, concrete issues that need to be addressed. For each issue, provide customized possible reasons and suggested interventions based on the specific situation.

Format your response as a JSON object with this structure:
{{
    "analysis_summary": "Brief summary of key findings from the care log",
    "suggestions": [
        {{
            "id": 1,
            "category": "Personal Care|Eating & Drinking|Continence|Mobility|Health & Medication|Daily Routine|Skin Care|Choice & Communication|Behavior|Other",
            "specific_issue": "Specific concrete issue (e.g., 'Aggressive Behavior During Meal Times', 'Refusing Personal Care', 'Frequent Night-time Wandering')",
            "description": "Detailed description of the issue based on log evidence",
            "priority": "High|Medium|Low",
            "icon": "😡|😰|😴|🚶|💊|🍽️|🚿|🗣️|⚠️|📋",
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
- Make issues specific enough that care staff can understand exactly what to address"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
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
    """Step 3: Generate final care plan by integrating selected content without creating new content"""
    
    # Get current date
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Format selected suggestions exactly as manager selected them
    selected_updates = ""
    if selected_suggestions:
        selected_updates += "\n## ✏️ Recent Updates\n\n"
        
        for i, suggestion in enumerate(selected_suggestions, 1):
            selected_updates += f"### ✏️ {suggestion.get('specific_issue', suggestion.get('suggestion', 'Update'))}\n"
            selected_updates += f"**Issue:** {suggestion.get('description', suggestion.get('suggestion', ''))}\n\n"
            
            if suggestion.get('reasons'):
                selected_updates += f"**Contributing Factors:**\n"
                for reason in suggestion['reasons']:
                    selected_updates += f"• {reason}\n"
                selected_updates += "\n"
            
            if suggestion.get('interventions'):
                selected_updates += f"**Actions to Take:**\n"
                for intervention in suggestion['interventions']:
                    selected_updates += f"• {intervention}\n"
                selected_updates += "\n"

    prompt = f"""You are a professional care home management assistant. Your task is to rewrite and organize the existing care plan, incorporating the manager's selected updates exactly as provided.

**ORIGINAL CARE PLAN:**
{original_care_plan}

**MANAGER'S SELECTED UPDATES TO INTEGRATE:**
{selected_updates}

**MANAGER'S ADDITIONAL COMMENTS:**
{manager_comments}

**TODAY'S DATE:** {today}

**INSTRUCTIONS:**
1. 📋 **Rewrite the original care plan** - keep all existing content but organize it clearly and concisely
2. 🔄 **Integrate the selected updates exactly as provided** - do not modify or create new content for the updates
3. 💬 **Add manager's comments** if provided
4. 📅 **Add update tracking information**

**IMPORTANT RULES:**
- Do NOT create or modify the content of the selected updates
- Do NOT add new interventions beyond what the manager selected
- Only reformat and organize existing content clearly
- Keep the ✏️ symbols only where they already appear in the selected updates
- Maintain all original care plan content unless it directly conflicts with selected updates
- Include "Last Updated: {today}" at the top
- If there was a previous update date in the original plan, preserve it as "Previous Update: [date]"

**FORMAT REQUIREMENTS:**
- Start with update tracking dates
- Clear section headers (Personal Care, Daily Routine, Health Monitoring, etc.)
- Professional healthcare documentation style
- Organize content logically and concisely

Generate the complete updated care plan following these exact requirements."""

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

        # File cleanup is handled in processing logic above

        return jsonify({
            'success': True,
            'step': 'suggestions',
            'analysis_summary': analysis_result.get('analysis_summary', ''),
            'suggestions': analysis_result.get('suggestions', []),
            'resident_name': resident_name,
            'original_care_plan': care_plan_content,
            'processing_steps': processing_steps,
            'was_compressed': is_large_file(daily_log_content)
        })

    except Exception as e:
        print(f"Error in analyze endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/generate_care_plan', methods=['POST'])
def generate_care_plan():
    """Step 3: Generate final care plan based on manager's selections"""
    if not client:
        return jsonify({'error': 'Claude API not available. Please check your CLAUDE environment variable.'}), 500

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

        # Generate final care plan
        final_care_plan = generate_final_care_plan(
            original_care_plan, 
            selected_suggestions, 
            manager_comments, 
            resident_name
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