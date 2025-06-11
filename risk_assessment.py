"""
Risk Assessment Module for Care Home Management System
Implements automatic risk assessment calculations based on care plan and log data
"""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

class RiskAssessmentCalculator:
    """Main class for calculating various risk assessment scores"""
    
    def __init__(self):
        self.assessment_tools = {
            'falls_screening': self.calculate_falls_screening,
            'pressure_ulcer_ppu': self.calculate_ppu,
            'must_nutrition': self.calculate_must,
            'waterlow': self.calculate_waterlow,
            'abbey_pain': self.calculate_abbey_pain,
            'cornell_depression': self.calculate_cornell_depression,
            'moving_handling': self.calculate_moving_handling,
            'peep': self.calculate_peep
        }
    
    def calculate_all_assessments(self, care_plan_text: str, log_entries: str, 
                                weight_logs: List[float] = None, height: float = None,
                                resident_data: Dict = None) -> Dict[str, Any]:
        """Calculate all risk assessments and return comprehensive results"""
        
        results = {
            'assessment_date': datetime.now().strftime('%Y-%m-%d'),
            'assessments': {},
            'summary': {
                'high_risk_count': 0,
                'medium_risk_count': 0,
                'low_risk_count': 0,
                'priority_alerts': []
            }
        }
        
        # Calculate each assessment
        for tool_name, calculator in self.assessment_tools.items():
            try:
                if tool_name == 'must_nutrition':
                    assessment = calculator(care_plan_text, log_entries, weight_logs, height)
                else:
                    assessment = calculator(care_plan_text, log_entries, resident_data)
                
                results['assessments'][tool_name] = assessment
                
                # Update summary
                risk_level = assessment['risk_level'].lower()
                if 'high' in risk_level or 'severe' in risk_level:
                    results['summary']['high_risk_count'] += 1
                    results['summary']['priority_alerts'].append({
                        'tool': tool_name,
                        'score': assessment['score'],
                        'risk_level': assessment['risk_level'],
                        'alert': f"HIGH RISK: {assessment['tool_name']} score {assessment['score']}"
                    })
                elif 'medium' in risk_level or 'moderate' in risk_level:
                    results['summary']['medium_risk_count'] += 1
                else:
                    results['summary']['low_risk_count'] += 1
                    
            except Exception as e:
                results['assessments'][tool_name] = {
                    'error': f"Calculation error: {str(e)}",
                    'score': 0,
                    'risk_level': 'Unable to assess'
                }
        
        return results
    
    def calculate_falls_screening(self, care_plan_text: str, log_entries: str, 
                                resident_data: Dict = None) -> Dict[str, Any]:
        """Calculate Falls Screening (FS) risk score"""
        
        score = 0
        evidence = []
        combined_text = (care_plan_text + " " + log_entries).lower()
        
        # Check falls history
        fall_keywords = ["fall", "fell", "trip", "stumble", "slip", "tumble"]
        if any(keyword in combined_text for keyword in fall_keywords):
            score += 1
            evidence.append("Fall history identified in records")
        
        # Check medication count
        medication_count = self._count_medications(care_plan_text)
        if medication_count >= 4:
            score += 1
            evidence.append(f"{medication_count} medications prescribed (≥4)")
        
        # Check diagnosed conditions
        disease_keywords = ["dementia", "stroke", "parkinson", "alzheimer"]
        for keyword in disease_keywords:
            if keyword in combined_text:
                score += 1
                evidence.append(f"Diagnosed condition: {keyword.title()}")
                break
        
        # Check balance problems
        balance_keywords = ["balance", "unsteady", "dizzy", "vertigo", "unstable", "wobble"]
        if any(keyword in combined_text for keyword in balance_keywords):
            score += 1
            evidence.append("Balance problems identified")
        
        # Check standing difficulty
        mobility_keywords = ["difficulty standing", "cannot stand", "unable to rise", "help standing"]
        if any(keyword in combined_text for keyword in mobility_keywords):
            score += 1
            evidence.append("Standing difficulty identified")
        
        # Determine risk level
        if score >= 3:
            risk_level = "High Risk"
        elif score >= 2:
            risk_level = "Medium Risk"
        else:
            risk_level = "Low Risk"
        
        return {
            'tool_name': 'Falls Screening',
            'score': score,
            'max_score': 6,
            'risk_level': risk_level,
            'evidence': evidence,
            'recommendations': self._get_falls_recommendations(score),
            'next_review_date': (datetime.now() + timedelta(weeks=1)).strftime('%Y-%m-%d')
        }
    
    def calculate_ppu(self, care_plan_text: str, log_entries: str, 
                     resident_data: Dict = None) -> Dict[str, Any]:
        """Calculate Preliminary Pressure Ulcer (PPU) risk score"""
        
        score = 0
        evidence = []
        combined_text = (care_plan_text + " " + log_entries).lower()
        
        # Check mobility
        mobility_keywords = ["wheelchair", "bedbound", "immobile", "hoist", "assistance walking"]
        if any(keyword in combined_text for keyword in mobility_keywords):
            score += 1
            evidence.append("Mobility assistance required")
        
        # Check continence
        continence_keywords = ["incontinent", "wet", "soiled", "catheter", "pad"]
        if any(keyword in combined_text for keyword in continence_keywords):
            score += 1
            evidence.append("Continence issues identified")
        
        # Check nutrition
        nutrition_keywords = ["poor appetite", "not eating", "weight loss", "malnourished", "refusing food"]
        if any(keyword in combined_text for keyword in nutrition_keywords):
            score += 1
            evidence.append("Nutritional concerns identified")
        
        # Determine risk level
        if score >= 1:
            risk_level = "Requires Full Assessment"
            recommendations = ["Conduct full Waterlow pressure ulcer risk assessment", "Inspect skin condition"]
        else:
            risk_level = "Low Risk"
            recommendations = ["Continue routine skin monitoring"]
        
        return {
            'tool_name': 'Preliminary Pressure Ulcer',
            'score': score,
            'max_score': 3,
            'risk_level': risk_level,
            'evidence': evidence,
            'recommendations': recommendations,
            'next_review_date': (datetime.now() + timedelta(weeks=2)).strftime('%Y-%m-%d')
        }
    
    def calculate_must(self, care_plan_text: str, log_entries: str, 
                      weight_logs: List[float] = None, height: float = None) -> Dict[str, Any]:
        """Calculate MUST (Malnutrition Universal Screening Tool) score"""
        
        score = 0
        evidence = []
        combined_text = (care_plan_text + " " + log_entries).lower()
        
        # BMI calculation
        if weight_logs and height and len(weight_logs) > 0:
            latest_weight = weight_logs[-1]
            bmi = latest_weight / (height/100)**2
            if bmi < 18.5:
                score += 2
                evidence.append(f"BMI {bmi:.1f} - Underweight (<18.5)")
            elif 18.5 <= bmi <= 20:
                score += 1
                evidence.append(f"BMI {bmi:.1f} - Below average (18.5-20)")
            else:
                evidence.append(f"BMI {bmi:.1f} - Normal (>20)")
        
        # Weight loss calculation
        if weight_logs and len(weight_logs) >= 2:
            weight_change = (weight_logs[0] - weight_logs[-1]) / weight_logs[0] * 100
            if weight_change > 10:
                score += 2
                evidence.append(f"Weight loss >10% ({weight_change:.1f}%)")
            elif 5 <= weight_change <= 10:
                score += 1
                evidence.append(f"Weight loss 5-10% ({weight_change:.1f}%)")
        
        # Acute illness and fasting
        fasting_keywords = ["nil by mouth", "nbm", "fasting", "no oral intake", "tube feeding only"]
        illness_keywords = ["acute", "unwell", "hospital", "infection", "fever"]
        
        if (any(keyword in combined_text for keyword in fasting_keywords) and 
            any(keyword in combined_text for keyword in illness_keywords)):
            score += 2
            evidence.append("Acutely ill with reduced nutritional intake")
        
        # Determine risk level
        if score >= 2:
            risk_level = "High Risk"
        elif score == 1:
            risk_level = "Medium Risk"
        else:
            risk_level = "Low Risk"
        
        return {
            'tool_name': 'MUST Nutrition Screening',
            'score': score,
            'max_score': 6,
            'risk_level': risk_level,
            'evidence': evidence,
            'recommendations': self._get_must_recommendations(score),
            'next_review_date': (datetime.now() + timedelta(weeks=1)).strftime('%Y-%m-%d')
        }
    
    def calculate_waterlow(self, care_plan_text: str, log_entries: str, 
                          resident_data: Dict = None) -> Dict[str, Any]:
        """Calculate Waterlow pressure ulcer risk assessment"""
        
        score = 0
        evidence = []
        combined_text = (care_plan_text + " " + log_entries).lower()
        
        # Age scoring (if available in resident_data)
        if resident_data and 'age' in resident_data:
            age = resident_data['age']
            if age >= 81:
                score += 5
                evidence.append(f"Age {age} years (5 points)")
            elif age >= 75:
                score += 4
                evidence.append(f"Age {age} years (4 points)")
            elif age >= 65:
                score += 3
                evidence.append(f"Age {age} years (3 points)")
        
        # Gender scoring
        if resident_data and 'gender' in resident_data:
            if resident_data['gender'].lower() == 'female':
                score += 2
                evidence.append("Female gender (2 points)")
            else:
                score += 1
                evidence.append("Male gender (1 point)")
        
        # Skin condition
        skin_keywords = ["bruising", "discoloured", "mottled", "broken skin", "red", "sore"]
        if any(keyword in combined_text for keyword in skin_keywords):
            score += 2
            evidence.append("Skin discoloration/bruising identified")
        
        # Continence
        if "incontinent" in combined_text:
            if "faeces" in combined_text or "bowel" in combined_text:
                score += 3
                evidence.append("Doubly incontinent (3 points)")
            else:
                score += 1
                evidence.append("Urine incontinence (1 point)")
        
        # Mobility
        mobility_keywords = ["bedbound", "chair bound", "immobile"]
        if any(keyword in combined_text for keyword in mobility_keywords):
            score += 4
            evidence.append("Restricted mobility/bedbound")
        elif any(keyword in ["wheelchair", "walking aid", "assistance"] for keyword in combined_text.split()):
            score += 3
            evidence.append("Restricted activity")
        
        # Nutrition
        nutrition_keywords = ["poor appetite", "weight loss", "not eating", "malnourished"]
        if any(keyword in combined_text for keyword in nutrition_keywords):
            score += 1
            evidence.append("Poor nutrition/appetite")
        
        # Determine risk level
        if score >= 20:
            risk_level = "Very High Risk"
        elif score >= 15:
            risk_level = "High Risk"
        elif score >= 10:
            risk_level = "Medium Risk"
        else:
            risk_level = "Low Risk"
        
        return {
            'tool_name': 'Waterlow Pressure Ulcer Assessment',
            'score': score,
            'max_score': 'Variable',
            'risk_level': risk_level,
            'evidence': evidence,
            'recommendations': self._get_waterlow_recommendations(score),
            'next_review_date': (datetime.now() + timedelta(weeks=4)).strftime('%Y-%m-%d')
        }
    
    def calculate_abbey_pain(self, care_plan_text: str, log_entries: str, 
                           resident_data: Dict = None) -> Dict[str, Any]:
        """Calculate Abbey Pain Scale score"""
        
        score = 0
        evidence = []
        combined_text = (care_plan_text + " " + log_entries).lower()
        
        # Vocalisation
        vocal_keywords = ["crying", "moaning", "groaning", "shouting", "calling out"]
        if any(keyword in combined_text for keyword in vocal_keywords):
            score += 2  # Assuming moderate level
            evidence.append("Vocalisation of pain identified")
        
        # Facial expression
        facial_keywords = ["grimacing", "frowning", "tense", "distressed", "wincing"]
        if any(keyword in combined_text for keyword in facial_keywords):
            score += 2
            evidence.append("Facial expressions of pain")
        
        # Body language changes
        body_keywords = ["restless", "fidgeting", "guarding", "withdrawn", "agitated"]
        if any(keyword in combined_text for keyword in body_keywords):
            score += 2
            evidence.append("Body language changes indicating pain")
        
        # Behavioural changes
        behaviour_keywords = ["confused", "refusing", "aggressive", "pattern change"]
        if any(keyword in combined_text for keyword in behaviour_keywords):
            score += 2
            evidence.append("Behavioural changes noted")
        
        # Pain medication or pain-related terms
        pain_keywords = ["pain", "discomfort", "sore", "ache", "hurts", "paracetamol", "analgesic"]
        if any(keyword in combined_text for keyword in pain_keywords):
            score += 1
            evidence.append("Pain or discomfort documented")
        
        # Determine risk level
        if score >= 14:
            risk_level = "Severe Pain"
        elif score >= 8:
            risk_level = "Moderate Pain"
        elif score >= 3:
            risk_level = "Mild Pain"
        else:
            risk_level = "No Pain to Mild Pain"
        
        return {
            'tool_name': 'Abbey Pain Scale',
            'score': score,
            'max_score': 18,
            'risk_level': risk_level,
            'evidence': evidence,
            'recommendations': self._get_pain_recommendations(score),
            'next_review_date': (datetime.now() + timedelta(weeks=4)).strftime('%Y-%m-%d')
        }
    
    def calculate_cornell_depression(self, care_plan_text: str, log_entries: str, 
                                   resident_data: Dict = None) -> Dict[str, Any]:
        """Calculate Cornell Depression Scale for Dementia"""
        
        score = 0
        evidence = []
        combined_text = (care_plan_text + " " + log_entries).lower()
        
        # Mood-related signs
        mood_keywords = ["anxious", "sad", "tearful", "irritable", "worried"]
        mood_count = sum(1 for keyword in mood_keywords if keyword in combined_text)
        if mood_count > 0:
            score += min(mood_count * 2, 8)  # Max 8 points for mood
            evidence.append(f"Mood-related symptoms identified ({mood_count} indicators)")
        
        # Behavioural disturbance
        behaviour_keywords = ["agitated", "slow", "withdrawn", "lost interest"]
        behaviour_count = sum(1 for keyword in behaviour_keywords if keyword in combined_text)
        if behaviour_count > 0:
            score += min(behaviour_count * 2, 8)  # Max 8 points
            evidence.append(f"Behavioural disturbances noted ({behaviour_count} indicators)")
        
        # Physical signs
        physical_keywords = ["appetite loss", "weight loss", "tired", "fatigue", "no energy"]
        physical_count = sum(1 for keyword in physical_keywords if keyword in combined_text)
        if physical_count > 0:
            score += min(physical_count * 2, 6)  # Max 6 points
            evidence.append(f"Physical symptoms of depression ({physical_count} indicators)")
        
        # Sleep disturbances
        sleep_keywords = ["sleep", "insomnia", "waking", "restless night"]
        if any(keyword in combined_text for keyword in sleep_keywords):
            score += 4
            evidence.append("Sleep disturbances identified")
        
        # Determine risk level
        if score >= 18:
            risk_level = "Definite Depression"
        elif score >= 10:
            risk_level = "Probable Depression"
        else:
            risk_level = "Low Risk"
        
        return {
            'tool_name': 'Cornell Depression Scale',
            'score': score,
            'max_score': 38,
            'risk_level': risk_level,
            'evidence': evidence,
            'recommendations': self._get_depression_recommendations(score),
            'next_review_date': (datetime.now() + timedelta(weeks=12)).strftime('%Y-%m-%d')
        }
    
    def calculate_moving_handling(self, care_plan_text: str, log_entries: str, 
                                resident_data: Dict = None) -> Dict[str, Any]:
        """Calculate Moving and Handling Assessment"""
        
        evidence = []
        combined_text = (care_plan_text + " " + log_entries).lower()
        
        # Assess different activities
        activities = {
            'standing': 0,
            'walking': 0,
            'transferring': 0,
            'personal_care': 0
        }
        
        # Standing ability
        if any(keyword in combined_text for keyword in ["cannot stand", "unable to stand"]):
            activities['standing'] = 3
            evidence.append("Unable to stand independently")
        elif "help standing" in combined_text or "assistance standing" in combined_text:
            activities['standing'] = 2
            evidence.append("Requires assistance to stand")
        
        # Walking ability
        if "wheelchair" in combined_text:
            activities['walking'] = 3
            evidence.append("Wheelchair dependent")
        elif any(keyword in combined_text for keyword in ["walking aid", "zimmer", "walker"]):
            activities['walking'] = 2
            evidence.append("Uses walking aids")
        
        # Overall risk assessment
        max_score = max(activities.values())
        if max_score >= 3:
            risk_level = "High Risk - 2 Staff Required"
        elif max_score >= 2:
            risk_level = "Medium Risk - 1 Staff Required"
        else:
            risk_level = "Low Risk - Independent"
        
        return {
            'tool_name': 'Moving and Handling Assessment',
            'score': max_score,
            'max_score': 5,
            'risk_level': risk_level,
            'evidence': evidence,
            'recommendations': self._get_handling_recommendations(max_score),
            'next_review_date': (datetime.now() + timedelta(weeks=24)).strftime('%Y-%m-%d')
        }
    
    def calculate_peep(self, care_plan_text: str, log_entries: str, 
                      resident_data: Dict = None) -> Dict[str, Any]:
        """Calculate Personal Emergency Evacuation Plan (PEEP) risk"""
        
        score = 1  # Default low risk
        evidence = []
        combined_text = (care_plan_text + " " + log_entries).lower()
        
        # Check evacuation ability
        if any(keyword in combined_text for keyword in ["wheelchair", "bedbound", "immobile"]):
            score = 4
            evidence.append("Cannot self-evacuate - requires equipment and multiple staff")
        elif any(keyword in combined_text for keyword in ["confusion", "dementia", "cognitive"]):
            score = 3
            evidence.append("May require assistance and guidance to evacuate")
        elif any(keyword in combined_text for keyword in ["walking aid", "slow mobility"]):
            score = 2
            evidence.append("May need verbal prompting or some assistance")
        else:
            evidence.append("Appears able to evacuate independently")
        
        # Determine risk level
        risk_levels = {
            4: "Severe Risk",
            3: "High Risk", 
            2: "Medium Risk",
            1: "Low Risk"
        }
        
        return {
            'tool_name': 'Personal Emergency Evacuation Plan',
            'score': score,
            'max_score': 4,
            'risk_level': risk_levels[score],
            'evidence': evidence,
            'recommendations': self._get_peep_recommendations(score),
            'next_review_date': (datetime.now() + timedelta(weeks=24)).strftime('%Y-%m-%d')
        }
    
    def _count_medications(self, text: str) -> int:
        """Count number of medications mentioned in text"""
        medication_indicators = [
            "tablet", "mg", "medication", "drug", "pill", "capsule",
            "paracetamol", "aspirin", "warfarin", "metformin", "insulin"
        ]
        
        # Simple count based on medication-related terms
        count = 0
        text_lower = text.lower()
        for indicator in medication_indicators:
            if indicator in text_lower:
                count += text_lower.count(indicator)
        
        # Cap at reasonable number and adjust for common duplicates
        return min(count // 2, 10)  # Divide by 2 to avoid over-counting
    
    def _get_falls_recommendations(self, score: int) -> List[str]:
        """Get recommendations based on falls screening score"""
        if score >= 3:
            return [
                "Implement comprehensive fall prevention measures",
                "Consider bed/chair alarms if appropriate",
                "Review medication for fall risk side effects",
                "Increase supervision during mobility",
                "Physiotherapy assessment for balance and strength"
            ]
        elif score >= 2:
            return [
                "Implement standard fall prevention measures",
                "Review medication regime",
                "Ensure clear walkways and good lighting",
                "Monitor during high-risk activities"
            ]
        else:
            return [
                "Continue routine fall prevention measures",
                "Maintain awareness of fall risk factors"
            ]
    
    def _get_must_recommendations(self, score: int) -> List[str]:
        """Get recommendations based on MUST score"""
        if score >= 2:
            return [
                "Refer to dietitian/nutritionist",
                "Implement nutrition care plan",
                "Monitor weight weekly",
                "Consider nutritional supplements",
                "Document food and fluid intake"
            ]
        elif score == 1:
            return [
                "Monitor weight and intake",
                "Review dietary preferences",
                "Consider nutritional supplements"
            ]
        else:
            return [
                "Continue routine nutrition monitoring",
                "Maintain balanced diet"
            ]
    
    def _get_waterlow_recommendations(self, score: int) -> List[str]:
        """Get recommendations based on Waterlow score"""
        if score >= 20:
            return [
                "Implement maximum pressure relief measures",
                "2-hourly repositioning regime",
                "Pressure-relieving mattress and cushions",
                "Daily skin inspection",
                "Involve tissue viability nurse"
            ]
        elif score >= 15:
            return [
                "Implement pressure relief measures",
                "4-hourly repositioning",
                "Pressure-relieving equipment",
                "Regular skin inspection"
            ]
        elif score >= 10:
            return [
                "Regular repositioning",
                "Monitor skin condition",
                "Consider pressure-relieving aids"
            ]
        else:
            return [
                "Continue routine skin care",
                "Monitor for changes in condition"
            ]
    
    def _get_pain_recommendations(self, score: int) -> List[str]:
        """Get recommendations based on Abbey Pain Scale score"""
        if score >= 14:
            return [
                "Urgent medical review for pain management",
                "Consider strong analgesics",
                "Regular pain assessment",
                "Non-pharmacological comfort measures"
            ]
        elif score >= 8:
            return [
                "Medical review for pain management",
                "Regular analgesics as prescribed",
                "Monitor effectiveness of pain relief"
            ]
        elif score >= 3:
            return [
                "Monitor for pain signs",
                "PRN analgesics as needed",
                "Comfort measures"
            ]
        else:
            return [
                "Continue routine comfort care",
                "Monitor for changes"
            ]
    
    def _get_depression_recommendations(self, score: int) -> List[str]:
        """Get recommendations based on Cornell Depression Scale score"""
        if score >= 18:
            return [
                "Urgent psychiatric/GP review",
                "Consider antidepressant medication",
                "Implement depression care plan",
                "Increase social interaction and activities"
            ]
        elif score >= 10:
            return [
                "Medical review for possible depression",
                "Monitor mood and behaviour",
                "Encourage social activities",
                "Consider counselling/therapy"
            ]
        else:
            return [
                "Continue routine emotional support",
                "Monitor for mood changes"
            ]
    
    def _get_handling_recommendations(self, score: int) -> List[str]:
        """Get recommendations based on Moving and Handling score"""
        if score >= 3:
            return [
                "Two staff required for all transfers",
                "Use appropriate lifting equipment",
                "Regular manual handling training for staff",
                "Risk assessment before each move"
            ]
        elif score >= 2:
            return [
                "One staff member assistance required",
                "Use walking aids as appropriate",
                "Monitor during mobility"
            ]
        else:
            return [
                "Encourage independence",
                "Monitor mobility levels"
            ]
    
    def _get_peep_recommendations(self, score: int) -> List[str]:
        """Get recommendations based on PEEP score"""
        if score == 4:
            return [
                "Requires evacuation chair and two staff",
                "Practice evacuation procedures regularly",
                "Ensure staff know evacuation route",
                "Consider refuge area if needed"
            ]
        elif score == 3:
            return [
                "Requires staff assistance to evacuate",
                "Verbal prompting and guidance needed",
                "Practice evacuation procedures"
            ]
        elif score == 2:
            return [
                "May need verbal prompting",
                "Monitor during evacuation drills"
            ]
        else:
            return [
                "Can evacuate independently",
                "Include in general evacuation procedures"
            ]

def format_risk_assessment_for_care_plan(assessment_results: Dict[str, Any]) -> str:
    """Format risk assessment results for inclusion in care plan"""
    
    if not assessment_results or 'assessments' not in assessment_results:
        return "Risk Assessment: Unable to calculate at this time."
    
    output = ["# 🛡️ RISK ASSESSMENT SUMMARY"]
    output.append(f"**Assessment Date:** {assessment_results['assessment_date']}")
    
    # Check for manual adjustments
    manual_adjustments = assessment_results.get('manual_adjustments', {})
    if manual_adjustments:
        output.append("")
        output.append("## ✏️ MANAGER ADJUSTMENTS APPLIED")
        output.append("*The following scores have been manually reviewed and adjusted by care manager based on actual resident observations:*")
        output.append("")
        for tool_name, adjustment in manual_adjustments.items():
            tool_display_name = assessment_results['assessments'][tool_name]['tool_name']
            output.append(f"- **{tool_display_name}:** Score adjusted from {adjustment['original_score']} to {adjustment['adjusted_score']}")
            if adjustment.get('reason'):
                output.append(f"  - *Manager's reasoning:* {adjustment['reason']}")
        output.append("")
    
    output.append("")
    
    # Summary overview
    summary = assessment_results['summary']
    output.append("## 📊 Risk Overview")
    output.append(f"- 🔴 High Risk Areas: {summary['high_risk_count']}")
    output.append(f"- 🟡 Medium Risk Areas: {summary['medium_risk_count']}")  
    output.append(f"- 🟢 Low Risk Areas: {summary['low_risk_count']}")
    output.append("")
    
    # Priority alerts
    if summary['priority_alerts']:
        output.append("## 🚨 PRIORITY ALERTS")
        for alert in summary['priority_alerts']:
            output.append(f"- {alert['alert']}")
        output.append("")
    
    # Detailed assessments
    output.append("## 📋 Detailed Risk Assessments")
    
    for tool_name, assessment in assessment_results['assessments'].items():
        if 'error' in assessment:
            continue
            
        output.append(f"### {assessment['tool_name']}")
        output.append(f"**Score:** {assessment['score']}/{assessment['max_score']} - **{assessment['risk_level']}**")
        
        if assessment['evidence']:
            output.append("**Evidence:**")
            for evidence in assessment['evidence']:
                output.append(f"- {evidence}")
        
        if assessment['recommendations']:
            output.append("**Recommendations:**")
            for rec in assessment['recommendations']:
                output.append(f"- {rec}")
        
        output.append(f"**Next Review:** {assessment['next_review_date']}")
        output.append("")
    
    return "\n".join(output) 