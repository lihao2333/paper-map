#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用论文 API 接口：根据是否有 arxiv_id 选择不同的处理方式
"""

from arxiv_api import ArxivApi
from typing import Optional

class PaperApi:
    """通用论文 API 接口"""
    
    def __init__(self):
        self._arxiv_api = ArxivApi()
    
    def get_abstract(self, paper_id: str, arxiv_id: Optional[str] = None, paper_url: Optional[str] = None) -> str:
        """
        获取论文摘要
        
        Args:
            paper_id: 论文 ID
            arxiv_id: arXiv ID（如果有）
            paper_url: 论文 URL
        
        Returns:
            论文摘要
        
        Raises:
            ValueError: 如果无法获取摘要
            NotImplementedError: 如果是不支持的来源类型
        """
        if arxiv_id:
            # arXiv 论文，使用 ArxivApi
            return self._arxiv_api.get_abstarct(arxiv_id)
        else:
            # 非 arXiv 论文，目前不支持自动获取摘要
            # 未来可以实现网页爬取或其他方式
            raise NotImplementedError(f"非 arXiv 论文的摘要获取尚未实现: {paper_url}")
    
    def get_pdf_url(self, paper_id: str, arxiv_id: Optional[str] = None, paper_url: Optional[str] = None) -> str:
        """
        获取 PDF URL
        
        Args:
            paper_id: 论文 ID
            arxiv_id: arXiv ID（如果有）
            paper_url: 论文 URL
        
        Returns:
            PDF URL
        """
        if arxiv_id:
            # arXiv 论文，使用 ArxivApi
            return self._arxiv_api.get_pdf_url(arxiv_id)
        else:
            # 非 arXiv 论文，返回原始 URL（假设就是 PDF 链接）
            # 或者可以尝试从 URL 推断 PDF 链接
            if paper_url and paper_url.endswith('.pdf'):
                return paper_url
            # 尝试将 URL 转换为 PDF 链接（某些网站支持）
            # 例如：https://example.com/paper -> https://example.com/paper.pdf
            if paper_url:
                return paper_url
            raise ValueError(f"无法获取 PDF URL: paper_id={paper_id}")
    
    def get_title(self, paper_id: str, arxiv_id: Optional[str] = None, paper_url: Optional[str] = None) -> str:
        """
        获取论文标题
        
        Args:
            paper_id: 论文 ID
            arxiv_id: arXiv ID（如果有）
            paper_url: 论文 URL
        
        Returns:
            论文标题
        
        Raises:
            ValueError: 如果无法获取标题
            NotImplementedError: 如果是不支持的来源类型
        """
        if arxiv_id:
            # arXiv 论文，使用 ArxivApi
            return self._arxiv_api.get_title(arxiv_id)
        else:
            # 非 arXiv 论文，目前不支持自动获取标题
            # 未来可以实现网页爬取或其他方式
            raise NotImplementedError(f"非 arXiv 论文的标题获取尚未实现: {paper_url}")
    
    def can_fetch_metadata(self, arxiv_id: Optional[str] = None) -> bool:
        """
        判断是否可以通过 API 获取元数据
        
        Args:
            arxiv_id: arXiv ID（如果有）
        
        Returns:
            True 如果可以获取元数据，否则 False
        """
        return arxiv_id is not None


if __name__ == "__main__":
    # 测试
    api = PaperApi()
    
    # 测试 arXiv 论文
    print("测试 arXiv 论文:")
    try:
        abstract = api.get_abstract("2401.12345", arxiv_id="2401.12345")
        print(f"摘要: {abstract[:100]}...")
    except Exception as e:
        print(f"错误: {e}")
    
    # 测试非 arXiv 论文
    print("\n测试非 arXiv 论文:")
    try:
        api.get_abstract("paper_abc123", arxiv_id=None, paper_url="https://example.com/paper")
    except NotImplementedError as e:
        print(f"预期错误（尚未实现）: {e}")



