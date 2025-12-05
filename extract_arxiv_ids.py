#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 XML 文件中提取所有 arxiv 链接的 ID，并导出为 txt 文件
"""

import xml.etree.ElementTree as ET
import re
import os

def extract_arxiv_id(url):
    """
    从 arxiv URL 中提取 arxiv ID
    支持的格式：
    - https://arxiv.org/abs/2511.10647
    - https://arxiv.org/pdf/2511.10647.pdf
    - arxiv.org/abs/2511.10647
    """
    # 匹配 arxiv ID 的正则表达式
    # 格式：YYYY.MMMMM 或 MMMM.MMMMM（旧格式）
    pattern = r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{5}|\d{7}\.\d{5})'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

def extract_arxiv_ids_from_xml(xml_path):
    """
    从 XML 文件中提取所有 arxiv ID
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    arxiv_ids = []
    
    # 遍历所有 record
    for record in root.find('records').findall('record'):
        # 遍历所有 item
        for item in record.findall('item'):
            # 查找所有 <a> 标签
            for link in item.findall('a'):
                href = link.get('href', '')
                if href:
                    arxiv_id = extract_arxiv_id(href)
                    if arxiv_id:
                        arxiv_ids.append(arxiv_id)
    
    # 去重并排序
    arxiv_ids = sorted(list(set(arxiv_ids)))
    
    return arxiv_ids

def main():
    import glob
    
    # 查找所有 XML 文件
    xml_files = glob.glob('*.xml')
    xml_files.sort()
    
    output_path = 'arxiv_ids.txt'
    
    all_arxiv_ids = []
    file_stats = {}
    
    print(f"找到 {len(xml_files)} 个 XML 文件\n")
    
    # 处理每个 XML 文件
    for xml_path in xml_files:
        print(f"正在处理: {xml_path}...")
        try:
            arxiv_ids = extract_arxiv_ids_from_xml(xml_path)
            all_arxiv_ids.extend(arxiv_ids)
            file_stats[xml_path] = len(arxiv_ids)
            print(f"  找到 {len(arxiv_ids)} 个 arxiv ID")
        except Exception as e:
            print(f"  错误: {e}")
            file_stats[xml_path] = 0
    
    # 去重并排序
    unique_arxiv_ids = sorted(list(set(all_arxiv_ids)))
    
    print(f"\n总共找到 {len(unique_arxiv_ids)} 个唯一的 arxiv ID")
    print(f"\n各文件统计:")
    for xml_path, count in file_stats.items():
        print(f"  {xml_path}: {count} 个")
    
    # 写入 txt 文件
    with open(output_path, 'w', encoding='utf-8') as f:
        for arxiv_id in unique_arxiv_ids:
            f.write(arxiv_id + '\n')
    
    print(f"\n已导出到 {output_path}")
    print(f"\n前10个 ID:")
    for i, arxiv_id in enumerate(unique_arxiv_ids[:10], 1):
        print(f"  {i}. {arxiv_id}")

if __name__ == '__main__':
    main()

