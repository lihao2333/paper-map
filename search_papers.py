#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索关注公司近一年的 3DGS/WorldModel/Simulator 相关工作
"""

import json
import os
import time
from datetime import datetime
from urllib.parse import quote, urlencode
from urllib.request import urlopen

def load_company_config():
    """加载公司配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'car_companies_config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def search_arxiv_api(query, max_results=100, start=0):
    """
    使用 arXiv API 搜索论文
    
    Args:
        query: 搜索查询字符串
        max_results: 最大结果数
        start: 起始位置
    
    Returns:
        论文列表，每个论文包含 arxiv_id, title, published_date 等信息
    """
    base_url = "http://export.arxiv.org/api/query"
    
    params = {
        'search_query': query,
        'start': start,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }
    
    try:
        # 构建 URL
        url = f"{base_url}?{urlencode(params)}"
        
        # 发送请求
        with urlopen(url, timeout=30) as response:
            content = response.read()
        
        # 解析 XML 响应
        import xml.etree.ElementTree as ET
        root = ET.fromstring(content)
        
        # 定义命名空间
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        papers = []
        for entry in root.findall('atom:entry', ns):
            arxiv_id_elem = entry.find('atom:id', ns)
            if arxiv_id_elem is None:
                continue
            
            arxiv_id = arxiv_id_elem.text.split('/')[-1]
            
            title_elem = entry.find('atom:title', ns)
            title = title_elem.text.strip() if title_elem is not None else ""
            
            published_elem = entry.find('atom:published', ns)
            published_date = None
            if published_elem is not None:
                try:
                    date_str = published_elem.text.replace('Z', '+00:00')
                    published_date = datetime.fromisoformat(date_str)
                    # 转换为 naive datetime（移除时区信息）
                    if published_date.tzinfo:
                        published_date = published_date.replace(tzinfo=None)
                except:
                    pass
            
            summary_elem = entry.find('atom:summary', ns)
            summary = summary_elem.text.strip() if summary_elem is not None else ""
            
            papers.append({
                'arxiv_id': arxiv_id,
                'title': title,
                'published_date': published_date,
                'summary': summary[:200] + "..." if len(summary) > 200 else summary
            })
        
        return papers
    
    except Exception as e:
        print(f"  API 请求出错: {e}")
        return []

def search_papers_by_company_and_keywords(company_name, keywords, max_results=200):
    """
    搜索指定公司和关键词的论文
    
    Args:
        company_name: 公司名称（英文）
        keywords: 关键词列表
        max_results: 最大结果数
    
    Returns:
        论文列表
    """
    # 构建查询：公司名称 AND (关键词1 OR 关键词2 OR ...)
    keyword_query = " OR ".join([f'"{kw}"' for kw in keywords])
    query = f'({company_name}) AND ({keyword_query})'
    
    # 计算近一年的日期范围（2024年1月1日至今）
    start_date = datetime(2024, 1, 1)  # naive datetime
    
    print(f"\n搜索: {company_name}")
    print(f"查询: {query}")
    
    papers = search_arxiv_api(query, max_results=max_results)
    
    # 过滤日期（2024年1月1日之后）
    filtered_papers = []
    for paper in papers:
        if paper['published_date'] and paper['published_date'] >= start_date:
            filtered_papers.append(paper)
            print(f"  [{paper['published_date'].strftime('%Y-%m-%d')}] {paper['arxiv_id']} - {paper['title'][:60]}...")
    
    print(f"  共找到 {len(filtered_papers)} 篇论文（在日期范围内）")
    return filtered_papers

def main():
    # 加载公司配置
    company_config = load_company_config()
    
    # 关键词列表
    keywords = [
        "3dgs",
        "3D Gaussian Splatting", 
        "Gaussian Splatting",
        "worldmodel",
        "world model",
        "simulator",
        "simulation"
    ]
    
    # 收集所有公司的英文名称（用于搜索）
    all_company_names = set()
    company_mapping = {}  # 英文名 -> 中文名映射
    for chinese_name, english_names in company_config.items():
        if chinese_name.startswith('_'):
            continue
        for eng_name in english_names:
            # 移除通配符，使用基础名称
            base_name = eng_name.replace('*', '').replace('?', '').strip()
            if base_name and len(base_name) > 2:  # 过滤太短的名称
                all_company_names.add(base_name)
                if base_name not in company_mapping:
                    company_mapping[base_name] = chinese_name
    
    print(f"共 {len(all_company_names)} 个公司名称需要搜索")
    print(f"关键词: {', '.join(keywords)}")
    
    # 收集所有找到的论文
    all_papers = []
    
    # 对每个公司名称进行搜索
    company_list = sorted(all_company_names)
    for i, company_name in enumerate(company_list, 1):
        print(f"\n[{i}/{len(company_list)}] 处理公司: {company_name}")
        papers = search_papers_by_company_and_keywords(company_name, keywords)
        
        # 添加公司信息到每篇论文
        for paper in papers:
            paper['company'] = company_mapping.get(company_name, company_name)
            paper['search_company'] = company_name
        
        all_papers.extend(papers)
        
        # 避免请求过快，添加延迟
        time.sleep(2)
    
    # 去重（基于 arxiv_id）
    seen_ids = set()
    unique_papers = []
    for paper in all_papers:
        if paper['arxiv_id'] not in seen_ids:
            seen_ids.add(paper['arxiv_id'])
            unique_papers.append(paper)
    
    print(f"\n\n总共找到 {len(unique_papers)} 篇唯一的论文")
    
    # 按日期排序
    unique_papers.sort(key=lambda x: x['published_date'] if x['published_date'] else datetime.min, reverse=True)
    
    # 保存到文件
    output_file = "searched_papers.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("搜索结果：关注公司近一年的 3DGS/WorldModel/Simulator 相关工作\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"搜索时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"关键词: {', '.join(keywords)}\n")
        f.write(f"日期范围: 2024-01-01 至今\n")
        f.write(f"共找到 {len(unique_papers)} 篇论文\n\n")
        
        # 按公司分组
        papers_by_company = {}
        for paper in unique_papers:
            company = paper['company']
            if company not in papers_by_company:
                papers_by_company[company] = []
            papers_by_company[company].append(paper)
        
        for company in sorted(papers_by_company.keys()):
            papers = papers_by_company[company]
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"公司: {company} ({len(papers)} 篇)\n")
            f.write("=" * 80 + "\n\n")
            
            for paper in papers:
                f.write(f"ArXiv ID: {paper['arxiv_id']}\n")
                f.write(f"标题: {paper['title']}\n")
                if paper['published_date']:
                    f.write(f"发布日期: {paper['published_date'].strftime('%Y-%m-%d')}\n")
                f.write(f"搜索匹配公司: {paper['search_company']}\n")
                if paper['summary']:
                    f.write(f"摘要预览: {paper['summary']}\n")
                f.write(f"链接: https://arxiv.org/abs/{paper['arxiv_id']}\n")
                f.write("-" * 80 + "\n\n")
        
        # 添加所有 arxiv_id 列表
        f.write("\n" + "=" * 80 + "\n")
        f.write("所有 ArXiv ID 列表（用于批量插入）\n")
        f.write("=" * 80 + "\n\n")
        for paper in unique_papers:
            f.write(f"{paper['arxiv_id']}\n")
    
    print(f"\n结果已保存到: {output_file}")
    print(f"共 {len(unique_papers)} 篇论文")

if __name__ == '__main__':
    main()

