#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 CSV 文件中提取链接并添加到 XML 文件中
"""

import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# CSV 列到 XML 列的映射
COLUMN_MAPPING = {
    'Tesla (WorldSimNN + PolicyNN)': 'Tesla',
    '理想 (VLA + RL + WM)': '理想',
    '小鹏 (VA)': '小鹏',
    'NVidia': 'NVidia',
    'XiaoMi WM': 'XiaoMi',
    '华为 (WEWA)': '华为',
}

def extract_urls_from_text(text):
    """从文本中提取所有 URL"""
    if not text:
        return []
    # 匹配 http:// 或 https:// 开头的 URL
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)
    return urls

def normalize_text(text):
    """标准化文本用于匹配"""
    if not text:
        return ""
    # 移除日期前缀 [YYYYMM]
    text = re.sub(r'\[20\d{4}\]\s*', '', text)
    # 移除多余空格
    text = ' '.join(text.split())
    return text.strip()

def extract_keywords(text):
    """提取关键词：英文单词（至少3个字符）和中文"""
    if not text:
        return set()
    # 提取英文单词（至少3个字符，忽略大小写）
    english_words = set(re.findall(r'\b[A-Za-z]{3,}\b', text.lower()))
    # 提取中文（单个字符或常见词组）
    chinese_chars = set(re.findall(r'[\u4e00-\u9fff]+', text))
    # 合并所有关键词
    keywords = english_words | chinese_chars
    return keywords

def find_matching_link(xml_text, csv_text, csv_urls):
    """根据文本内容匹配链接"""
    if not csv_urls:
        return None
    
    if not xml_text or not csv_text:
        return None
    
    # 标准化文本（保留原始格式用于匹配）
    xml_normalized = normalize_text(xml_text)
    csv_normalized = normalize_text(csv_text)
    
    # 策略1: 直接包含匹配（XML 文本在 CSV 文本中）
    if xml_normalized in csv_normalized:
        return csv_urls[0]
    
    # 策略2: 提取 CSV 文本中的项目名称（通常在冒号或链接之前）
    # 例如："[202510] PAGS https://..." -> "PAGS"
    # 或者 "DRIVINGSCENE: A MULTI-TASK..." -> "DRIVINGSCENE"
    csv_project_patterns = [
        r'([A-Z][A-Za-z0-9]+):',  # 项目名: 描述
        r'([A-Z][A-Za-z0-9]+)\s+https?://',  # 项目名 链接
        r'\[20\d{4}\]\s*([A-Z][A-Za-z0-9]+)',  # [日期] 项目名
    ]
    
    csv_projects = set()
    for pattern in csv_project_patterns:
        matches = re.findall(pattern, csv_normalized)
        csv_projects.update([m.upper() for m in matches])
    
    # 检查 XML 文本中是否包含这些项目名
    xml_upper = xml_normalized.upper()
    for project in csv_projects:
        if project in xml_upper:
            return csv_urls[0]
    
    # 策略3: 关键词匹配
    xml_keywords = extract_keywords(xml_text)
    csv_keywords = extract_keywords(csv_text)
    
    if xml_keywords and csv_keywords:
        common_keywords = xml_keywords & csv_keywords
        # 如果至少有2个关键词匹配，或者有1个较长的关键词匹配
        if len(common_keywords) >= 2:
            return csv_urls[0]
        # 如果有较长的英文关键词匹配（至少5个字符）
        long_common = {k for k in common_keywords if len(k) >= 5 and k.isalpha()}
        if long_common:
            return csv_urls[0]
    
    # 策略4: 部分匹配（XML 文本的关键部分在 CSV 中）
    # 提取 XML 中的主要英文单词（大写开头的）
    xml_main_words = re.findall(r'\b[A-Z][a-z]+\b', xml_text)
    if xml_main_words:
        csv_upper = csv_normalized.upper()
        for word in xml_main_words:
            if word.upper() in csv_upper:
                return csv_urls[0]
    
    return None

def parse_csv_file(csv_path):
    """解析 CSV 文件，返回按时间和列组织的数据"""
    data = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)  # 跳过第一行（可能是空行）
        headers = next(reader)  # 读取真正的表头
        
        for row in reader:
            if not row or not row[0]:
                continue
            
            time = row[0].strip()
            if not time or not time.isdigit():
                continue
            
            if time not in data:
                data[time] = {}
            
            # 处理每一列（从第2列开始，索引1）
            for idx, col_name in enumerate(headers[1:], start=1):
                if idx < len(row):
                    cell_text = row[idx].strip()
                    if cell_text and cell_text != '"':
                        # 提取链接
                        urls = extract_urls_from_text(cell_text)
                        if col_name in COLUMN_MAPPING:
                            xml_col = COLUMN_MAPPING[col_name]
                            if xml_col not in data[time]:
                                data[time][xml_col] = []
                            data[time][xml_col].append({
                                'text': cell_text,
                                'urls': urls
                            })
    
    return data

def update_xml_with_links(xml_path, csv_data):
    """更新 XML 文件，添加链接"""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    updated_count = 0
    
    for record in root.find('records').findall('record'):
        identifier = record.find('identifier')
        if identifier is None:
            continue
        
        time = identifier.text.strip()
        if time not in csv_data:
            continue
        
        # 处理该时间的所有 item
        for item in record.findall('item'):
            col_name = item.get('column')
            if not col_name or col_name not in csv_data[time]:
                continue
            
            xml_text = item.text.strip() if item.text else ""
            
            # 如果已经有 link 属性，跳过
            if item.get('link'):
                continue
            
            # 在 CSV 数据中查找匹配的链接
            for csv_entry in csv_data[time][col_name]:
                link = find_matching_link(xml_text, csv_entry['text'], csv_entry['urls'])
                if link:
                    item.set('link', link)
                    updated_count += 1
                    break
    
    # 保存更新后的 XML
    tree.write(xml_path, encoding='utf-8', xml_declaration=True)
    return updated_count

def main():
    csv_path = Path('工作调研 - 友商工作.csv')
    xml_path = Path('competitor_survey.xml')
    
    if not csv_path.exists():
        print(f"错误: CSV 文件不存在: {csv_path}")
        return
    
    if not xml_path.exists():
        print(f"错误: XML 文件不存在: {xml_path}")
        return
    
    print("正在解析 CSV 文件...")
    csv_data = parse_csv_file(csv_path)
    print(f"找到 {len(csv_data)} 个时间点的数据")
    
    print("正在更新 XML 文件...")
    updated_count = update_xml_with_links(xml_path, csv_data)
    
    print(f"完成！共更新了 {updated_count} 个链接")

if __name__ == '__main__':
    main()

