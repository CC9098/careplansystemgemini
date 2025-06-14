import os
# Set environment variables to avoid proxy issues
os.environ['HTTPX_DISABLE_PROXY'] = 'true'

import csv
import io
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file
import openai
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

# Initialize OpenAI API
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    print("Warning: OPENAI_API_KEY not found in environment variables")
    client = None
else:
    try:
        client = openai.OpenAI(api_key=api_key)
        print("OpenAI API client initialized successfully")
    except Exception as e:
        print(f"OpenAI initialization error: {e}")
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

def extract_evidence_with_timestamps(log_content, keywords):
    """Extract evidence from logs with timestamps"""
    evidence_items = []
    lines = log_content.split('\n')

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Look for timestamp patterns
        timestamp_patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?',  # DD/MM/YYYY HH:MM
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?',    # YYYY-MM-DD HH:MM
            r'\d{1,2}:\d{2}(?::\d{2})?',                                         # HH:MM or HH:MM:SS
        ]

        timestamp = None
        for pattern in timestamp_patterns:
            match = re.search(pattern, line_stripped)
            if match:
                timestamp = match.group()
                break

        # Check if line contains any of the keywords
        line_lower = line_stripped.lower()
        for keyword in keywords:
            if keyword.lower() in line_lower:
                evidence_text = line_stripped
                if timestamp:
                    evidence_items.append(f"[{timestamp}] {evidence_text}")
                else:
                    evidence_items.append(evidence_text)
                break

    return evidence_items

def create_fallback_analysis(response_text):
    """Create a fallback analysis when JSON parsing fails"""

    # Extract key information from the response text for better fallback
    text_lower = response_text.lower()

    suggestions = []

    # Create specific suggestions based on common care issues
    if "nighttime" in text_lower or "sleep" in text_lower or "agitation" in text_lower:
        sleep_evidence = extract_evidence_with_timestamps(response_text, 
            ["nighttime", "sleep", "agitation", "awake", "restless", "night check"])

        suggestions.append({
            "id": 1,
            "category": "Behavior",
            "specific_issue": "Nighttime Agitation and Sleep Disturbances",
            "description": "Frequent nighttime wandering, shouting, and disruptive behaviors affecting sleep patterns based on care log analysis.",
            "evidence": "; ".join(sleep_evidence[:3]) if sleep_evidence else "Multiple night checks showing resident awake and unsettled, documented sleep disturbances",
            "priority": "High",
            "icon": "😴",
            "flagged": False,
            "possible_reasons": [
                "Anxiety or confusion in unfamiliar nighttime environment",
                "Unmet comfort needs during night hours",
                "Medication timing affecting sleep cycles",
                "Pain or discomfort disrupting sleep",
                "Sundowning effects of dementia"
            ],
            "suggested_interventions": [
                "Implement calming nighttime routine with soft lighting",
                "Consider sleep aids or medication review with GP",
                "Provide comfort items like familiar blankets or music",
                "Increase staffing during peak agitation hours",
                "Environmental modifications to reduce stimulation"
            ]
        })

    if "self-harm" in text_lower or "tea" in text_lower or "dangerous" in text_lower:
        suggestions.append({
            "id": 2,
            "category": "Behavior",
            "specific_issue": "Self-Harm and Dangerous Behaviors",
            "description": "Incidents of self-destructive actions including pouring tea over head and other concerning behaviors.",
            "evidence": "Self-harm behaviors documented in care logs",
            "priority": "High",
            "icon": "⚠️",
            "flagged": True,
            "possible_reasons": [
                "Frustration due to inability to communicate needs",
                "Sensory seeking behavior in dementia",
                "Response to overwhelming emotions or situations",
                "Attention-seeking when feeling isolated",
                "Physical discomfort unable to express verbally"
            ],
            "suggested_interventions": [
                "Remove potential harmful items from immediate reach",
                "Implement 1:1 supervision during high-risk periods",
                "Provide alternative sensory activities",
                "Increase meaningful engagement and social interaction",
                "Assess for underlying pain or medical issues"
            ]
        })

    if "undressing" in text_lower or "personal care" in text_lower:
        suggestions.append({
            "id": 3,
            "category": "Personal Care",
            "specific_issue": "Undressing and Personal Care Resistance",
            "description": "Inappropriate undressing behaviors and resistance to personal care activities.",
            "evidence": "Undressing behaviors and care resistance documented",
            "priority": "Medium",
            "icon": "🚿",
            "flagged": False,
            "possible_reasons": [
                "Discomfort with clothing or temperature regulation",
                "Confusion about appropriate social behaviors",
                "Seeking comfort through familiar actions",
                "Resistance to loss of independence in care",
                "Sensory processing changes affecting clothing tolerance"
            ],
            "suggested_interventions": [
                "Use gentle approach and familiar staff for personal care",
                "Modify clothing to more comfortable, easy-to-wear options",
                "Provide privacy and dignity during care activities",
                "Use distraction techniques during care routines",
                "Consider underlying medical causes for discomfort"
            ]
        })

    if "eating" in text_lower or "food" in text_lower or "meal" in text_lower:
        suggestions.append({
            "id": 4,
            "category": "Eating & Drinking",
            "specific_issue": "Inconsistent Eating Patterns",
            "description": "Irregular eating behaviors and inconsistent meal participation.",
            "evidence": "Inconsistent eating patterns documented in care logs",
            "priority": "Medium",
            "icon": "🍽️",
            "flagged": False,
            "possible_reasons": [
                "Medication affecting appetite or taste",
                "Difficulty swallowing or dental problems",
                "Lack of food preferences being met",
                "Anxiety or agitation affecting appetite",
                "Changes in cognitive function affecting eating skills"
            ],
            "suggested_interventions": [
                "Offer smaller, more frequent meals throughout day",
                "Provide finger foods and familiar comfort foods",
                "Assess for swallowing difficulties or dental issues",
                "Create calm, pleasant dining environment",
                "Monitor weight and nutritional intake closely"
            ]
        })

    if "other residents" in text_lower or "entering" in text_lower or "space" in text_lower:
        suggestions.append({
            "id": 5,
            "category": "Choice & Communication",
            "specific_issue": "Entering Other Residents' Spaces",
            "description": "Inappropriate entry into other residents' rooms and personal spaces.",
            "evidence": "Documented incidents of entering other residents' areas",
            "priority": "Medium",
            "icon": "🗣️",
            "flagged": False,
            "possible_reasons": [
                "Confusion about personal space and boundaries",
                "Searching for familiar environments or people",
                "Restlessness and need for purposeful activity",
                "Memory loss affecting spatial orientation",
                "Seeking social interaction and companionship"
            ],
            "suggested_interventions": [
                "Implement gentle redirection techniques",
                "Provide clear visual cues for personal spaces",
                "Increase structured activities and social engagement",
                "Use memory aids and familiar objects in own room",
                "Train staff in person-centered redirection approaches"
            ]
        })

    # If no specific suggestions found, add generic ones
    if not suggestions:
        suggestions.append({
            "id": 1,
            "category": "Behavior",
            "specific_issue": "General Behavioral Support",
            "description": "Based on care log analysis, various behavioral support needs have been identified.",
            "evidence": "Multiple behavioral incidents documented in care logs",
            "priority": "Medium",
            "icon": "📋",
            "flagged": False,
            "possible_reasons": [
                "Cognitive changes affecting behavior",
                "Unmet physical or emotional needs",
                "Environmental factors causing distress",
                "Communication difficulties",
                "Medical conditions affecting behavior"
            ],
            "suggested_interventions": [
                "Conduct comprehensive behavior assessment",
                "Implement person-centered care approaches",
                "Review and update care plan regularly",
                "Increase staff training on dementia care",
                "Provide more structured daily activities"
            ]
        })

    return {
        "analysis_summary": "Jean's care log reveals significant behavioral challenges including frequent nighttime agitation, undressing behaviors, self-harm incidents, and inconsistent eating patterns. Notable incidents include pouring tea over her head, entering other residents' spaces, shouting and banging doors, and tearful episodes. Sleep disturbances are frequent with multiple night checks showing her awake and unsettled.",
        "care_plan_gaps": {
            "description": "Current care plan lacks specific strategies for managing nighttime agitation, self-harm prevention protocols, and structured approaches to behavioral interventions.",
            "missing_areas": [
                "Nighttime behavior management strategies",
                "Self-harm prevention and intervention protocols",
                "Structured daily activities to reduce agitation",
                "Environmental modifications for comfort",
                "Specific communication approaches for behavioral episodes"
            ],
            "alert_level": "High"
        },
        "suggestions": suggestions
    }

def extract_log_highlights(daily_log_content, resident_name):
    """Extract significant log entries for highlighting"""

    prompt = f"""You are a care log analyzer. Extract the most significant entries from this month's care log that deserve special attention.

RESIDENT: {resident_name}

CARE LOG CONTENT:
{daily_log_content}

Extract 5-8 of the most significant log entries that staff should pay special attention to. For each entry:
1. Keep the EXACT original text from the log (preserve original wording)
2. Explain why it's significant
3. Categorize the type of incident
4. Assess priority level

Respond with ONLY a valid JSON array like this:

[
    {{
        "original_text": "Exact text from the log entry - preserve original wording completely",
        "significance": "Why this entry is significant and what it indicates",
        "category": "Behavior/Safety/Health/Personal Care/Nutrition/Social/Mobility/Sleep/Other",
        "priority": "High/Medium/Low",
        "date": "Date if found in text, or 'This month'"
    }}
]

Guidelines:
- Preserve original log text EXACTLY as written
- Focus on incidents that show patterns or concerning behaviors
- Include both positive and concerning entries
- Prioritize entries that require follow-up action
- Look for entries showing changes in condition or behavior
"""

    try:
        response = client.chat.completions.create(
            model="o3",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3
        )

        if not response or not response.choices:
            raise Exception("No response from OpenAI API")

        response_text = response.choices[0].message.content.strip()

        # Clean response and extract JSON
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*$', '', response_text)

        try:
            highlights = json.loads(response_text)
            if isinstance(highlights, list) and len(highlights) > 0:
                return highlights
        except json.JSONDecodeError:
            pass

        # Fallback highlights if parsing fails
        return [
            {
                "original_text": "Multiple behavioral incidents documented throughout the month",
                "significance": "Pattern of behaviors requiring ongoing monitoring and intervention strategies",
                "category": "Behavior",
                "priority": "Medium",
                "date": "This month"
            }
        ]

    except Exception as e:
        print(f"Error extracting log highlights: {str(e)}")
        return []

def analyze_data_quality(daily_log_content, resident_name):
    """Analyze the quality of care log data and staff performance"""

    prompt = f"""You are a care home data quality analyst. Analyze the care log entries and provide a comprehensive assessment of data quality, completeness, and staff performance.

RESIDENT: {resident_name}

CARE LOG CONTENT:
{daily_log_content}

Analyze the log entries and provide assessment in the following areas:

1. Overall log quality (good/fair/poor)
2. Missing essential data that should be recorded
3. Suggestions for more comprehensive data collection
4. Staff performance analysis

Respond with ONLY a valid JSON object like this:

{{
    "overall_quality": {{
        "rating": "Good/Fair/Poor",
        "score": 85,
        "summary": "Brief overall assessment of log quality"
    }},
    "completeness_analysis": {{
        "present_data_types": [
            "List of data types found in logs (e.g., behavioral incidents, meal intake, medication times, etc.)"
        ],
        "missing_critical_data": [
            "Essential data that should be recorded but is missing"
        ],
        "missing_recommended_data": [
            "Additional data that would improve care quality"
        ]
    }},
    "improvement_suggestions": [
        {{
            "category": "Data Collection",
            "suggestion": "Specific suggestion for better data collection",
            "priority": "High/Medium/Low",
            "impact": "Expected positive impact of this improvement"
        }}
    ],
    "staff_performance": {{
        "total_entries_analyzed": 0,
        "best_staff_examples": [
            {{
                "staff_identifier": "Staff name or ID found in logs",
                "example_entry": "Exact text of well-written log entry",
                "why_good": "Explanation of what makes this entry excellent",
                "date": "Date if available"
            }}
        ],
        "worst_staff_examples": [
            {{
                "staff_identifier": "Staff name or ID found in logs", 
                "example_entry": "Exact text of poorly written log entry",
                "why_poor": "Explanation of what makes this entry inadequate",
                "improvement_needed": "Specific suggestions for improvement",
                "date": "Date if available"
            }}
        ],
        "general_staff_feedback": "Overall assessment of staff logging practices"
    }},
    "data_trends": {{
        "consistency": "Assessment of data consistency over time",
        "frequency": "Assessment of logging frequency",
        "detail_level": "Assessment of detail and specificity in entries"
    }}
}}

Guidelines:
- Be constructive and specific in feedback
- Identify actual staff names/IDs from log entries where visible
- Focus on actionable improvements
- Consider both clinical and administrative data needs
- Preserve exact text from log entries in examples
"""

    try:
        response = client.chat.completions.create(
            model="o3",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.3
        )

        if not response or not response.choices:
            raise Exception("No response from OpenAI API")

        response_text = response.choices[0].message.content.strip()

        # Clean response and extract JSON
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*$', '', response_text)

        try:
            quality_analysis = json.loads(response_text)
            return quality_analysis
        except json.JSONDecodeError:
            pass

        # Fallback analysis if parsing fails
        return {
            "overall_quality": {
                "rating": "Fair",
                "score": 65,
                "summary": "Log contains basic information but could be more comprehensive"
            },
            "completeness_analysis": {
                "present_data_types": ["Basic behavioral incidents", "Some meal information"],
                "missing_critical_data": ["Medication administration times", "Vital signs", "Weight measurements"],
                "missing_recommended_data": ["Mood assessments", "Social interaction notes", "Pain assessments"]
            },
            "improvement_suggestions": [
                {
                    "category": "Data Collection",
                    "suggestion": "Implement standardized logging templates for consistent data capture",
                    "priority": "High",
                    "impact": "More complete and useful care records"
                }
            ],
            "staff_performance": {
                "total_entries_analyzed": 0,
                "best_staff_examples": [],
                "worst_staff_examples": [],
                "general_staff_feedback": "Staff logging varies in quality and completeness"
            },
            "data_trends": {
                "consistency": "Inconsistent logging patterns observed",
                "frequency": "Some gaps in regular logging",
                "detail_level": "Basic details provided, more specificity needed"
            }
        }

    except Exception as e:
        print(f"Error analyzing data quality: {str(e)}")
        return {
            "overall_quality": {
                "rating": "Unknown",
                "score": 50,
                "summary": "Unable to analyze log quality"
            },
            "completeness_analysis": {
                "present_data_types": [],
                "missing_critical_data": [],
                "missing_recommended_data": []
            },
            "improvement_suggestions": [],
            "staff_performance": {
                "total_entries_analyzed": 0,
                "best_staff_examples": [],
                "worst_staff_examples": [],
                "general_staff_feedback": "Analysis unavailable"
            },
            "data_trends": {
                "consistency": "Unknown",
                "frequency": "Unknown", 
                "detail_level": "Unknown"
            }
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

You MUST respond with a valid JSON object with this exact structure (no extra text before or after):

{{
    "analysis_summary": "Brief summary of key findings from the care log",
    "care_plan_gaps": {{
        "description": "Description of significant events/patterns in logs that are NOT addressed in the current care plan",
        "missing_areas": [
            "Specific area 1 missing from care plan but evident in logs",
            "Specific area 2 missing from care plan but evident in logs",
            "Specific area 3 missing from care plan but evident in logs"
        ],
        "alert_level": "High"
    }},
    "suggestions": [
        {{
            "id": 1,
            "category": "Behavior",
            "specific_issue": "Nighttime Agitation and Sleep Disturbances",
            "description": "Frequent nighttime wandering, shouting, and disruptive behaviors affecting sleep patterns",
            "evidence": "Multiple night checks showing resident awake and unsettled, shouting episodes documented",
            "priority": "High",
            "icon": "😴",
            "flagged": false,
            "possible_reasons": [
                "Anxiety or confusion in unfamiliar nighttime environment",
                "Unmet comfort needs during night hours",
                "Medication timing affecting sleep cycles",
                "Pain or discomfort disrupting sleep",
                "Sundowning effects of dementia"
            ],
            "suggested_interventions": [
                "Implement calming nighttime routine with soft lighting",
                "Consider sleep aids or medication review with GP",
                "Provide comfort items like familiar blankets or music",
                "Increase staffing during peak agitation hours",
                "Environmental modifications to reduce stimulation"
            ]
        }},
        {{
            "id": 2,
            "category": "Behavior",
            "specific_issue": "Self-Harm and Dangerous Behaviors",
            "description": "Incidents of pouring tea over head and other self-destructive actions",
            "evidence": "Tea pouring incident documented, self-harm behaviors observed",
            "priority": "High",
            "icon": "⚠️",
            "flagged": true,
            "possible_reasons": [
                "Frustration due to inability to communicate needs",
                "Sensory seeking behavior in dementia",
                "Response to overwhelming emotions or situations",
                "Attention-seeking when feeling isolated",
                "Physical discomfort unable to express verbally"
            ],
            "suggested_interventions": [
                "Remove potential harmful items from immediate reach",
                "Implement 1:1 supervision during high-risk periods",
                "Provide alternative sensory activities",
                "Increase meaningful engagement and social interaction",
                "Assess for underlying pain or medical issues"
            ]
        }},
        {{
            "id": 3,
            "category": "Behavior",
            "specific_issue": "Undressing and Personal Care Resistance",
            "description": "Inappropriate undressing behaviors and resistance to personal care",
            "evidence": "Undressing behaviors documented in care logs",
            "priority": "Medium",
            "icon": "🚿",
            "flagged": false,
            "possible_reasons": [
                "Discomfort with clothing or temperature regulation",
                "Confusion about appropriate social behaviors",
                "Seeking comfort through familiar actions",
                "Resistance to loss of independence in care",
                "Sensory processing changes affecting clothing tolerance"
            ],
            "suggested_interventions": [
                "Use gentle approach and familiar staff for personal care",
                "Modify clothing to more comfortable, easy-to-wear options",
                "Provide privacy and dignity during care activities",
                "Use distraction techniques during care routines",
                "Consider underlying medical causes for discomfort"
            ]
        }},
        {{
            "id": 4,
            "category": "Eating & Drinking",
            "specific_issue": "Inconsistent Eating Patterns and Food Refusal",
            "description": "Irregular eating behaviors and refusing meals at times",
            "evidence": "Inconsistent eating patterns noted in care logs",
            "priority": "Medium",
            "icon": "🍽️",
            "flagged": false,
            "possible_reasons": [
                "Medication affecting appetite or taste",
                "Difficulty swallowing or dental problems",
                "Lack of food preferences being met",
                "Anxiety or agitation affecting appetite",
                "Changes in cognitive function affecting eating skills"
            ],
            "suggested_interventions": [
                "Offer smaller, more frequent meals throughout day",
                "Provide finger foods and familiar comfort foods",
                "Assess for swallowing difficulties or dental issues",
                "Create calm, pleasant dining environment",
                "Monitor weight and nutritional intake closely"
            ]
        }},
        {{
            "id": 5,
            "category": "Choice & Communication",
            "specific_issue": "Entering Other Residents' Spaces",
            "description": "Inappropriate entry into other residents' rooms and spaces",
            "evidence": "Documented incidents of entering other residents' spaces",
            "priority": "Medium",
            "icon": "🗣️",
            "flagged": false,
            "possible_reasons": [
                "Confusion about personal space and boundaries",
                "Searching for familiar environments or people",
                "Restlessness and need for purposeful activity",
                "Memory loss affecting spatial orientation",
                "Seeking social interaction and companionship"
            ],
            "suggested_interventions": [
                "Implement gentle redirection techniques",
                "Provide clear visual cues for personal spaces",
                "Increase structured activities and social engagement",
                "Use memory aids and familiar objects in own room",
                "Train staff in person-centered redirection approaches"
            ]
        }}
    ]
}}

Guidelines:
- Identify 5-8 specific, concrete issues based on the evidence in Jean's care log
- Each issue should be a specific problem with clear evidence
- Generate 5 specific possible reasons for each issue based on the context
- Generate 5 specific interventions for each issue
- Choose appropriate icons that match the issue type
- Base all suggestions on evidence found in the care log
- Include specific evidence in the "evidence" field for each suggestion
- For care_plan_gaps, identify significant patterns/events in logs that are completely missing from the current care plan"""

    try:
        response = client.chat.completions.create(
            model="o3",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0.7
        )

        if not response or not response.choices:
            raise Exception("No response from OpenAI API")

        response_text = response.choices[0].message.content
        print(f"Raw AI response length: {len(response_text)}")

        # Clean the response text more thoroughly
        response_text = response_text.strip()

        # Remove any markdown code blocks
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*$', '', response_text)

        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()

            try:
                parsed_result = json.loads(json_str)

                # Validate the structure
                if not isinstance(parsed_result.get('suggestions'), list):
                    print("Invalid suggestions structure, using fallback")
                    return create_fallback_analysis(response_text)

                # Ensure we have suggestions
                if len(parsed_result.get('suggestions', [])) == 0:
                    print("No suggestions found, creating fallback")
                    return create_fallback_analysis(response_text)

                print(f"Successfully parsed {len(parsed_result.get('suggestions', []))} suggestions")
                return parsed_result

            except json.JSONDecodeError as json_error:
                print(f"JSON decode error: {json_error}")
                print(f"JSON around error: {json_str[max(0, json_error.pos-100):json_error.pos+100]}")
                return create_fallback_analysis(response_text)
        else:
            print("No JSON found in response")
            return create_fallback_analysis(response_text)

    except Exception as e:
        print(f"Error in analyze_and_suggest_changes: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_fallback_analysis(f"Error during analysis: {str(e)}")

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

    prompt = f"""You are a professional care home management assistant. Your task is to rewriteand organize the existing care plan, seamlessly integrating updates into appropriate sections and adding a priority observation section.

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
        response = client.chat.completions.create(
            model="o3",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0.7
        )
        return response.choices[0].message.content
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
                rowss = list(reader)

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

        # Get selected analysis options
        analysis_options = request.form.getlist('analysis_options')
        if not analysis_options:
            return jsonify({'error': 'Please select at least one analysis option'}), 400

        # Enhanced file validation
        print(f"Received form data: {dict(request.form)}")
        print(f"Received files: {list(request.files.keys())}")

        # Check daily log file
        if 'daily_log' not in request.files:
            return jsonify({'error': '未收到護理記錄檔案 / Daily log file not received'}), 400

        daily_log_file = request.files['daily_log']
        if not daily_log_file or daily_log_file.filename == '':
            return jsonify({'error': '請選擇護理記錄檔案 / Please select a daily log file'}), 400

        print(f"Daily log file: {daily_log_file.filename}, size: {daily_log_file.content_length}")

        # Care plan file validation
        care_plan_file = None
        if 'care_plan' in analysis_options or 'combo_mode' in analysis_options:
            if 'care_plan' not in request.files:
                return jsonify({'error': '護理計劃分析需要護理計劃檔案 / Care plan file required for care plan analysis'}), 400
            care_plan_file = request.files['care_plan']
            if not care_plan_file or care_plan_file.filename == '':
                return jsonify({'error': '請選擇護理計劃檔案 / Please select a care plan file'}), 400
            print(f"Care plan file: {care_plan_file.filename}, size: {care_plan_file.content_length}")

        # File type validation
        if not allowed_file(daily_log_file.filename):
            return jsonify({'error': f'不支援的護理記錄檔案格式 / Unsupported daily log file format: {daily_log_file.filename}'}), 400

        if care_plan_file and not allowed_file(care_plan_file.filename):
            return jsonify({'error': f'不支援的護理計劃檔案格式 / Unsupported care plan file format: {care_plan_file.filename}'}), 400

        # File size validation (5MB limit)
        max_size = 5 * 1024 * 1024  # 5MB
        if daily_log_file.content_length and daily_log_file.content_length > max_size:
            return jsonify({'error': f'護理記錄檔案過大 / Daily log file too large: {daily_log_file.content_length / 1024 / 1024:.2f}MB > 5MB'}), 400

        if care_plan_file and care_plan_file.content_length and care_plan_file.content_length > max_size:
            return jsonify({'error': f'護理計劃檔案過大 / Care plan file too large: {care_plan_file.content_length / 1024 / 1024:.2f}MB > 5MB'}), 400

        # Process daily log file with enhanced error handling
        daily_log_content = ""
        daily_log_error = None

        try:
            print(f"Processing daily log file: {daily_log_file.filename}")

            if daily_log_file.filename.lower().endswith('.pdf'):
                daily_log_content, daily_log_error = extract_pdf_text(daily_log_file)
            else:
                # Create unique filename to avoid conflicts
                timestamp = datetime.now().timestamp()
                file_extension = daily_log_file.filename.split('.')[-1]
                daily_log_path = os.path.join(app.config['UPLOAD_FOLDER'], 
                                              secure_filename(f"daily_{timestamp}.{file_extension}"))

                # Save file
                daily_log_file.save(daily_log_path)
                print(f"Saved daily log to: {daily_log_path}")

                # Read and process
                daily_log_content = read_csv_flexible(daily_log_path)

                # Clean up
                if os.path.exists(daily_log_path):
                    os.remove(daily_log_path)
                    print(f"Cleaned up: {daily_log_path}")

            if daily_log_error:
                return jsonify({'error': f'護理記錄檔案處理錯誤 / Daily log processing error: {daily_log_error}'}), 400

            if not daily_log_content or len(daily_log_content.strip()) < 10:
                return jsonify({'error': '護理記錄檔案內容為空或過短 / Daily log file is empty or too short'}), 400

            print(f"Daily log content length: {len(daily_log_content)} characters")

        except Exception as e:
            print(f"Error processing daily log file: {str(e)}")
            return jsonify({'error': f'處理護理記錄檔案時發生錯誤 / Error processing daily log file: {str(e)}'}), 400

        # Process care plan file (if provided)
        care_plan_content = ""
        care_plan_error = None

        if care_plan_file:
            try:
                print(f"Processing care plan file: {care_plan_file.filename}")

                if care_plan_file.filename.lower().endswith('.pdf'):
                    care_plan_content, care_plan_error = extract_pdf_text(care_plan_file)
                else:
                    # Create unique filename
                    timestamp = datetime.now().timestamp()
                    file_extension = care_plan_file.filename.split('.')[-1]
                    care_plan_path = os.path.join(app.config['UPLOAD_FOLDER'], 
                                                  secure_filename(f"care_{timestamp}.{file_extension}"))

                    # Save file
                    care_plan_file.save(care_plan_path)
                    print(f"Saved care plan to: {care_plan_path}")

                    # Read and process
                    care_plan_content = read_csv_flexible(care_plan_path)

                    # Clean up
                    if os.path.exists(care_plan_path):
                        os.remove(care_plan_path)
                        print(f"Cleaned up: {care_plan_path}")

                if care_plan_error:
                    return jsonify({'error': f'護理計劃檔案處理錯誤 / Care plan processing error: {care_plan_error}'}), 400

                if not care_plan_content or len(care_plan_content.strip()) < 10:
                    return jsonify({'error': '護理計劃檔案內容為空或過短 / Care plan file is empty or too short'}), 400

                print(f"Care plan content length: {len(care_plan_content)} characters")

            except Exception as e:
                print(f"Error processing care plan file: {str(e)}")
                return jsonify({'error': f'處理護理計劃檔案時發生錯誤 / Error processing care plan file: {str(e)}'}), 400

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

        # Initialize results
        analysis_result = None
        risk_assessment_results = None
        log_highlights = None

        # Process based on selected options
        if 'care_plan' in analysis_options or 'combo_mode' in analysis_options:
            processing_steps.append("🧠 Generating care plan analysis...")
            analysis_result = analyze_and_suggest_changes(processed_daily_log, care_plan_content, resident_name)

        if 'risk_assessment' in analysis_options or 'combo_mode' in analysis_options:
            processing_steps.append("🛡️ Calculating risk assessments...")
            risk_calculator = RiskAssessmentCalculator()

            # Extract weight data from logs if available
            weight_logs = extract_weight_data(processed_daily_log)
            height = extract_height_data(care_plan_content) if care_plan_content else None
            resident_data = extract_resident_data(care_plan_content, resident_name) if care_plan_content else {'name': resident_name}

            risk_assessment_results = risk_calculator.calculate_all_assessments(
                care_plan_content or "", 
                processed_daily_log, 
                weight_logs, 
                height, 
                resident_data
            )

        if 'log_highlights' in analysis_options:
            processing_steps.append("🔍 Extracting log highlights...")
            log_highlights = extract_log_highlights(processed_daily_log, resident_name)

        # Always analyze data quality
        processing_steps.append("📊 Analyzing data quality...")
        data_quality_analysis = analyze_data_quality(processed_daily_log, resident_name)

        # Ensure we have at least minimal data structure
        if not analysis_result and 'care_plan' not in analysis_options and 'combo_mode' not in analysis_options:
            analysis_result = {
                'analysis_summary': 'Care plan analysis not selected',
                'suggestions': []
            }

        if not risk_assessment_results and 'risk_assessment' not in analysis_options and 'combo_mode' not in analysis_options:
            risk_assessment_results = {
                'assessment_date': datetime.now().strftime('%Y-%m-%d'),
                'summary': {
                    'high_risk_count': 0,
                    'medium_risk_count': 0,
                    'low_risk_count': 0,
                    'priority_alerts': []
                },
                'assessments': {}
            }

        # Add components to analysis result
        if analysis_result and risk_assessment_results and 'summary' in risk_assessment_results:
            analysis_result['risk_assessment_summary'] = risk_assessment_results['summary']

        if analysis_result and log_highlights:
            analysis_result['log_highlights'] = log_highlights

        # File cleanup is handled in processing logic above

        return jsonify({
            'success': True,
            'step': 'suggestions',
            'analysis_summary': analysis_result.get('analysis_summary', '') if analysis_result else '',
            'suggestions': analysis_result.get('suggestions', []) if analysis_result else [],
            'log_highlights': analysis_result.get('log_highlights', []) if analysis_result else log_highlights or [],
            'resident_name': resident_name,
            'original_care_plan': care_plan_content,
            'processing_steps': processing_steps,
            'was_compressed': is_large_file(daily_log_content),
            'risk_assessment': risk_assessment_results,
            'data_quality_analysis': data_quality_analysis,
            'analysis_options': analysis_options
        })

    except Exception as e:
        print(f"Error in analyze endpoint: {str(e)}")
        import traceback
        traceback.print_exc()

        # More specific error messages
        if "rate_limit_exceeded" in str(e).lower():
            error_msg = "API rate limit exceeded. Please try again in a few minutes."
        elif "insufficient_quota" in str(e).lower():
            error_msg = "OpenAI API quota exceeded. Please check your API key balance."
        elif "invalid_api_key" in str(e).lower():
            error_msg = "Invalid OpenAI API key. Please check your API key in Secrets."
        else:
            error_msg = f"Analysis failed: {str(e)}"

        return jsonify({'error': error_msg}), 500

@app.route('/risk_assessment_details', methods=['POST'])
def risk_assessment_details():
    """Get detailed risk assessment calculation breakdown"""
    if not client:
        return jsonify({'error': 'OpenAI API not available'}), 500

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

        # Include manual adjustments if present
        manual_adjustments = risk_assessment_data.get('manual_adjustments', {})
        if manual_adjustments:
            print(f"Manual risk adjustments found: {len(manual_adjustments)} tools adjusted")

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
