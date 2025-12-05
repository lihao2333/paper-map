#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加 date 字段到现有数据库
"""

try:
    import pysqlite3 as sqlite3
except ImportError:
    import sqlite3
import os
import shutil
from datetime import datetime

def extract_date_from_arxiv_id(arxiv_id):
    """
    从 arxiv_id 提取日期，格式：yyyyMM
    例如：2401.12345 -> 202401
    """
    if not arxiv_id:
        return None
    
    # arxiv_id 格式：YYMM.NNNNN
    # 需要转换为 yyyyMM
    parts = arxiv_id.split('.')
    if len(parts) != 2:
        return None
    
    yymm = parts[0]
    if len(yymm) != 4:
        return None
    
    yy = int(yymm[:2])
    mm = yymm[2:]
    
    # 判断年份：00-30 认为是 2000-2030，31-99 认为是 1931-1999
    if yy <= 30:
        yyyy = 2000 + yy
    else:
        yyyy = 1900 + yy
    
    return f"{yyyy}{mm}"

def check_has_date_column(cursor):
    """检查 paper 表是否有 date 列"""
    cursor.execute("PRAGMA table_info(paper)")
    columns = [row[1] for row in cursor.fetchall()]
    return 'date' in columns

def add_date_column(db_path):
    """添加 date 字段到数据库"""
    print(f"开始添加 date 字段到数据库: {db_path}")
    
    # 备份数据库
    if os.path.exists(db_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{db_path}.backup_{timestamp}"
        shutil.copy2(db_path, backup_path)
        print(f"✅ 数据库已备份到: {backup_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查是否已经有 date 字段
        if check_has_date_column(cursor):
            print("✅ date 字段已存在，无需添加")
            return True
        
        print("添加 date 字段...")
        # 添加 date 列
        cursor.execute("ALTER TABLE paper ADD COLUMN date TEXT")
        
        # 为已有 arxiv_id 的记录填充 date
        print("为已有 arxiv_id 的记录填充 date...")
        cursor.execute("SELECT paper_id, arxiv_id FROM paper WHERE arxiv_id IS NOT NULL")
        papers = cursor.fetchall()
        
        updated_count = 0
        for paper_id, arxiv_id in papers:
            date = extract_date_from_arxiv_id(arxiv_id)
            if date:
                cursor.execute("UPDATE paper SET date = ? WHERE paper_id = ?", (date, paper_id))
                updated_count += 1
        
        conn.commit()
        print(f"✅ 成功添加 date 字段，并为 {updated_count} 条记录填充了日期")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 添加 date 字段失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    db_path = "./data/database.db"
    
    # 确保数据库目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    success = add_date_column(db_path)
    if success:
        print("\n✅ 完成！")
    else:
        print("\n❌ 失败，请检查错误信息。")


