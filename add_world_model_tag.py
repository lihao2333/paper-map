#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索数据库中所有与 world_model 相关的论文，并给它们打上 world_model 标签
"""

import os
import sys
from database import Database

def search_world_model_papers(db_path):
    """
    搜索数据库中所有与 world_model 相关的论文
    搜索字段包括：alias, full_name, abstract, summary
    """
    try:
        import pysqlite3 as sqlite3
    except ImportError:
        import sqlite3
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # 搜索关键词（不区分大小写）
        keywords = ['world_model', 'world model', 'worldmodel', 'world-model']
        search_patterns = [f"%{kw}%" for kw in keywords]
        
        # 构建查询：搜索 alias, full_name, abstract, summary 字段
        conditions = []
        params = []
        
        for pattern in search_patterns:
            conditions.append("""
                (LOWER(alias) LIKE LOWER(?)
                 OR LOWER(full_name) LIKE LOWER(?)
                 OR LOWER(abstract) LIKE LOWER(?)
                 OR LOWER(summary) LIKE LOWER(?))
            """)
            params.extend([pattern] * 4)
        
        query = f"""
            SELECT DISTINCT paper_id, arxiv_id, alias, full_name
            FROM paper
            WHERE {' OR '.join(conditions)}
            ORDER BY date DESC, paper_id
        """
        
        cursor.execute(query, params)
        results = []
        for row in cursor.fetchall():
            results.append({
                "paper_id": row[0],
                "arxiv_id": row[1],
                "alias": row[2] or "",
                "full_name": row[3] or ""
            })
        
        return results

def main():
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='搜索数据库中所有与 world_model 相关的论文，并给它们打上 world_model 标签')
    parser.add_argument('--yes', '-y', action='store_true', help='自动确认，不需要用户输入')
    args = parser.parse_args()
    
    # 数据库路径
    db_path = "./data/database.db"
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)
    
    # 初始化数据库
    database = Database(db_path)
    
    # 搜索所有与 world_model 相关的论文
    print("正在搜索数据库中所有与 world_model 相关的论文...")
    papers = search_world_model_papers(db_path)
    
    print(f"\n找到 {len(papers)} 篇相关论文:")
    print("-" * 80)
    
    # 显示找到的论文
    for i, paper in enumerate(papers, 1):
        print(f"{i}. [{paper['paper_id']}] {paper['arxiv_id'] or 'N/A'}")
        if paper['alias']:
            print(f"   别名: {paper['alias']}")
        if paper['full_name']:
            print(f"   标题: {paper['full_name'][:100]}...")
        print()
    
    if len(papers) == 0:
        print("没有找到相关论文。")
        return
    
    # 确认是否继续
    print("-" * 80)
    if not args.yes:
        try:
            response = input(f"\n是否给这 {len(papers)} 篇论文添加 'world_model' 标签？(y/n): ")
            if response.lower() != 'y':
                print("操作已取消。")
                return
        except EOFError:
            print("\n检测到非交互式环境，使用 --yes 参数可自动确认")
            print("操作已取消。")
            return
    else:
        print(f"\n自动确认：将给这 {len(papers)} 篇论文添加 'world_model' 标签...")
    
    # 添加标签
    tag_name = "world_model"
    print(f"\n正在添加标签 '{tag_name}'...")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for paper in papers:
        paper_id = paper['paper_id']
        try:
            # 检查是否已经有这个标签
            existing_tags = database.get_paper_tags(paper_id)
            tag_names = [tag["tag_name"] for tag in existing_tags]
            
            if tag_name in tag_names:
                print(f"  ⏭️  跳过 [{paper_id}]: 已有标签 '{tag_name}'")
                skip_count += 1
            else:
                tag_id, created = database.add_tag_to_paper(paper_id, tag_name)
                if created:
                    print(f"  ✅ [{paper_id}]: 添加标签 '{tag_name}' (新建标签)")
                else:
                    print(f"  ✅ [{paper_id}]: 添加标签 '{tag_name}'")
                success_count += 1
        except Exception as e:
            print(f"  ❌ [{paper_id}]: 添加标签失败 - {str(e)}")
            error_count += 1
    
    # 显示统计信息
    print("\n" + "=" * 80)
    print("操作完成！")
    print(f"  成功添加: {success_count} 篇")
    print(f"  已存在标签: {skip_count} 篇")
    print(f"  失败: {error_count} 篇")
    print("=" * 80)

if __name__ == "__main__":
    main()
