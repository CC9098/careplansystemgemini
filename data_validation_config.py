
"""
Data Validation and Chart Configuration
數據驗證和圖表配置文件

This file contains all the rules and thresholds for data validation and chart display.
You can modify these values to adjust how data is filtered and displayed.
"""

# =============================================================================
# BOWEL MOVEMENT VALIDATION RULES
# 排便次數驗證規則
# =============================================================================

BOWEL_MOVEMENT_CONFIG = {
    # Valid range for daily bowel movements
    # 每日排便次數的有效範圍
    'min_count': 0,          # Minimum allowed bowel movements per day
    'max_count': 10,         # Maximum allowed bowel movements per day (reduced from 15)
    
    # Keywords to identify bowel movement records
    # 識別排便記錄的關鍵字
    'keywords': [
        'bowel', 'stool', 'defecation', 'bm', 'toilet',
        '排便', '大便', '如廁', '便便'
    ],
    
    # Alert thresholds
    # 警報閾值
    'low_frequency_alert': 1,    # Alert if average < 1 per day
    'high_frequency_alert': 5,   # Alert if average > 5 per day
}

# =============================================================================
# WATER INTAKE VALIDATION RULES
# 飲水量驗證規則
# =============================================================================

WATER_INTAKE_CONFIG = {
    # Valid range for daily water intake (in ml)
    # 每日飲水量的有效範圍（毫升）
    'min_amount': 100,       # Minimum allowed water intake per day
    'max_amount': 4000,      # Maximum allowed water intake per day
    
    # Keywords to identify water intake records
    # 識別飲水記錄的關鍵字
    'keywords': [
        'water', 'fluid', 'drink', 'ml', 'liter', 'hydration',
        '飲水', '水分', '毫升', '升', '液體', '喝水'
    ],
    
    # Alert thresholds
    # 警報閾值
    'low_intake_alert': 1200,    # Alert if average < 1200ml per day
    'high_intake_alert': 3000,   # Alert if average > 3000ml per day
}

# =============================================================================
# FOOD INTAKE VALIDATION RULES
# 進食量驗證規則
# =============================================================================

FOOD_INTAKE_CONFIG = {
    # Valid range for food intake percentage
    # 進食量百分比的有效範圍
    'min_percentage': 0,     # Minimum allowed food intake percentage
    'max_percentage': 100,   # Maximum allowed food intake percentage
    
    # Keywords to identify food intake records
    # 識別進食記錄的關鍵字
    'keywords': [
        'food', 'eat', 'meal', 'intake', 'consumption', '%', 'percent',
        '進食', '食量', '用餐', '餐', '吃', '食物'
    ],
    
    # Alert thresholds
    # 警報閾值
    'low_intake_alert': 60,      # Alert if average < 60%
    'normal_intake_threshold': 80, # Consider normal if >= 80%
}

# =============================================================================
# INCIDENT DETECTION RULES
# 異常事件檢測規則
# =============================================================================

INCIDENT_CONFIG = {
    # Keywords to identify incidents
    # 識別異常事件的關鍵字
    'general_keywords': [
        'fall', 'incident', 'accident', 'injury', 'problem', 'concern',
        'unusual', 'abnormal', 'emergency', 'alert',
        '跌倒', '異常', '問題', '事故', '受傷', '意外', '緊急', '警報'
    ],
    
    # High severity keywords (will mark as high priority)
    # 高嚴重性關鍵字（標記為高優先級）
    'high_severity_keywords': [
        'severe', 'serious', 'emergency', 'injury', 'hospital', 'doctor',
        'bleeding', 'fracture', 'unconscious',
        '嚴重', '緊急', '受傷', '醫院', '醫生', '出血', '骨折', '昏迷'
    ],
    
    # Medium severity keywords
    # 中等嚴重性關鍵字
    'medium_severity_keywords': [
        'minor', 'small', 'slight', 'bruise', 'scratch',
        '輕微', '小', '擦傷', '瘀傷'
    ]
}

# =============================================================================
# CHART DISPLAY SETTINGS
# 圖表顯示設置
# =============================================================================

CHART_CONFIG = {
    # Chart colors
    # 圖表顏色
    'water_chart_color': '#3498db',
    'bowel_chart_color': '#e67e22',
    'food_chart_color': '#27ae60',
    
    # Chart display limits
    # 圖表顯示限制
    'max_data_points': 31,       # Maximum number of days to show in charts
    'min_data_points_required': 3, # Minimum data points needed to show chart
    
    # Y-axis settings
    # Y軸設置
    'water_y_max': 4000,         # Maximum Y value for water chart
    'bowel_y_max': 10,           # Maximum Y value for bowel chart
    'food_y_max': 100,           # Maximum Y value for food chart
}

# =============================================================================
# STATISTICS CALCULATION SETTINGS
# 統計計算設置
# =============================================================================

STATS_CONFIG = {
    # How to handle missing data
    # 如何處理缺失數據
    'ignore_zero_values': True,   # Ignore zero values in average calculation
    'require_min_days': 3,        # Require at least 3 days of data for statistics
    
    # Rounding settings
    # 四捨五入設置
    'decimal_places': {
        'water': 0,               # Round water intake to whole numbers
        'bowel': 1,               # Round bowel movements to 1 decimal place
        'food': 0,                # Round food intake to whole numbers
    }
}

# =============================================================================
# DATE FORMAT SETTINGS
# 日期格式設置
# =============================================================================

DATE_CONFIG = {
    # Supported date formats for parsing
    # 支持的日期格式
    'supported_formats': [
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # MM/DD/YYYY or DD/MM/YYYY
        r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',    # YYYY/MM/DD
        r'(\d{1,2}\.\d{1,2}\.\d{2,4})',      # DD.MM.YYYY
        r'(\d{4}\.\d{1,2}\.\d{1,2})'         # YYYY.MM.DD
    ]
}

# =============================================================================
# HELPER FUNCTIONS
# 輔助函數
# =============================================================================

def is_valid_bowel_movement(count):
    """Check if bowel movement count is valid"""
    return BOWEL_MOVEMENT_CONFIG['min_count'] <= count <= BOWEL_MOVEMENT_CONFIG['max_count']

def is_valid_water_intake(amount):
    """Check if water intake amount is valid"""
    return WATER_INTAKE_CONFIG['min_amount'] <= amount <= WATER_INTAKE_CONFIG['max_amount']

def is_valid_food_intake(percentage):
    """Check if food intake percentage is valid"""
    return FOOD_INTAKE_CONFIG['min_percentage'] <= percentage <= FOOD_INTAKE_CONFIG['max_percentage']

def get_incident_severity(description):
    """Determine incident severity based on description"""
    description_lower = description.lower()
    
    if any(keyword in description_lower for keyword in INCIDENT_CONFIG['high_severity_keywords']):
        return 'high'
    elif any(keyword in description_lower for keyword in INCIDENT_CONFIG['medium_severity_keywords']):
        return 'medium'
    else:
        return 'medium'  # Default to medium if no specific keywords found

# =============================================================================
# CONFIGURATION NOTES
# 配置說明
# =============================================================================

"""
USAGE INSTRUCTIONS / 使用說明:

1. To adjust data validation ranges, modify the min/max values in each config section
   要調整數據驗證範圍，修改各配置部分的最小/最大值

2. To add new keywords for detection, add them to the 'keywords' lists
   要添加新的檢測關鍵字，將它們添加到'keywords'列表中

3. To change alert thresholds, modify the alert values in each config
   要更改警報閾值，修改各配置中的警報值

4. To customize chart colors, modify the color values in CHART_CONFIG
   要自定義圖表顏色，修改CHART_CONFIG中的顏色值

5. After making changes, restart the application to apply new settings
   修改後，重啟應用程序以應用新設置

COMMON ISSUES / 常見問題:

- If you see too many false positives, increase the min/max ranges
  如果看到太多誤報，增加最小/最大範圍

- If data is being filtered out incorrectly, check the keywords lists
  如果數據被錯誤過濾，檢查關鍵字列表

- If charts don't show data, check min_data_points_required setting
  如果圖表不顯示數據，檢查min_data_points_required設置
"""
