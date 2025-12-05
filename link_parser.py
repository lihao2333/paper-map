#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
链接解析器：解析不同类型的论文链接，提取 paper_id、arxiv_id 和 paper_url
"""

import re
import hashlib
from urllib.parse import urlparse

class LinkParser:
    """解析不同类型的论文链接"""
    
    @staticmethod
    def parse(url: str) -> dict:
        """
        解析论文链接
        
        Args:
            url: 论文链接（可以是 arXiv URL、arXiv ID 或其他 URL）
        
        Returns:
            {
                'paper_id': '...',      # 对于 arXiv: arxiv_id, 对于其他: hash(url)
                'arxiv_id': '...' (如果是 arXiv 链接，否则为 None),
                'paper_url': '...',      # 标准化后的 URL
                'date': '...' (如果是 arXiv 链接，格式 yyyyMM，否则为 None)
            }
        
        Raises:
            ValueError: 如果 URL 格式无效
        """
        if not url or not url.strip():
            raise ValueError("URL 不能为空")
        
        url = url.strip()
        
        # 尝试提取 arXiv ID
        arxiv_id = LinkParser._extract_arxiv_id(url)
        
        if arxiv_id:
            # 是 arXiv 链接
            paper_id = arxiv_id
            paper_url = f"https://arxiv.org/abs/{arxiv_id}"
            date = LinkParser._extract_date_from_arxiv_id(arxiv_id)
            return {
                'paper_id': paper_id,
                'arxiv_id': arxiv_id,
                'paper_url': paper_url,
                'date': date
            }
        else:
            # 非 arXiv 链接
            # 标准化 URL（确保有协议）
            if not url.startswith(('http://', 'https://', 'file://')):
                paper_url = 'https://' + url
            else:
                paper_url = url
            
            # 使用 URL 的哈希值作为 paper_id（取前16个字符）
            paper_id = LinkParser._generate_paper_id(paper_url)
            
            return {
                'paper_id': paper_id,
                'arxiv_id': None,
                'paper_url': paper_url,
                'date': None
            }
    
    @staticmethod
    def _extract_date_from_arxiv_id(arxiv_id: str) -> str:
        """
        从 arxiv_id 提取日期，格式：yyyyMM
        例如：2401.12345 -> 202401, 2401.12345v1 -> 202401
        
        Args:
            arxiv_id: arXiv ID (格式：YYMM.NNNNN 或 YYMM.NNNNNvN)
        
        Returns:
            日期字符串 (格式：yyyyMM)，如果无法提取则返回 None
        """
        if not arxiv_id:
            return None
        
        # arxiv_id 格式：YYMM.NNNNN 或 YYMM.NNNNNvN
        # 需要先移除版本号（如果有）
        # 移除版本号部分（v1, v2等）
        arxiv_id_without_version = re.sub(r'v\d+$', '', arxiv_id)
        
        # 提取日期部分
        parts = arxiv_id_without_version.split('.')
        if len(parts) != 2:
            return None
        
        yymm = parts[0]
        if len(yymm) != 4:
            return None
        
        try:
            yy = int(yymm[:2])
            mm = yymm[2:]
            
            # 判断年份：00-30 认为是 2000-2030，31-99 认为是 1931-1999
            if yy <= 30:
                yyyy = 2000 + yy
            else:
                yyyy = 1900 + yy
            
            return f"{yyyy}{mm}"
        except (ValueError, IndexError):
            return None
    
    @staticmethod
    def _extract_arxiv_id(url: str) -> str:
        """
        从 URL 中提取 arXiv ID（包括版本号）
        
        支持的格式：
        - https://arxiv.org/abs/1234.5678
        - https://arxiv.org/abs/1234.5678v1
        - https://arxiv.org/pdf/1234.5678.pdf
        - https://arxiv.org/pdf/1234.5678v1.pdf
        - arxiv.org/abs/1234.5678
        - arxiv.org/abs/1234.5678v1
        - 1234.5678 (直接是 ID)
        - 1234.5678v1 (直接是 ID，带版本号)
        
        Returns:
            arXiv ID 字符串（包含版本号，如果有），如果不是 arXiv 链接则返回 None
        """
        if not url:
            return None
        
        # 匹配 arXiv ID 格式：YYYY.MMMMM 或 YYYY.MMMMMvN (例如：2401.12345 或 2401.12345v1)
        # 版本号是可选的，格式为 v 后跟数字
        arxiv_id_pattern = r'(\d{4}\.\d{4,5}(?:v\d+)?)'
        
        # 尝试从 URL 中提取
        match = re.search(arxiv_id_pattern, url)
        if match:
            arxiv_id = match.group(1)
            # 验证是否真的是 arXiv 链接（包含 arxiv.org 或者是纯 ID）
            # 纯 ID 格式：YYYY.MMMMM 或 YYYY.MMMMMvN
            if 'arxiv.org' in url.lower() or re.match(r'^\d{4}\.\d{4,5}(?:v\d+)?$', url.strip()):
                return arxiv_id
        
        return None
    
    @staticmethod
    def _generate_paper_id(url: str) -> str:
        """
        为非 arXiv 链接生成唯一的 paper_id
        
        Args:
            url: 论文 URL
        
        Returns:
            唯一的 paper_id（基于 URL 的哈希值）
        """
        # 使用 SHA256 哈希，取前16个字符
        hash_obj = hashlib.sha256(url.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()
        return f"paper_{hash_hex[:16]}"
    
    @staticmethod
    def is_arxiv_link(url: str) -> bool:
        """
        判断是否为 arXiv 链接
        
        Args:
            url: 论文链接
        
        Returns:
            True 如果是 arXiv 链接，否则 False
        """
        return LinkParser._extract_arxiv_id(url) is not None


if __name__ == "__main__":
    # 测试
    parser = LinkParser()
    
    test_cases = [
        "https://arxiv.org/abs/2401.12345",
        "https://arxiv.org/abs/2401.12345v1",
        "https://arxiv.org/pdf/2401.12345.pdf",
        "https://arxiv.org/pdf/2401.12345v1.pdf",
        "2401.12345",
        "2401.12345v1",
        "https://example.com/paper",
        "https://openreview.net/forum?id=xxx",
    ]
    
    print("测试链接解析器：")
    print("=" * 60)
    for url in test_cases:
        try:
            result = parser.parse(url)
            print(f"\n输入: {url}")
            print(f"  paper_id: {result['paper_id']}")
            print(f"  arxiv_id: {result['arxiv_id']}")
            print(f"  paper_url: {result['paper_url']}")
            print(f"  是 arXiv: {parser.is_arxiv_link(url)}")
        except Exception as e:
            print(f"\n输入: {url}")
            print(f"  错误: {e}")

