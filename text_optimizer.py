
import re
from typing import Dict, List

class TextOptimizer:
    """智能文本優化，減少 token 使用量"""
    
    def __init__(self):
        self.care_keywords = [
            'bowel', 'water', 'food', 'medication', 'pain', 'mobility', 
            'fall', 'skin', 'behaviour', 'confusion', 'agitation'
        ]
        
    def compress_log_content(self, content: str, max_length: int = 8000) -> str:
        """壓縮日誌內容，保留重要資訊"""
        if len(content) <= max_length:
            return content
            
        lines = content.split('\n')
        important_lines = []
        
        # 優先保留包含關鍵詞的行
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in self.care_keywords):
                important_lines.append(line)
            elif re.search(r'\d+', line):  # 保留包含數字的行
                important_lines.append(line)
                
        # 如果還是太長，進一步壓縮
        if len('\n'.join(important_lines)) > max_length:
            # 只保留最近的記錄
            important_lines = important_lines[-50:]
            
        return '\n'.join(important_lines)
    
    def summarize_care_plan(self, content: str, max_length: int = 5000) -> str:
        """壓縮護理計劃，保留核心資訊"""
        if len(content) <= max_length:
            return content
            
        # 保留標題和重要段落
        lines = content.split('\n')
        key_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
                
            # 保留標題
            if line_stripped.startswith('#') or ':' in line_stripped:
                key_lines.append(line)
            # 保留包含關鍵醫療資訊的行
            elif any(keyword in line.lower() for keyword in self.care_keywords):
                key_lines.append(line)
                
        return '\n'.join(key_lines)
