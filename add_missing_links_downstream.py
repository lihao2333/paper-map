#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 downstream_tasks_survey.xml 中缺少链接的条目搜索并添加链接
"""

import xml.etree.ElementTree as ET
import requests
import time
import re
from pathlib import Path

ARXIV_API_BASE = "http://export.arxiv.org/api/query"

def search_arxiv(title, max_results=5):
    """在 arXiv 上搜索论文"""
    # 清理标题，提取模型名称
    search_query = title.replace(':', '').replace('(', '').replace(')', '').replace('-', ' ')
    # 移除版本号如 V2, V3 等
    search_query = re.sub(r'\s+V\d+', '', search_query, flags=re.IGNORECASE)
    # 提取主要关键词
    words = search_query.split()
    # 使用前几个关键词进行搜索
    query = ' OR '.join(words[:5])
    
    params = {
        'search_query': f'all:{query}',
        'start': 0,
        'max_results': max_results,
        'sortBy': 'relevance',
        'sortOrder': 'descending'
    }
    
    try:
        response = requests.get(ARXIV_API_BASE, params=params, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"搜索 arXiv 时出错: {e}")
        return None

def parse_arxiv_response(xml_text, original_title):
    """解析 arXiv API 响应，找到最匹配的论文"""
    if not xml_text:
        return None
    
    try:
        root = ET.fromstring(xml_text)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        entries = root.findall('atom:entry', ns)
        if not entries:
            return None
        
        # 提取模型名称
        model_match = re.match(r'^([^:]+?):', original_title)
        if model_match:
            model_name = model_match.group(1).strip()
        else:
            model_name = original_title.split()[0] if original_title.split() else original_title
        
        # 提取关键词
        original_keywords = set(re.findall(r'\b[A-Z][a-z]+\b|\b[A-Z]{2,}\b', model_name))
        
        best_match = None
        best_score = 0
        
        for entry in entries:
            title_elem = entry.find('atom:title', ns)
            if title_elem is None:
                continue
            
            arxiv_title = title_elem.text.strip()
            arxiv_title = ' '.join(arxiv_title.split())
            
            # 计算匹配分数
            arxiv_keywords = set(re.findall(r'\b[A-Z][a-z]+\b|\b[A-Z]{2,}\b', arxiv_title))
            common_keywords = original_keywords & arxiv_keywords
            
            score = len(common_keywords)
            
            # 如果模型名称在标题中，大幅增加分数
            if model_name.lower() in arxiv_title.lower():
                score += 5
            
            # 检查主要单词
            model_words = model_name.split()
            for word in model_words:
                if len(word) > 3 and word.lower() in arxiv_title.lower():
                    score += 2
            
            if score > best_score:
                best_score = score
                id_elem = entry.find('atom:id', ns)
                published_elem = entry.find('atom:published', ns)
                
                if id_elem is not None:
                    arxiv_id = id_elem.text.strip()
                    arxiv_id_match = re.search(r'arxiv\.org/abs/(\d+\.\d+)', arxiv_id)
                    if arxiv_id_match:
                        paper_id = arxiv_id_match.group(1)
                        link = f"https://arxiv.org/abs/{paper_id}"
                        
                        published_date = None
                        if published_elem is not None:
                            published_date = published_elem.text.strip()[:10]
                        
                        best_match = {
                            'link': link,
                            'title': arxiv_title,
                            'published': published_date,
                            'score': score
                        }
        
        if best_score < 2:
            return None
        
        return best_match
    except Exception as e:
        print(f"解析 arXiv 响应时出错: {e}")
        return None

def update_xml_with_links(xml_path):
    """更新 XML 文件，只为没有链接的条目添加链接"""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    updated_count = 0
    
    for record in root.find('records').findall('record'):
        identifier_elem = record.find('identifier')
        if identifier_elem is None:
            continue
        
        current_identifier = identifier_elem.text.strip()
        
        for item in record.findall('item'):
            # 检查是否已经有链接
            has_link = False
            if len(item) > 0:
                has_link = any(child.tag == 'a' for child in item)
            
            if has_link:
                continue  # 已经有链接，跳过
            
            text_content = item.text.strip() if item.text else ""
            if not text_content:
                continue
            
            # 跳过非论文条目（如"拉普拉斯方差"）
            if '拉普拉斯方差' in text_content or 'NIMA' in text_content and 'Neural Image Assessment' not in text_content:
                continue
            
            # 提取模型名称
            model_match = re.match(r'^([^:]+?):', text_content)
            if model_match:
                model_name = model_match.group(1).strip()
            else:
                model_name = text_content.split()[0] if text_content.split() else text_content
            
            print(f"\n搜索: {model_name}")
            print(f"当前时间: {current_identifier}")
            
            # 搜索 arXiv
            arxiv_response = search_arxiv(model_name)
            if not arxiv_response:
                print("  未找到 arXiv 结果")
                time.sleep(1)
                continue
            
            match = parse_arxiv_response(arxiv_response, model_name)
            if not match:
                print("  未找到匹配的论文")
                time.sleep(1)
                continue
            
            print(f"  找到匹配: {match['title']}")
            print(f"  链接: {match['link']}")
            print(f"  发布日期: {match['published']}")
            print(f"  匹配分数: {match['score']}")
            
            # 添加链接
            link_elem = ET.Element('a')
            link_elem.set('href', match['link'])
            link_elem.set('target', '_blank')
            link_elem.text = '[Link]'
            
            if item.text:
                item.text = item.text + ' '
            item.append(link_elem)
            
            updated_count += 1
            print(f"  ✓ 已添加链接")
            
            time.sleep(2)
    
    tree.write(xml_path, encoding='utf-8', xml_declaration=True)
    return updated_count

def main():
    xml_path = Path('downstream_tasks_survey.xml')
    
    if not xml_path.exists():
        print(f"错误: XML 文件不存在: {xml_path}")
        return
    
    print("开始搜索 arXiv 并为缺少链接的条目添加链接...")
    print("这可能需要一些时间，请耐心等待...\n")
    
    updated_count = update_xml_with_links(xml_path)
    
    print(f"\n完成！")
    print(f"共添加了 {updated_count} 个链接")

if __name__ == '__main__':
    main()






