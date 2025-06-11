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
        """Create standardized assessment forms with AI filling available data"""
        
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
        
        # Create standardized forms for each assessment tool
        for tool_name, calculator in self.assessment_tools.items():
            try:
                # Create standardized form structure
                form = self._create_standard_form(tool_name)
                
                # Fill form with AI-detected data
                if tool_name == 'must_nutrition':
                    filled_form = self._fill_form_with_ai_data(form, care_plan_text, log_entries, weight_logs, height, resident_data)
                else:
                    filled_form = self._fill_form_with_ai_data(form, care_plan_text, log_entries, None, None, resident_data)
                
                # Calculate score from filled form
                calculated_score = self._calculate_score_from_form(tool_name, filled_form)
                
                # Determine risk level
                risk_level = self._determine_risk_level(tool_name, calculated_score['total_score'])
                
                results['assessments'][tool_name] = {
                    'tool_name': filled_form['tool_name'],
                    'form_items': filled_form['items'],
                    'score': calculated_score['total_score'],
                    'max_score': filled_form['max_score'],
                    'risk_level': risk_level,
                    'ai_filled_items': calculated_score['ai_filled_count'],
                    'manager_required_items': calculated_score['missing_count'],
                    'calculation_formula': filled_form['formula'],
                    'next_review_date': (datetime.now() + timedelta(weeks=self._get_review_interval(tool_name))).strftime('%Y-%m-%d')
                }
                
                # Update summary
                if 'high' in risk_level.lower() or 'severe' in risk_level.lower():
                    results['summary']['high_risk_count'] += 1
                    if calculated_score['total_score'] > 0:  # Only alert if there's actual data
                        results['summary']['priority_alerts'].append({
                            'tool': tool_name,
                            'score': calculated_score['total_score'],
                            'risk_level': risk_level,
                            'alert': f"HIGH RISK: {filled_form['tool_name']} score {calculated_score['total_score']}"
                        })
                elif 'medium' in risk_level.lower() or 'moderate' in risk_level.lower():
                    results['summary']['medium_risk_count'] += 1
                else:
                    results['summary']['low_risk_count'] += 1
                    
            except Exception as e:
                results['assessments'][tool_name] = {
                    'error': f"Form creation error: {str(e)}",
                    'score': 0,
                    'risk_level': 'Unable to assess'
                }
        
        return results
    
    def calculate_falls_screening(self, care_plan_text: str, log_entries: str, 
                                resident_data: Dict = None) -> Dict[str, Any]:
        """Calculate Falls Screening (FS) risk score following exact formula"""
        
        score = 0
        evidence = []
        missing_data = []
        combined_text = (care_plan_text + " " + log_entries).lower()
        
        # 1. Falls history in past year (0-1 points)
        fall_keywords = ["fall", "fell", "trip", "stumble", "slip", "tumble"]
        falls_found = [kw for kw in fall_keywords if kw in combined_text]
        if falls_found:
            score += 1
            evidence.append(f"Fall history: Found keywords - {', '.join(falls_found)}")
        else:
            missing_data.append("Falls history in past year - Manager must verify if resident has fallen in last 12 months")
        
        # 2. Daily medications ≥4 (0-1 points)
        medication_count = self._count_medications(care_plan_text)
        if medication_count >= 4:
            score += 1
            evidence.append(f"Medications: {medication_count} prescribed (≥4 threshold met)")
        elif medication_count > 0:
            evidence.append(f"Medications: Only {medication_count} identified (<4)")
        else:
            missing_data.append("Complete medication list - Manager must provide current medication count")
        
        # 3. Diagnosed conditions: Dementia/Stroke/Parkinson's (0-1 points)
        disease_keywords = ["dementia", "stroke", "parkinson", "alzheimer"]
        diseases_found = [kw for kw in disease_keywords if kw in combined_text]
        if diseases_found:
            score += 1
            evidence.append(f"Diagnosed condition: {', '.join(diseases_found).title()}")
        else:
            missing_data.append("Medical diagnosis confirmation - Manager must verify if resident has Dementia, Stroke, or Parkinson's")
        
        # 4. Balance problems (0-1 points)
        balance_keywords = ["balance", "unsteady", "dizzy", "vertigo", "unstable", "wobble"]
        balance_found = [kw for kw in balance_keywords if kw in combined_text]
        if balance_found:
            score += 1
            evidence.append(f"Balance problems: {', '.join(balance_found)}")
        else:
            missing_data.append("Balance assessment - Manager must confirm if resident has balance issues")
        
        # 5. Chair rise test (0-1 points)
        mobility_keywords = ["difficulty standing", "cannot stand", "unable to rise", "help standing"]
        mobility_found = [kw for kw in mobility_keywords if kw in combined_text]
        if mobility_found:
            score += 1
            evidence.append(f"Standing difficulty: {', '.join(mobility_found)}")
        else:
            missing_data.append("Chair rise test - Manager must perform test: Can resident rise from knee-height chair without assistance?")
        
        # 6. Postural hypotension (optional, 0-1 points)
        bp_keywords = ["blood pressure", "hypotension", "bp drop", "dizzy standing"]
        bp_found = [kw for kw in bp_keywords if kw in combined_text]
        if bp_found:
            # Would need actual BP measurements to score this properly
            missing_data.append("Postural hypotension test - Manager must measure BP lying and standing (>20mmHg systolic or >10mmHg diastolic drop)")
        else:
            missing_data.append("Postural hypotension assessment - Manager must conduct blood pressure measurements")
        
        # Determine risk level based on actual formula
        if score >= 3:
            risk_level = "High Risk"
        elif score == 2:
            risk_level = "Medium Risk"
        else:
            risk_level = "Low Risk"
        
        return {
            'tool_name': 'Falls Screening',
            'score': score,
            'max_score': 6,
            'risk_level': risk_level,
            'evidence': evidence,
            'missing_data': missing_data,
            'recommendations': self._get_falls_recommendations(score),
            'next_review_date': (datetime.now() + timedelta(weeks=1)).strftime('%Y-%m-%d'),
            'calculation_note': f"Score calculated from available evidence only. {len(missing_data)} items require manager verification for complete assessment."
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
        """Calculate MUST (Malnutrition Universal Screening Tool) score following exact formula"""
        
        score = 0
        evidence = []
        missing_data = []
        combined_text = (care_plan_text + " " + log_entries).lower()
        
        # 1. BMI calculation (0-2 points)
        if weight_logs and height and len(weight_logs) > 0:
            latest_weight = weight_logs[-1]
            bmi = latest_weight / (height/100)**2
            if bmi < 18.5:
                score += 2
                evidence.append(f"BMI: {bmi:.1f} (<18.5) = 2 points")
            elif 18.5 <= bmi <= 20:
                score += 1
                evidence.append(f"BMI: {bmi:.1f} (18.5-20) = 1 point")
            else:
                evidence.append(f"BMI: {bmi:.1f} (>20) = 0 points")
        else:
            missing_data.append("BMI calculation - Manager must provide current weight (kg) and height (cm)")
        
        # 2. Unplanned weight loss in 3-6 months (0-2 points)
        if weight_logs and len(weight_logs) >= 2:
            weight_change = (weight_logs[0] - weight_logs[-1]) / weight_logs[0] * 100
            if weight_change > 10:
                score += 2
                evidence.append(f"Weight loss: {weight_change:.1f}% (>10%) = 2 points")
            elif 5 <= weight_change <= 10:
                score += 1
                evidence.append(f"Weight loss: {weight_change:.1f}% (5-10%) = 1 point")
            else:
                evidence.append(f"Weight loss: {weight_change:.1f}% (<5%) = 0 points")
        else:
            missing_data.append("Weight loss calculation - Manager must provide weight records from 3-6 months ago")
        
        # 3. Acute illness and no nutritional intake for 5+ days (0 or 2 points)
        fasting_keywords = ["nil by mouth", "nbm", "fasting", "no oral intake"]
        illness_keywords = ["acute", "unwell", "hospital", "infection", "fever"]
        
        fasting_found = any(keyword in combined_text for keyword in fasting_keywords)
        illness_found = any(keyword in combined_text for keyword in illness_keywords)
        
        if fasting_found and illness_found:
            score += 2
            evidence.append("Acute illness with no nutritional intake = 2 points")
        elif fasting_found or illness_found:
            missing_data.append("Acute illness assessment - Manager must confirm if resident is acutely ill AND has had no nutritional intake for 5+ days")
        else:
            missing_data.append("Acute illness and fasting status - Manager must assess current illness status and nutritional intake")
        
        # Determine risk level based on exact MUST criteria
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
            'missing_data': missing_data,
            'recommendations': self._get_must_recommendations(score),
            'next_review_date': (datetime.now() + timedelta(weeks=1)).strftime('%Y-%m-%d'),
            'calculation_note': f"MUST score based on available data only. {len(missing_data)} components require manager input for complete assessment."
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
    
    def _create_standard_form(self, tool_name: str) -> Dict[str, Any]:
        """Create standardized form for each assessment tool"""
        
        forms = {
            'falls_screening': {
                'tool_name': 'Falls Screening',
                'max_score': 6,
                'formula': 'Falls History(0-1) + Medications≥4(0-1) + Diagnosis(0-1) + Balance Issues(0-1) + Chair Rise(0-1) + Postural Hypotension(0-1)',
                'items': [
                    {'id': 'falls_history', 'name': 'Falls history in past year', 'score_range': '0-1', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'medications', 'name': 'Daily medications ≥4', 'score_range': '0-1', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'diagnosis', 'name': 'Dementia/Stroke/Parkinson\'s diagnosis', 'score_range': '0-1', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'balance', 'name': 'Balance problems', 'score_range': '0-1', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'chair_rise', 'name': 'Chair rise test (unable to rise)', 'score_range': '0-1', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'postural_bp', 'name': 'Postural hypotension (optional)', 'score_range': '0-1', 'ai_value': None, 'manager_input_required': True}
                ]
            },
            'must_nutrition': {
                'tool_name': 'MUST Nutrition Screening',
                'max_score': 6,
                'formula': 'BMI Score(0-2) + Weight Loss(0-2) + Acute Illness Fasting(0-2)',
                'items': [
                    {'id': 'bmi', 'name': 'BMI calculation', 'score_range': '0-2', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'weight_loss', 'name': 'Unplanned weight loss 3-6 months', 'score_range': '0-2', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'acute_illness', 'name': 'Acute illness with no intake 5+ days', 'score_range': '0-2', 'ai_value': None, 'manager_input_required': True}
                ]
            },
            'waterlow': {
                'tool_name': 'Waterlow Pressure Ulcer Assessment',
                'max_score': 'Variable',
                'formula': 'Age + Gender + BMI + Skin + Mobility + Nutrition + Continence + Special Conditions',
                'items': [
                    {'id': 'age', 'name': 'Age scoring', 'score_range': '1-5', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'gender', 'name': 'Gender', 'score_range': '1-2', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'skin_condition', 'name': 'Skin type/condition', 'score_range': '0-2', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'mobility', 'name': 'Mobility level', 'score_range': '0-4', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'continence', 'name': 'Continence status', 'score_range': '0-3', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'nutrition', 'name': 'Nutrition status', 'score_range': '0-1', 'ai_value': None, 'manager_input_required': True}
                ]
            },
            'abbey_pain': {
                'tool_name': 'Abbey Pain Scale',
                'max_score': 18,
                'formula': 'Vocalisation(0-3) + Facial(0-3) + Body Language(0-3) + Behavioural(0-3) + Physiological(0-3) + Physical(0-3)',
                'items': [
                    {'id': 'vocalisation', 'name': 'Vocalisation (crying, moaning, groaning)', 'score_range': '0-3', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'facial', 'name': 'Facial expression (grimacing, frowning)', 'score_range': '0-3', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'body_language', 'name': 'Body language changes (restless, guarding)', 'score_range': '0-3', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'behavioural', 'name': 'Behavioural changes (confusion, refusal)', 'score_range': '0-3', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'physiological', 'name': 'Physiological changes (BP, pulse, temp)', 'score_range': '0-3', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'physical', 'name': 'Physical changes (skin tears, pressure areas)', 'score_range': '0-3', 'ai_value': None, 'manager_input_required': True}
                ]
            },
            'cornell_depression': {
                'tool_name': 'Cornell Depression Scale',
                'max_score': 38,
                'formula': 'Mood Signs(0-8) + Behavioural(0-8) + Physical(0-6) + Cyclic Functions(0-8) + Ideational(0-8)',
                'items': [
                    {'id': 'mood_signs', 'name': 'Mood-related signs (anxiety, sadness)', 'score_range': '0-8', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'behavioural_dist', 'name': 'Behavioural disturbance (agitation, retardation)', 'score_range': '0-8', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'physical_signs', 'name': 'Physical signs (appetite, weight, energy)', 'score_range': '0-6', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'cyclic_functions', 'name': 'Sleep and cyclic functions', 'score_range': '0-8', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'ideational', 'name': 'Ideational disturbance (suicide, pessimism)', 'score_range': '0-8', 'ai_value': None, 'manager_input_required': True}
                ]
            },
            'moving_handling': {
                'tool_name': 'Moving and Handling Assessment',
                'max_score': 5,
                'formula': 'Maximum risk level across all activities (Standing, Walking, Transferring, Personal Care)',
                'items': [
                    {'id': 'standing', 'name': 'Standing ability', 'score_range': '0-5', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'walking', 'name': 'Walking ability', 'score_range': '0-5', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'transferring', 'name': 'Transferring ability', 'score_range': '0-5', 'ai_value': None, 'manager_input_required': True},
                    {'id': 'personal_care', 'name': 'Personal care activities', 'score_range': '0-5', 'ai_value': None, 'manager_input_required': True}
                ]
            },
            'peep': {
                'tool_name': 'Personal Emergency Evacuation Plan',
                'max_score': 4,
                'formula': 'Single risk level assessment (1=Low, 2=Medium, 3=High, 4=Severe)',
                'items': [
                    {'id': 'evacuation_ability', 'name': 'Evacuation ability assessment', 'score_range': '1-4', 'ai_value': None, 'manager_input_required': True}
                ]
            }
        }
        
        return forms.get(tool_name, {})
    
    def _fill_form_with_ai_data(self, form: Dict, care_plan_text: str, log_entries: str, 
                               weight_logs: List[float] = None, height: float = None,
                               resident_data: Dict = None) -> Dict[str, Any]:
        """Fill standardized form with AI-detected data where possible"""
        
        combined_text = (care_plan_text + " " + log_entries).lower()
        
        # Process each form item
        for item in form['items']:
            ai_result = self._ai_detect_item_value(item['id'], combined_text, weight_logs, height, resident_data)
            item['ai_value'] = ai_result['value']
            item['ai_confidence'] = ai_result['confidence']
            item['ai_evidence'] = ai_result['evidence']
            item['manager_input_required'] = ai_result['value'] is None
        
        return form
    
    def _ai_detect_item_value(self, item_id: str, combined_text: str, weight_logs=None, height=None, resident_data=None) -> Dict:
        """AI detection for specific form items"""
        
        detection_rules = {
            'falls_history': {
                'keywords': ['fall', 'fell', 'trip', 'stumble', 'slip', 'tumble'],
                'score_if_found': 1,
                'score_if_not_found': None  # Require manager input
            },
            'medications': {
                'keywords': ['tablet', 'mg', 'medication', 'drug', 'pill', 'capsule'],
                'count_based': True,
                'threshold': 4,
                'score_if_above': 1,
                'score_if_below': None  # Require manager verification
            },
            'diagnosis': {
                'keywords': ['dementia', 'stroke', 'parkinson', 'alzheimer'],
                'score_if_found': 1,
                'score_if_not_found': None
            },
            'balance': {
                'keywords': ['balance', 'unsteady', 'dizzy', 'vertigo', 'unstable', 'wobble'],
                'score_if_found': 1,
                'score_if_not_found': None
            },
            'chair_rise': {
                'keywords': ['difficulty standing', 'cannot stand', 'unable to rise', 'help standing'],
                'score_if_found': 1,
                'score_if_not_found': None
            },
            'bmi': {
                'calculation': True,
                'requires_weight_height': True
            },
            'vocalisation': {
                'keywords': ['crying', 'moaning', 'groaning', 'shouting', 'calling out'],
                'score_scale': [0, 1, 2, 3],  # Absent, Mild, Moderate, Severe
                'default': None
            }
        }
        
        rule = detection_rules.get(item_id, {})
        
        if not rule:
            return {'value': None, 'confidence': 'low', 'evidence': 'No detection rule defined'}
        
        # Handle BMI calculation
        if rule.get('calculation') and rule.get('requires_weight_height'):
            if weight_logs and height and len(weight_logs) > 0:
                latest_weight = weight_logs[-1]
                bmi = latest_weight / (height/100)**2
                if bmi < 18.5:
                    return {'value': 2, 'confidence': 'high', 'evidence': f'BMI calculated as {bmi:.1f} from weight {latest_weight}kg and height {height}cm'}
                elif 18.5 <= bmi <= 20:
                    return {'value': 1, 'confidence': 'high', 'evidence': f'BMI calculated as {bmi:.1f}'}
                else:
                    return {'value': 0, 'confidence': 'high', 'evidence': f'BMI calculated as {bmi:.1f}'}
            return {'value': None, 'confidence': 'low', 'evidence': 'Missing weight or height data for BMI calculation'}
        
        # Handle keyword-based detection
        if 'keywords' in rule:
            keywords_found = [kw for kw in rule['keywords'] if kw in combined_text]
            
            if rule.get('count_based'):
                count = sum(combined_text.count(kw) for kw in rule['keywords'])
                if count >= rule.get('threshold', 1):
                    return {
                        'value': rule.get('score_if_above'),
                        'confidence': 'medium',
                        'evidence': f'Found {count} medication references: {keywords_found}'
                    }
                else:
                    return {
                        'value': rule.get('score_if_below'),
                        'confidence': 'low',
                        'evidence': f'Only found {count} medication references (threshold: {rule.get("threshold", 1)})'
                    }
            
            if keywords_found:
                return {
                    'value': rule.get('score_if_found'),
                    'confidence': 'medium',
                    'evidence': f'Keywords found: {", ".join(keywords_found)}'
                }
            else:
                return {
                    'value': rule.get('score_if_not_found'),
                    'confidence': 'low',
                    'evidence': 'No relevant keywords found in care plan/logs'
                }
        
        return {'value': None, 'confidence': 'low', 'evidence': 'No detection method available'}
    
    def _calculate_score_from_form(self, tool_name: str, form: Dict) -> Dict[str, int]:
        """Calculate total score from filled form"""
        
        total_score = 0
        ai_filled_count = 0
        missing_count = 0
        
        for item in form['items']:
            if item['ai_value'] is not None:
                total_score += item['ai_value']
                ai_filled_count += 1
            else:
                missing_count += 1
        
        return {
            'total_score': total_score,
            'ai_filled_count': ai_filled_count,
            'missing_count': missing_count
        }
    
    def _determine_risk_level(self, tool_name: str, score: int) -> str:
        """Determine risk level based on tool and score"""
        
        risk_levels = {
            'falls_screening': {
                0: 'Low Risk',
                1: 'Low Risk', 
                2: 'Medium Risk',
                3: 'High Risk',
                4: 'High Risk',
                5: 'High Risk',
                6: 'High Risk'
            },
            'must_nutrition': {
                0: 'Low Risk',
                1: 'Medium Risk',
                2: 'High Risk',
                3: 'High Risk',
                4: 'High Risk',
                5: 'High Risk',
                6: 'High Risk'
            },
            'abbey_pain': {
                0: 'No Pain',
                1: 'No Pain', 
                2: 'No Pain',
                3: 'Mild Pain',
                4: 'Mild Pain',
                5: 'Mild Pain',
                6: 'Mild Pain',
                7: 'Mild Pain',
                8: 'Moderate Pain',
                9: 'Moderate Pain',
                10: 'Moderate Pain',
                11: 'Moderate Pain',
                12: 'Moderate Pain',
                13: 'Moderate Pain',
                14: 'Severe Pain',
                15: 'Severe Pain',
                16: 'Severe Pain',
                17: 'Severe Pain',
                18: 'Severe Pain'
            }
        }
        
        if tool_name in risk_levels:
            return risk_levels[tool_name].get(score, 'Medium Risk')
        
        # Generic risk level for other tools
        if score == 0:
            return 'Low Risk'
        elif score <= 2:
            return 'Medium Risk'
        else:
            return 'High Risk'
    
    def _get_review_interval(self, tool_name: str) -> int:
        """Get review interval in weeks for each tool"""
        intervals = {
            'falls_screening': 1,
            'must_nutrition': 1,
            'waterlow': 4,
            'abbey_pain': 4,
            'cornell_depression': 12,
            'moving_handling': 24,
            'peep': 24
        }
        return intervals.get(tool_name, 4)

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