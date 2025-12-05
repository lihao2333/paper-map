#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试重构后的功能
"""

import sys
from database import Database
from link_parser import LinkParser

def test_database():
    """测试数据库基本功能"""
    print("=" * 60)
    print("测试数据库功能")
    print("=" * 60)
    
    db_path = "./data/database.db"
    database = Database(db_path)
    
    # 1. 测试获取论文数量
    print("\n1. 测试获取论文数量...")
    arxiv_ids = database.get_arxiv_ids()
    print(f"   arXiv 论文数量: {len(arxiv_ids)}")
    
    paper_ids = database.get_paper_ids()
    print(f"   总论文数量: {len(paper_ids)}")
    
    # 2. 测试获取论文信息
    if arxiv_ids:
        print("\n2. 测试获取论文信息...")
        test_arxiv_id = arxiv_ids[0]
        paper_info = database.get_paper_info(arxiv_id=test_arxiv_id)
        if paper_info:
            print(f"   测试 arXiv ID: {test_arxiv_id}")
            print(f"   paper_id: {paper_info.get('paper_id')}")
            print(f"   arxiv_id: {paper_info.get('arxiv_id')}")
            print(f"   paper_url: {paper_info.get('paper_url')}")
            print(f"   alias: {paper_info.get('alias', '')[:50]}...")
        else:
            print(f"   ❌ 无法获取论文信息: {test_arxiv_id}")
    
    # 3. 测试获取所有论文详情
    print("\n3. 测试获取所有论文详情...")
    all_papers = database.get_all_papers_with_details()
    print(f"   获取到 {len(all_papers)} 条论文记录")
    if all_papers:
        sample = all_papers[0]
        print(f"   示例论文:")
        print(f"     paper_id: {sample.get('paper_id')}")
        print(f"     arxiv_id: {sample.get('arxiv_id')}")
        print(f"     paper_url: {sample.get('paper_url')}")
        print(f"     公司数量: {len(sample.get('company_names', []))}")
        print(f"     高校数量: {len(sample.get('university_names', []))}")
    
    print("\n✅ 数据库测试完成")

def test_link_parser():
    """测试链接解析器"""
    print("\n" + "=" * 60)
    print("测试链接解析器")
    print("=" * 60)
    
    parser = LinkParser()
    
    test_cases = [
        "https://arxiv.org/abs/2401.12345",
        "https://arxiv.org/pdf/2401.12345.pdf",
        "2401.12345",
        "https://example.com/paper",
        "https://openreview.net/forum?id=xxx",
        "https://github.com/user/repo",
    ]
    
    for url in test_cases:
        try:
            result = parser.parse(url)
            is_arxiv = parser.is_arxiv_link(url)
            print(f"\n输入: {url}")
            print(f"  paper_id: {result['paper_id']}")
            print(f"  arxiv_id: {result['arxiv_id']}")
            print(f"  paper_url: {result['paper_url']}")
            print(f"  是 arXiv: {is_arxiv}")
        except Exception as e:
            print(f"\n输入: {url}")
            print(f"  ❌ 错误: {e}")
    
    print("\n✅ 链接解析器测试完成")

def test_insert_paper():
    """测试插入论文（使用新格式）"""
    print("\n" + "=" * 60)
    print("测试插入论文（新格式）")
    print("=" * 60)
    
    db_path = "./data/database.db"
    database = Database(db_path)
    
    # 测试插入非 arXiv 论文
    test_paper = {
        "paper_id": "test_paper_001",
        "paper_url": "https://example.com/test-paper",
        "arxiv_id": None,
        "alias": "TestPaper",
        "full_name": "Test Paper: A Sample Paper",
        "abstract": "This is a test abstract."
    }
    
    try:
        database.insert_paper([test_paper])
        print(f"✅ 成功插入测试论文: {test_paper['paper_id']}")
        
        # 验证插入
        paper_info = database.get_paper_info(paper_id=test_paper['paper_id'])
        if paper_info:
            print(f"   验证成功:")
            print(f"     paper_id: {paper_info['paper_id']}")
            print(f"     paper_url: {paper_info['paper_url']}")
            print(f"     arxiv_id: {paper_info['arxiv_id']}")
            
            # 清理测试数据
            # 注意：这里只是测试，实际应用中可能需要删除功能
            print(f"   ⚠️  注意：测试数据已插入，可能需要手动清理")
        else:
            print(f"   ❌ 无法验证插入的数据")
    except Exception as e:
        print(f"❌ 插入失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ 插入论文测试完成")

if __name__ == "__main__":
    print("开始测试重构后的功能...\n")
    
    try:
        test_database()
        test_link_parser()
        test_insert_paper()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成！")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


