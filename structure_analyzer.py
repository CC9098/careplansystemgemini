
import csv
import json
import re
from collections import defaultdict
import anthropic
import os

# Initialize Claude client for structure analysis
api_key = os.environ.get('CLAUDE')
structure_client = anthropic.Anthropic(api_key=api_key) if api_key else None

def analyze_csv_structure(csv_content, max_rows=10):
    """
    Analyze CSV structure using AI to understand data patterns and importance
    
    Args:
        csv_content: String content of CSV file
        max_rows: Number of rows to analyze for structure
    
    Returns:
        dict: JSON structure with column analysis and compression recommendations
    """
    if not structure_client:
        return get_fallback_structure(csv_content, max_rows)
    
    # Get preview of CSV
    lines = csv_content.split('\n')
    preview_lines = lines[:max_rows] if len(lines) > max_rows else lines
    preview_content = '\n'.join(preview_lines)
    
    prompt = f"""You are a data structure analyst. Analyze this CSV preview and provide a JSON response about its structure and data patterns.

CSV Preview (first {max_rows} rows):
{preview_content}

Analyze and return a JSON object with this exact structure:
{{
    "columns": [
        {{
            "name": "column_name",
            "data_type": "text|number|date|boolean",
            "importance": "critical|high|medium|low",
            "compression_strategy": "keep_all|sample|summarize|remove",
            "pattern_description": "Brief description of data pattern"
        }}
    ],
    "total_columns": number,
    "data_density": "high|medium|low",
    "recommended_compression_ratio": 0.1-1.0,
    "key_insights": "Brief summary of important data patterns"
}}

Guidelines:
- Mark columns as "critical" if they contain dates, names, IDs, or medical data
- Mark columns as "high" if they contain care-related information
- Mark columns as "medium" if they contain supplementary information
- Mark columns as "low" if they contain administrative or less relevant data
- Compression strategies: keep_all (important), sample (reduce rows), summarize (aggregate), remove (delete)
- Recommended compression ratio: how much to compress (0.1 = keep 10%, 1.0 = keep all)"""

    try:
        message = structure_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            return json.loads(json_match.group())
        else:
            return get_fallback_structure(csv_content, max_rows)
            
    except Exception as e:
        print(f"Structure analysis error: {e}")
        return get_fallback_structure(csv_content, max_rows)

def get_fallback_structure(csv_content, max_rows):
    """Fallback structure analysis without AI"""
    try:
        lines = csv_content.split('\n')
        if not lines:
            return {"error": "Empty CSV"}
        
        # Try to parse headers
        reader = csv.reader([lines[0]])
        headers = next(reader, [])
        
        columns = []
        for header in headers:
            # Simple heuristic classification
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in ['date', 'time', 'day']):
                importance = "critical"
                strategy = "keep_all"
            elif any(keyword in header_lower for keyword in ['name', 'id', 'resident']):
                importance = "critical" 
                strategy = "keep_all"
            elif any(keyword in header_lower for keyword in ['care', 'health', 'medical', 'bowel', 'water', 'food']):
                importance = "high"
                strategy = "sample"
            else:
                importance = "medium"
                strategy = "summarize"
            
            columns.append({
                "name": header,
                "data_type": "text",
                "importance": importance,
                "compression_strategy": strategy,
                "pattern_description": f"Column: {header}"
            })
        
        return {
            "columns": columns,
            "total_columns": len(headers),
            "data_density": "medium",
            "recommended_compression_ratio": 0.6,
            "key_insights": f"CSV with {len(headers)} columns, fallback analysis used"
        }
        
    except Exception as e:
        return {"error": f"Fallback analysis failed: {e}"}

def smart_compress_csv(csv_content, structure_info):
    """
    Compress CSV based on structure analysis
    
    Args:
        csv_content: Original CSV content
        structure_info: Structure analysis from analyze_csv_structure
        
    Returns:
        str: Compressed CSV content
    """
    if "error" in structure_info:
        return csv_content  # Return original if structure analysis failed
    
    try:
        lines = csv_content.split('\n')
        if not lines:
            return csv_content
        
        reader = csv.reader(lines)
        rows = list(reader)
        
        if not rows:
            return csv_content
        
        headers = rows[0]
        data_rows = rows[1:]
        
        # Determine which columns to keep based on structure analysis
        columns_to_keep = []
        for i, header in enumerate(headers):
            for col_info in structure_info.get('columns', []):
                if col_info['name'] == header:
                    if col_info['compression_strategy'] in ['keep_all', 'sample']:
                        columns_to_keep.append(i)
                    break
        
        # If no columns marked for keeping, keep all critical/high importance columns
        if not columns_to_keep:
            for i, header in enumerate(headers):
                for col_info in structure_info.get('columns', []):
                    if col_info['name'] == header and col_info['importance'] in ['critical', 'high']:
                        columns_to_keep.append(i)
                        break
        
        # Ensure we keep at least some columns
        if not columns_to_keep:
            columns_to_keep = list(range(min(5, len(headers))))  # Keep first 5 columns
        
        # Apply row sampling based on compression ratio
        compression_ratio = structure_info.get('recommended_compression_ratio', 0.6)
        max_rows = max(10, int(len(data_rows) * compression_ratio))
        
        # Sample rows - keep first, last, and evenly distributed middle rows
        if len(data_rows) > max_rows:
            sampled_rows = []
            if max_rows >= 3:
                sampled_rows.append(data_rows[0])  # First row
                if max_rows > 3:
                    # Sample middle rows
                    step = len(data_rows) // (max_rows - 2)
                    for i in range(step, len(data_rows) - 1, step):
                        if len(sampled_rows) < max_rows - 1:
                            sampled_rows.append(data_rows[i])
                sampled_rows.append(data_rows[-1])  # Last row
            else:
                sampled_rows = data_rows[:max_rows]
            data_rows = sampled_rows
        
        # Rebuild CSV with selected columns and rows
        compressed_rows = []
        
        # Add filtered headers
        compressed_headers = [headers[i] for i in columns_to_keep]
        compressed_rows.append(compressed_headers)
        
        # Add filtered data rows
        for row in data_rows:
            compressed_row = [row[i] if i < len(row) else '' for i in columns_to_keep]
            compressed_rows.append(compressed_row)
        
        # Convert back to CSV string
        output = []
        for row in compressed_rows:
            csv_row = ','.join(f'"{cell}"' if ',' in str(cell) or '"' in str(cell) else str(cell) for cell in row)
            output.append(csv_row)
        
        compressed_content = '\n'.join(output)
        
        # Add compression summary
        summary = f"\n\n[COMPRESSION SUMMARY]\nOriginal: {len(rows)} rows x {len(headers)} columns\nCompressed: {len(compressed_rows)} rows x {len(compressed_headers)} columns\nCompression ratio: {len(compressed_rows)/len(rows):.2f}\n"
        
        return compressed_content + summary
        
    except Exception as e:
        print(f"Compression error: {e}")
        return csv_content  # Return original on error

def is_large_file(file_content, size_threshold=50000):
    """
    Check if file is considered large and needs compression
    
    Args:
        file_content: String content of file
        size_threshold: Size threshold in characters
        
    Returns:
        bool: True if file is large
    """
    return len(file_content) > size_threshold
"""
Structure Analyzer for CSV files
Provides functions to analyze and compress large CSV files
"""

def analyze_csv_structure(content):
    """Analyze CSV structure and return metadata"""
    lines = content.split('\n')
    return {
        'total_lines': len(lines),
        'has_header': True,
        'estimated_size': len(content),
        'columns': lines[0].split(',') if lines else []
    }

def smart_compress_csv(content, structure_info):
    """Smart compression of CSV content"""
    lines = content.split('\n')
    
    # If file is very large (>1000 lines), keep every 3rd line after header
    if len(lines) > 1000:
        header = lines[0] if lines else ""
        data_lines = lines[1::3]  # Keep every 3rd line
        return header + '\n' + '\n'.join(data_lines)
    
    return content

def is_large_file(content):
    """Check if file is considered large"""
    lines = content.split('\n')
    return len(lines) > 500 or len(content) > 100000
