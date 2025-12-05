#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 arxiv API 搜索论文并插入数据库
支持通过命令行参数指定查询时间段
"""

import arxiv
import argparse
import os
import re
from datetime import datetime, date, timedelta
from database import Database
from config import get_db_path


def normalize_datetime(dt):
    """
    将 datetime 对象标准化为 naive datetime（无时区）
    支持 datetime、date 对象，以及带时区的 datetime
    """
    if isinstance(dt, datetime):
        # 如果有时区信息，转换为 naive datetime
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt
    elif isinstance(dt, date):
        # date 对象转换为 datetime
        return datetime.combine(dt, datetime.min.time())
    return None


class PaperCollector:
    """论文收集器类，用于从 arxiv 搜索论文并插入数据库"""
    
    def __init__(self, db_path=None):
        """
        初始化论文收集器
        
        Args:
            db_path: 数据库路径，如果为 None 则使用配置文件中的路径
        """
        self.db_path = db_path or get_db_path()
        self.database = None
        self._init_database()
    
    def _init_database(self):
        """初始化数据库连接"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.database = Database(self.db_path)
        self.database.construct()
    
    def get_existing_arxiv_ids(self):
        """获取数据库中已存在的 arxiv_id 集合"""
        try:
            return set(self.database.get_arxiv_ids())
        except Exception as e:
            print(f"加载数据库信息时出错: {e}")
            return set()
    
    @staticmethod
    def _get_base_arxiv_id(arxiv_id):
        """
        获取基础 arxiv_id（移除版本号）
        例如：2401.12345v1 -> 2401.12345
        """
        if not arxiv_id:
            return None
        # 移除版本号部分（v1, v2等）
        return re.sub(r'v\d+$', '', arxiv_id)
    
    def _is_arxiv_id_exists(self, arxiv_id, existing_arxiv_ids):
        """
        检查 arxiv_id 是否已存在于数据库中（考虑版本号）
        
        如果数据库中已有相同基础 ID 的记录（无论是否有版本号），则认为已存在
        例如：如果数据库中已有 2401.12345 或 2401.12345v1，则 2401.12345v2 也会被认为已存在
        
        Args:
            arxiv_id: 要检查的 arxiv_id（可能带版本号）
            existing_arxiv_ids: 数据库中已存在的 arxiv_id 集合
        
        Returns:
            bool: 如果已存在返回 True，否则返回 False
        """
        if not arxiv_id or not existing_arxiv_ids:
            return False
        
        # 完全匹配
        if arxiv_id in existing_arxiv_ids:
            return True
        
        # 检查基础 ID 是否匹配（处理版本号差异）
        base_id = self._get_base_arxiv_id(arxiv_id)
        if not base_id:
            return False
        
        # 检查是否有相同基础 ID 的记录（无论版本号）
        for existing_id in existing_arxiv_ids:
            existing_base_id = self._get_base_arxiv_id(existing_id)
            if existing_base_id == base_id:
                return True
        
        return False
    
    def search_arxiv_papers(self, keywords, start_date=None, end_date=None, max_results=2000, existing_arxiv_ids=None):
        """
        搜索 arxiv 论文
        
        Args:
            keywords: 关键词列表
            start_date: 开始日期 (datetime 对象)
            end_date: 结束日期 (datetime 对象)
            max_results: 最大结果数
            existing_arxiv_ids: 数据库中已存在的 arxiv_id 集合，如果提供则跳过这些论文
        
        Returns:
            论文信息列表，每个元素包含：
            {
                "arxiv_id": "...",
                "paper_id": "...",
                "paper_url": "...",
                "date": "...",
                "full_name": "...",
                "abstract": "..."
            }
        """
        client = arxiv.Client()
        
        # 构建查询：关键词1 OR 关键词2 OR ...
        keyword_query = " OR ".join([f'"{kw}"' for kw in keywords])
        
        # 如果指定了日期范围，在查询中添加日期过滤
        # arXiv 查询语法支持 submittedDate:[YYYYMMDD TO YYYYMMDD]
        date_query = None
        if start_date and end_date:
            # 同时有开始和结束日期，使用单个日期范围查询
            start_date_str = start_date.strftime('%Y%m%d')
            end_date_str = end_date.strftime('%Y%m%d')
            date_query = f"submittedDate:[{start_date_str} TO {end_date_str}]"
        elif start_date:
            # 只有开始日期
            start_date_str = start_date.strftime('%Y%m%d')
            date_query = f"submittedDate:[{start_date_str} TO *]"
        elif end_date:
            # 只有结束日期
            end_date_str = end_date.strftime('%Y%m%d')
            date_query = f"submittedDate:[* TO {end_date_str}]"
        
        # 组合查询：如果有日期过滤，使用 AND 连接
        if date_query:
            query = f"({keyword_query}) AND ({date_query})"
        else:
            query = keyword_query
        
        print(f"\n搜索关键词: {', '.join(keywords)}")
        print(f"查询语句: {query}")
        if start_date:
            print(f"开始日期: {start_date.strftime('%Y-%m-%d')}")
        if end_date:
            print(f"结束日期: {end_date.strftime('%Y-%m-%d')}")
        print(f"最大结果数: {max_results}")
        if existing_arxiv_ids:
            print(f"数据库中已存在: {len(existing_arxiv_ids)} 篇论文，将自动跳过")
        
        papers = []
        seen_ids = set()  # 用于去重（本次搜索中的去重）
        total_found = 0  # 总共找到的论文数
        no_date = 0  # 没有发布日期信息的论文数
        skipped_existing = 0  # 因数据库中已存在而跳过的论文数
        
        try:
            # 使用 arxiv API 搜索，查询中已包含日期范围过滤
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            print("正在搜索...")
            
            # 遍历搜索结果（日期范围已在查询中过滤）
            for paper in client.results(search):
                # 提取 arxiv_id
                arxiv_id = paper.entry_id.split('/')[-1]
                
                # 去重（本次搜索中的去重）
                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)
                total_found += 1
                
                # 检查数据库中是否已存在（考虑版本号）
                if existing_arxiv_ids and self._is_arxiv_id_exists(arxiv_id, existing_arxiv_ids):
                    skipped_existing += 1
                    if skipped_existing <= 5:  # 只显示前5个被跳过的示例
                        print(f"  [跳过-已存在] {arxiv_id} - {paper.title[:60]}...")
                    continue
                
                # 处理发布日期（用于显示和验证）
                pub_date = None
                if paper.published:
                    pub_date = normalize_datetime(paper.published)
                    if not pub_date:
                        no_date += 1
                        # 如果查询中指定了日期范围但没有日期信息，跳过这篇论文
                        if start_date or end_date:
                            continue
                else:
                    no_date += 1
                    # 如果查询中指定了日期范围但没有日期信息，跳过这篇论文
                    if start_date or end_date:
                        continue
                
                # 验证日期范围（备用检查，以防查询中的日期过滤没有完全生效）
                if start_date or end_date:
                    if not pub_date:
                        continue
                    if start_date and pub_date < start_date:
                        continue
                    if end_date and pub_date > end_date:
                        continue
                
                # 从 arxiv_id 提取日期（格式：yyyyMM）
                date_str = Database._extract_date_from_arxiv_id(arxiv_id)
                
                # 构建论文信息
                paper_info = {
                    "arxiv_id": arxiv_id,
                    "paper_id": arxiv_id,  # 使用 arxiv_id 作为 paper_id
                    "paper_url": f"https://arxiv.org/abs/{arxiv_id}",
                    "date": date_str,
                    "full_name": paper.title,
                    "abstract": paper.summary
                }
                
                papers.append(paper_info)
                date_str_display = pub_date.strftime('%Y-%m-%d') if pub_date else 'N/A'
                print(f"  [✓] [{date_str_display}] {arxiv_id} - {paper.title[:80]}...")
            
            # 打印统计信息
            print(f"\n搜索统计:")
            print(f"  总共找到: {total_found} 篇论文（已在查询中按日期范围过滤）")
            print(f"  符合条件: {len(papers)} 篇")
            print(f"  数据库中已存在（已跳过）: {skipped_existing} 篇")
            print(f"  无发布日期信息: {no_date} 篇")
            print(f"\n共找到 {len(papers)} 篇论文（在日期范围内且数据库中不存在）")
            return papers
        
        except Exception as e:
            print(f"搜索出错: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def insert_papers(self, papers):
        """
        将论文插入数据库
        
        Args:
            papers: 论文信息列表
        
        Returns:
            bool: 是否成功插入
        """
        if not papers:
            return False
        
        # 准备数据格式（新格式：字典列表）
        data = []
        for paper in papers:
            data.append({
                "paper_id": paper["paper_id"],
                "arxiv_id": paper["arxiv_id"],
                "paper_url": paper["paper_url"],
                "date": paper["date"],
                "alias": None,
                "full_name": paper["full_name"],
                "abstract": paper["abstract"]
            })
        
        # 插入数据库
        try:
            self.database.insert_paper(data)
            return True
        except Exception as e:
            print(f"插入时出错: {e}")
            import traceback
            traceback.print_exc()
            return False


def print_papers(papers):
    """打印论文信息"""
    print("\n" + "="*80)
    print(f"找到 {len(papers)} 篇论文:")
    print("="*80)
    
    for i, paper in enumerate(papers, 1):
        print(f"\n[{i}] {paper['arxiv_id']}")
        print(f"    标题: {paper['full_name']}")
        print(f"    日期: {paper['date'] or 'N/A'}")
        print(f"    URL: {paper['paper_url']}")
        if paper['abstract']:
            abstract_preview = paper['abstract'][:200].replace('\n', ' ')
            print(f"    摘要: {abstract_preview}...")
        print("-" * 80)




def parse_date(date_str):
    """解析日期字符串，支持格式：YYYY-MM-DD 或 YYYYMM"""
    if not date_str:
        return None
    
    try:
        # 尝试 YYYY-MM-DD 格式
        if '-' in date_str:
            return datetime.strptime(date_str, '%Y-%m-%d')
        # 尝试 YYYYMM 格式
        elif len(date_str) == 6:
            return datetime.strptime(date_str, '%Y%m')
        else:
            raise ValueError(f"不支持的日期格式: {date_str}")
    except ValueError as e:
        print(f"日期解析错误: {e}")
        print("支持的格式: YYYY-MM-DD 或 YYYYMM")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='通过 arxiv API 搜索论文并插入数据库',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 搜索所有相关论文
  python paper_collector.py
  
  # 搜索指定日期范围的论文
  python paper_collector.py --start-date 2024-01-01 --end-date 2024-12-31
  
  # 使用 YYYYMM 格式
  python paper_collector.py --start-date 202401 --end-date 202412
  
  # 搜索过去7天的论文并自动插入数据库
  python paper_collector.py --days 7 --auto-inject-to-db
  
  # 搜索过去30天的论文（需要确认）
  python paper_collector.py --days 30
        """
    )
    
    parser.add_argument(
        '--start-date',
        type=str,
        help='开始日期 (格式: YYYY-MM-DD 或 YYYYMM)'
    )
    
    parser.add_argument(
        '--end-date',
        type=str,
        help='结束日期 (格式: YYYY-MM-DD 或 YYYYMM)'
    )
    
    parser.add_argument(
        '--max-results',
        type=int,
        default=2000,
        help='最大结果数 (默认: 2000)'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        default=None,
        help='数据库路径 (默认: 使用配置文件中的路径)'
    )
    
    parser.add_argument(
        '--insert',
        action='store_true',
        help='直接插入数据库，不进行确认（已废弃，请使用 --auto-inject-to-db）'
    )
    
    parser.add_argument(
        '--auto-inject-to-db',
        action='store_true',
        help='自动插入数据库，无需人工确认'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        help='指定过去多少天的时间范围（例如：--days 7 表示过去7天）'
    )
    
    args = parser.parse_args()
    
    # 处理日期范围
    current_date = datetime.now()
    
    # 如果指定了 --days，自动计算日期范围
    if args.days:
        if args.days <= 0:
            print(f"错误: --days 参数必须大于 0，当前值: {args.days}")
            return
        end_date = current_date
        start_date = current_date - timedelta(days=args.days)
        print(f"使用时间范围: 过去 {args.days} 天")
        print(f"  开始日期: {start_date.strftime('%Y-%m-%d')}")
        print(f"  结束日期: {end_date.strftime('%Y-%m-%d')}")
    else:
        # 解析手动指定的日期
        start_date = parse_date(args.start_date) if args.start_date else None
        end_date = parse_date(args.end_date) if args.end_date else None
        
        # 检查日期是否合理
        if start_date and start_date > current_date:
            print(f"警告: 开始日期 {start_date.strftime('%Y-%m-%d')} 是未来日期")
        if end_date and end_date > current_date:
            print(f"警告: 结束日期 {end_date.strftime('%Y-%m-%d')} 是未来日期")
    
    # 兼容旧的 --insert 参数
    auto_inject = args.auto_inject_to_db or args.insert
    
    # 创建论文收集器
    collector = PaperCollector(db_path=args.db_path if args.db_path else None)
    
    # 加载数据库中已存在的 arxiv_id
    existing_arxiv_ids = collector.get_existing_arxiv_ids()
    print(f"数据库中已存在 {len(existing_arxiv_ids)} 篇论文")
    
    # 搜索关键词
    keywords = [
        "3dgs",
        "world model",
        "3d gaussian splatting",
        "3d gaussian",
        "novel view synthesis",
        "gaussian splatting",
        "3D Gaussian Splatting",
        "3DGS",
        "3d generative",
        "3d generative model",
        "3d generation",
        "diffusion model",
        "flow model",
        "foundation model",
        "vla",
        "vlm",
        "reinforcement learning",
        "reconstruct",
        "3D scene geometry"
        "multi-view geometry",
    ]
    
    # 搜索论文
    papers = collector.search_arxiv_papers(
        keywords=keywords,
        start_date=start_date,
        end_date=end_date,
        max_results=args.max_results,
        existing_arxiv_ids=existing_arxiv_ids
    )
    
    if not papers:
        print("\n没有找到符合条件的论文")
        return
    
    # 打印论文信息
    print_papers(papers)
    
    # 确认是否插入数据库
    if auto_inject:
        print(f"\n正在自动插入到数据库 {collector.db_path}...")
        success = collector.insert_papers(papers)
        if success:
            print(f"成功插入/更新 {len(papers)} 条记录")
    else:
        print("\n" + "="*80)
        response = input(f"\n是否要将这 {len(papers)} 篇论文插入数据库? (yes/no): ").strip().lower()
        if response in ['yes', 'y', '是']:
            print(f"\n正在插入到数据库 {collector.db_path}...")
            success = collector.insert_papers(papers)
            if success:
                print(f"成功插入/更新 {len(papers)} 条记录")
        else:
            print("已取消插入操作")


if __name__ == '__main__':
    main()

