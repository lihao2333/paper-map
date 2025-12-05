#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索关注公司近一年的 3DGS/WorldModel/Simulator 相关工作并插入数据库
"""

import arxiv
import json
import os
import time
from datetime import datetime, timedelta
from database import Database

def load_company_config():
    """加载公司配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'car_companies_config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def search_papers_by_company_and_keywords(company_name, keywords, max_results=200):
    """
    搜索指定公司和关键词的论文
    
    Args:
        company_name: 公司名称（英文）
        keywords: 关键词列表，如 ["3dgs", "worldmodel", "simulator"]
        max_results: 最大结果数
    
    Returns:
        arxiv_id 列表
    """
    client = arxiv.Client()
    
    # 构建查询：公司名称 AND (关键词1 OR 关键词2 OR ...)
    keyword_query = " OR ".join([f'"{kw}"' for kw in keywords])
    query = f'({company_name}) AND ({keyword_query})'
    
    # 计算近一年的日期范围（2024年1月1日至今）
    start_date = datetime(2024, 1, 1)
    end_date = datetime.now()
    
    print(f"\n搜索: {company_name}")
    print(f"查询: {query}")
    print(f"日期范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    
    try:
        # 使用 arxiv API 搜索
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        arxiv_ids = []
        for paper in client.results(search):
            # 检查日期是否在近一年内（2024年1月1日之后）
            if paper.published:
                # 转换为 datetime 对象（如果还不是）
                if isinstance(paper.published, datetime):
                    pub_date = paper.published
                else:
                    # 如果是 date 对象，转换为 datetime
                    from datetime import date
                    if isinstance(paper.published, date):
                        pub_date = datetime.combine(paper.published, datetime.min.time())
                    else:
                        continue
                
                if pub_date >= start_date:
                    arxiv_id = paper.entry_id.split('/')[-1]
                    arxiv_ids.append(arxiv_id)
                    print(f"  [{pub_date.strftime('%Y-%m-%d')}] {arxiv_id} - {paper.title[:60]}...")
        
        print(f"  共找到 {len(arxiv_ids)} 篇论文（在日期范围内）")
        return arxiv_ids
    
    except Exception as e:
        print(f"  搜索出错: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    # 数据库路径
    db_path = "./data/database.db"
    
    # 确保数据库目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # 初始化数据库
    database = Database(db_path)
    database.construct()
    
    # 加载公司配置
    company_config = load_company_config()
    
    # 关键词列表（使用更精确的关键词）
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
    for chinese_name, english_names in company_config.items():
        if chinese_name.startswith('_'):
            continue
        for eng_name in english_names:
            # 移除通配符，使用基础名称
            base_name = eng_name.replace('*', '').replace('?', '').strip()
            if base_name:
                all_company_names.add(base_name)
    
    print(f"共 {len(all_company_names)} 个公司名称需要搜索")
    print(f"关键词: {', '.join(keywords)}")
    
    # 收集所有找到的 arxiv_id
    all_arxiv_ids = set()
    
    # 对每个公司名称进行搜索
    for i, company_name in enumerate(sorted(all_company_names), 1):
        print(f"\n[{i}/{len(all_company_names)}] 处理公司: {company_name}")
        arxiv_ids = search_papers_by_company_and_keywords(company_name, keywords)
        all_arxiv_ids.update(arxiv_ids)
        
        # 避免请求过快，添加延迟
        time.sleep(3)
    
    print(f"\n\n总共找到 {len(all_arxiv_ids)} 个唯一的 arxiv_id")
    
    # 准备插入数据（只插入 arxiv_id，其他字段为 None）
    data = [(arxiv_id, None, None, None) for arxiv_id in sorted(all_arxiv_ids)]
    
    # 插入数据库
    print(f"\n正在插入到数据库 {db_path}...")
    try:
        database.insert_paper(data)
        print(f"成功插入/更新 {len(data)} 条记录")
    except Exception as e:
        print(f"插入时出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

