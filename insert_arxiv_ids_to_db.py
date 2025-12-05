#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 arxiv_ids.txt 中的 arxiv ID 插入到数据库中
"""

from database import Database
import os

def read_arxiv_ids(txt_path):
    """从 txt 文件中读取 arxiv ID 列表"""
    arxiv_ids = []
    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f:
            arxiv_id = line.strip()
            if arxiv_id:  # 跳过空行
                arxiv_ids.append(arxiv_id)
    return arxiv_ids

def main():
    # 数据库路径
    db_path = "./data/database.db"
    
    # 确保数据库目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # 初始化数据库
    database = Database(db_path)
    database.construct()
    
    # 读取 arxiv IDs
    arxiv_ids_file = "arxiv_ids.txt"
    print(f"正在读取 {arxiv_ids_file}...")
    arxiv_ids = read_arxiv_ids(arxiv_ids_file)
    print(f"找到 {len(arxiv_ids)} 个 arxiv ID")
    
    # 准备数据：executemany 需要元组列表
    # 格式：(arxiv_id, alias, full_name)
    data = [(arxiv_id, None, None) for arxiv_id in arxiv_ids]
    
    # 插入数据库
    print(f"正在插入到数据库 {db_path}...")
    try:
        database.insert_paper(data)
        print(f"成功插入 {len(data)} 条记录")
    except Exception as e:
        print(f"插入时出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
