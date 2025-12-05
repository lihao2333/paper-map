#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除数据库中指定标签的所有关联
"""

import os
import sys
from database import Database

def get_tag_id_by_name(db_path, tag_name):
    """根据标签名获取标签 ID"""
    try:
        import pysqlite3 as sqlite3
    except ImportError:
        import sqlite3
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tag_id FROM tag WHERE tag_name = ?", (tag_name,))
        result = cursor.fetchone()
        return result[0] if result else None

def get_papers_with_tag(db_path, tag_id):
    """获取所有有这个标签的论文"""
    try:
        import pysqlite3 as sqlite3
    except ImportError:
        import sqlite3
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT pt.paper_id, p.arxiv_id, p.alias, p.full_name
            FROM paper_tag pt
            JOIN paper p ON pt.paper_id = p.paper_id
            WHERE pt.tag_id = ?
            ORDER BY p.date DESC, pt.paper_id
        """, (tag_id,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "paper_id": row[0],
                "arxiv_id": row[1],
                "alias": row[2] or "",
                "full_name": row[3] or ""
            })
        return results

def remove_tag_from_all_papers(db_path, tag_name, dry_run=True):
    """删除指定标签的所有关联"""
    database = Database(db_path)
    
    # 获取标签 ID
    tag_id = get_tag_id_by_name(db_path, tag_name)
    if not tag_id:
        print(f"标签 '{tag_name}' 不存在")
        return []
    
    # 获取所有有这个标签的论文
    papers = get_papers_with_tag(db_path, tag_id)
    
    if len(papers) == 0:
        print(f"没有找到有标签 '{tag_name}' 的论文")
        return []
    
    print(f"\n找到 {len(papers)} 篇论文有标签 '{tag_name}':")
    print("-" * 80)
    for i, paper in enumerate(papers, 1):
        print(f"{i}. [{paper['paper_id']}] {paper['arxiv_id'] or 'N/A'}")
        if paper['alias']:
            print(f"   别名: {paper['alias']}")
        if paper['full_name']:
            print(f"   标题: {paper['full_name'][:100]}...")
        print()
    
    if dry_run:
        print("-" * 80)
        print(f"【模拟模式】将删除这 {len(papers)} 篇论文的标签 '{tag_name}'")
        print("使用 --yes 参数可实际执行删除操作")
        return papers
    
    # 实际删除
    print("-" * 80)
    print(f"正在删除这 {len(papers)} 篇论文的标签 '{tag_name}'...")
    
    success_count = 0
    error_count = 0
    
    for paper in papers:
        paper_id = paper["paper_id"]
        try:
            database.remove_tag_from_paper(paper_id, tag_id)
            print(f"  ✅ [{paper_id}]: 已删除标签 '{tag_name}'")
            success_count += 1
        except Exception as e:
            print(f"  ❌ [{paper_id}]: 删除标签失败 - {str(e)}")
            error_count += 1
    
    print("\n" + "=" * 80)
    print("操作完成！")
    print(f"  成功删除: {success_count} 篇")
    print(f"  失败: {error_count} 篇")
    print("=" * 80)
    
    return papers

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='删除数据库中指定标签的所有关联')
    parser.add_argument('tag_name', help='要删除的标签名称（例如: feedforward.static_scene）')
    parser.add_argument('--yes', '-y', action='store_true', help='实际执行删除操作（默认是模拟模式）')
    args = parser.parse_args()
    
    # 数据库路径
    db_path = "./data/database.db"
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)
    
    # 删除标签
    dry_run = not args.yes
    remove_tag_from_all_papers(db_path, args.tag_name, dry_run=dry_run)

if __name__ == "__main__":
    main()
