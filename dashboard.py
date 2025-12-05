import panel as pn
import pandas as pd
import json
import os
import re
import sys
import io
import html
import asyncio
from contextlib import redirect_stdout
from database import Database
from completer import Completer
from link_parser import LinkParser
from paper_collector import PaperCollector
from datetime import datetime, timedelta
import config

# 统一的 CSS 样式定义 - PaperMap 风格
# 注意：不使用 <style> 标签，因为会通过 pn.config.raw_css 注入
COMMON_CSS = f"""
/* 全局样式 */
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
    background-color: {config.BG_COLOR_LIGHT};
}}

/* 表格单元格样式 */
.tabulator-cell {{
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    padding: 8px 12px !important;
}}
.tabulator-cell a {{
    white-space: nowrap !important;
    color: {config.LINK_COLOR} !important;
    text-decoration: none !important;
    font-weight: 500 !important;
    transition: color 0.2s ease !important;
}}
.tabulator-cell a:hover {{
    color: {config.THEME_SECONDARY} !important;
    text-decoration: underline !important;
}}

/* 表头样式 */
.tabulator-header {{
    background-color: {config.BG_COLOR_LIGHTER} !important;
    border-bottom: 2px solid {config.BORDER_COLOR} !important;
}}
.tabulator-header .tabulator-col-title {{
    white-space: normal !important;
    line-height: 1.3 !important;
    font-weight: 600 !important;
    color: {config.TEXT_COLOR_PRIMARY} !important;
}}

/* 表格行样式 */
.tabulator-row {{
    transition: background-color 0.2s ease !important;
}}
.tabulator-row:hover {{
    background-color: {config.BG_COLOR_LIGHTER} !important;
}}

/* 工具提示样式 */
.custom-tooltip {{
    cursor: help !important;
}}

/* 论文列表样式 */
.paper-list {{
    margin-top: 20px;
    padding: 20px;
    background-color: {config.BG_COLOR_WHITE};
    border-radius: {config.BORDER_RADIUS_LARGE};
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}}
.paper-item {{
    padding: 12px 16px;
    margin: 8px 0;
    background-color: {config.BG_COLOR_WHITE};
    border-radius: {config.BORDER_RADIUS_MEDIUM};
    border-left: 4px solid {config.LINK_COLOR};
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
    transition: all 0.2s ease;
}}
.paper-item:hover {{
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    transform: translateY(-1px);
}}
.paper-item a {{
    color: {config.LINK_COLOR};
    text-decoration: none;
    font-weight: 500;
    transition: color 0.2s ease;
}}
.paper-item a:hover {{
    color: {config.THEME_SECONDARY};
    text-decoration: underline;
}}
.paper-summary {{
    color: {config.TEXT_COLOR_SECONDARY};
    font-size: 0.9em;
    margin-top: 8px;
    line-height: 1.5;
}}

/* 按钮样式增强 */
.bk-btn {{
    border-radius: {config.BORDER_RADIUS_MEDIUM} !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}}
.bk-btn:hover {{
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}}

/* 输入框样式 */
.bk-input {{
    border-radius: {config.BORDER_RADIUS_MEDIUM} !important;
    border: 1px solid {config.BORDER_COLOR} !important;
    transition: border-color 0.2s ease !important;
}}
.bk-input:focus {{
    border-color: {config.LINK_COLOR} !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important;
}}
"""

pn.extension('tabulator')

def get_css_pane():
    """返回统一的 CSS 样式面板
    
    使用每次创建新实例的方式，避免 ImportedStyleSheet 重复附加。
    虽然每次都会创建新的 HTML pane，但这是最安全的方法。
    """
    # 每次都创建新的 HTML pane，使用相同的 CSS 内容
    # Panel/Bokeh 会正确处理这些独立的 pane 对象
    css_html = f"<style>{COMMON_CSS}</style>"
    pane = pn.pane.HTML(css_html, sizing_mode='stretch_width', height=0, margin=0)
    # 设置一个属性来标识这是 CSS pane，避免被重复处理
    pane._is_css_pane = True
    return pane

def parse_paper_link(paper_link):
    """
    解析论文链接，返回 paper_id、arxiv_id 和 paper_url
    使用 LinkParser 进行解析
    """
    if not paper_link:
        return None
    
    try:
        parser = LinkParser()
        return parser.parse(paper_link.strip())
    except Exception as e:
        print(f"解析链接失败: {e}")
        return None

def generate_paper_link(arxiv_id, paper_url):
    """生成论文链接"""
    return f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else paper_url

def generate_tooltip(full_name, summary, company_names, university_names, tag_names=None, date=None, author_names=None, paper_id=None):
    """生成 tooltip HTML 属性"""
    tooltip_parts = []
    
    # 标题
    if full_name:
        tooltip_parts.append(f"📄 {html.escape(str(full_name))}")
    
    # 分隔线
    if tooltip_parts and (paper_id or author_names or date or summary or company_names or university_names or tag_names):
        tooltip_parts.append("─" * 40)
    
    # Paper ID（放在最前面）
    if paper_id:
        tooltip_parts.append(f"🆔 Paper ID: {html.escape(str(paper_id))}")
    
    # 作者信息（重要，放在前面）
    if author_names:
        authors_text = ", ".join(author_names)
        tooltip_parts.append(f"👤 作者: {html.escape(authors_text)}")
    
    # 日期
    if date:
        tooltip_parts.append(f"📅 日期: {html.escape(str(date))}")
    
    # 摘要/总结
    if summary:
        # 限制摘要长度，避免 tooltip 过长
        summary_text = html.escape(str(summary))
        if len(summary_text) > 300:
            summary_text = summary_text[:300] + "..."
        tooltip_parts.append(f"📝 摘要: {summary_text}")
    
    # 机构信息
    if company_names or university_names:
        tooltip_parts.append("─" * 40)
        if company_names:
            companies_text = ", ".join(company_names)
            tooltip_parts.append(f"🏢 公司: {html.escape(companies_text)}")
        if university_names:
            universities_text = ", ".join(university_names)
            tooltip_parts.append(f"🎓 高校: {html.escape(universities_text)}")
    
    # 标签
    if tag_names:
        tags_text = ", ".join(tag_names)
        tooltip_parts.append(f"🏷️ 标签: {html.escape(tags_text)}")
    
    # 使用换行符连接，HTML title 属性在某些浏览器中支持换行
    tooltip_text = "\n".join(tooltip_parts) if tooltip_parts else ""
    return f' title="{tooltip_text}"' if tooltip_text else ""

def generate_cell_content(alias, full_name, paper_link, tooltip_attr=""):
    """生成表格单元格 HTML 内容"""
    if not alias and not full_name:
        return ''
    
    display_text = alias if alias else full_name
    return f'<a href="{paper_link}" target="_blank" style="font-weight: bold; color: {config.LINK_COLOR_ALT}; text-decoration: none; white-space: nowrap;" class="custom-tooltip"{tooltip_attr}>{html.escape(display_text)}</a>'

def get_paper_hover_info(paper_id, paper_info_map, database, paper_data=None):
    """
    获取论文的 hover 信息（统一函数，避免重复代码）
    
    Args:
        paper_id: 论文 ID
        paper_info_map: 论文信息映射字典
        database: 数据库实例
        paper_data: 可选的论文数据字典（如果提供，优先使用）
    
    Returns:
        dict: 包含以下字段的字典
            - company_names: 公司名称列表
            - university_names: 高校名称列表
            - author_names: 作者名称列表
            - arxiv_id: arXiv ID
            - paper_url: 论文 URL
            - tag_names: 标签名称列表
            - date: 日期
            - full_name: 完整名称
            - summary: 摘要
    """
    # 优先使用 paper_data，否则从 paper_info_map 获取
    if paper_data:
        company_names = paper_data.get("company_names", [])
        university_names = paper_data.get("university_names", [])
        author_names = paper_data.get("author_names", [])
        arxiv_id = paper_data.get("arxiv_id")
        paper_url = paper_data.get("paper_url", "")
        date = paper_data.get("date", "")
        full_name = paper_data.get("full_name", "")
        summary = paper_data.get("summary", "")
    else:
        paper_info = paper_info_map.get(paper_id, {})
        company_names = paper_info.get("company_names", [])
        university_names = paper_info.get("university_names", [])
        author_names = paper_info.get("author_names", [])
        arxiv_id = paper_info.get("arxiv_id")
        paper_url = paper_info.get("paper_url", "")
        date = paper_info.get("date", "")
        full_name = paper_info.get("full_name", "")
        summary = paper_info.get("summary", "")
    
    # 如果 company_names 或 university_names 为空，尝试从数据库查询
    if not company_names or not university_names:
        try:
            db_paper_info = database.get_paper_info(paper_id=paper_id)
            if db_paper_info:
                # 如果 paper_info_map 中没有公司信息，使用数据库中的
                if not company_names and db_paper_info.get("company_names"):
                    company_names = db_paper_info.get("company_names", [])
                # 如果 paper_info_map 中没有高校信息，使用数据库中的
                if not university_names and db_paper_info.get("university_names"):
                    university_names = db_paper_info.get("university_names", [])
                # 如果 paper_info_map 中没有作者信息，使用数据库中的
                if not author_names and db_paper_info.get("author_names"):
                    author_names = db_paper_info.get("author_names", [])
                # 如果 paper_info_map 中没有其他信息，使用数据库中的
                if not arxiv_id and db_paper_info.get("arxiv_id"):
                    arxiv_id = db_paper_info.get("arxiv_id")
                if not paper_url and db_paper_info.get("paper_url"):
                    paper_url = db_paper_info.get("paper_url", "")
                if not date and db_paper_info.get("date"):
                    date = db_paper_info.get("date", "")
                if not full_name and db_paper_info.get("full_name"):
                    full_name = db_paper_info.get("full_name", "")
                if not summary and db_paper_info.get("summary"):
                    summary = db_paper_info.get("summary", "")
        except Exception as e:
            # 如果查询失败，使用已有的信息
            pass
    
    # 获取论文的标签
    try:
        paper_tags = database.get_paper_tags(paper_id)
        tag_names = [tag["tag_name"] for tag in paper_tags]
    except:
        tag_names = []
    
    return {
        "paper_id": paper_id,
        "company_names": company_names,
        "university_names": university_names,
        "author_names": author_names,
        "arxiv_id": arxiv_id,
        "paper_url": paper_url,
        "tag_names": tag_names,
        "date": date,
        "full_name": full_name,
        "summary": summary
    }

# ==================== 全局数据缓存 ====================
# 用于在不同 session 之间共享数据，避免重复加载
_global_data_cache = {
    'data': None,
    'df': None,
    'company_df': None,
    'university_df': None,
    'author_df': None,
    'paper_info_map': None,
    'data_loaded': False,
    'db_path': None,
    'cache_timestamp': None,  # 数据加载时间戳
    'db_mtime': None  # 数据库文件修改时间戳，用于判断是否需要刷新
}
import threading
_cache_lock = threading.Lock()  # 用于线程安全的缓存访问

def _get_cache_key(db_path):
    """获取缓存键（基于数据库路径）"""
    return db_path or config.get_db_path()

def _get_db_mtime(db_path):
    """获取数据库文件的修改时间"""
    try:
        if os.path.exists(db_path):
            return os.path.getmtime(db_path)
    except:
        pass
    return None

def _is_cache_valid(db_path):
    """检查缓存是否仍然有效（数据库文件未被修改）"""
    cache_key = _get_cache_key(db_path)
    with _cache_lock:
        if (_global_data_cache['data_loaded'] and 
            _global_data_cache['db_path'] == cache_key and
            _global_data_cache['data'] is not None):
            # 检查数据库文件修改时间
            current_mtime = _get_db_mtime(db_path)
            cached_mtime = _global_data_cache.get('db_mtime')
            # 如果修改时间相同，缓存仍然有效
            if current_mtime is not None and cached_mtime is not None:
                return abs(current_mtime - cached_mtime) < 1.0  # 允许1秒误差
    return False

def _clear_global_cache(db_path=None):
    """清除全局缓存"""
    cache_key = _get_cache_key(db_path)
    with _cache_lock:
        if _global_data_cache['db_path'] == cache_key:
            _global_data_cache['data'] = None
            _global_data_cache['df'] = None
            _global_data_cache['company_df'] = None
            _global_data_cache['university_df'] = None
            _global_data_cache['author_df'] = None
            _global_data_cache['paper_info_map'] = None
            _global_data_cache['data_loaded'] = False
            _global_data_cache['cache_timestamp'] = None
            _global_data_cache['db_mtime'] = None

class PaperDashboard:
    def __init__(self, db_path=None, cache_path=None):
        # 使用配置文件中的默认路径，如果未提供则使用配置
        self.db_path = db_path or config.get_db_path()
        self.database = Database(self.db_path)
        self.completer = Completer(cache_path or config.get_cache_path(), self.database)
        self.data = None
        self.df = None
        self.company_df = None
        self.university_df = None
        self.author_df = None
        self.paper_info_map = {}  # 初始化 paper_info_map，避免访问时出错
        self.group_by_date = True  # 是否按日期聚合相同的工作（默认开启）
        self._data_loaded = False  # 标记数据是否已加载
        # 延迟加载：不在初始化时加载数据，而是在首次需要时加载
        
    def load_data(self):
        """从数据库加载数据（延迟加载，使用全局缓存共享数据）"""
        # 如果数据已加载，直接返回
        if self._data_loaded:
            return
        
        cache_key = _get_cache_key(self.db_path)
        
        # 检查全局缓存是否有效（使用数据库修改时间）
        if _is_cache_valid(self.db_path):
            # 从缓存复制数据（避免引用问题）
            with _cache_lock:
                self.data = _global_data_cache['data']
                self.df = _global_data_cache['df'].copy() if _global_data_cache['df'] is not None else None
                self.company_df = _global_data_cache['company_df'].copy() if _global_data_cache['company_df'] is not None else None
                self.university_df = _global_data_cache['university_df'].copy() if _global_data_cache['university_df'] is not None else None
                self.author_df = _global_data_cache['author_df'].copy() if _global_data_cache['author_df'] is not None else None
                self.paper_info_map = _global_data_cache['paper_info_map'].copy() if _global_data_cache['paper_info_map'] is not None else {}
            self._data_loaded = True
            return
        
        # 缓存不存在或需要刷新，从数据库加载
        # 缓存不存在或需要刷新，从数据库加载
        self.data = self.database.get_all_papers_with_details()
        # 初始化 paper_info_map（将在后面填充，但这里先初始化避免错误）
        self.paper_info_map = {}
        # 转换为 DataFrame
        records = []
        for paper in self.data:
            paper_id = paper["paper_id"]
            arxiv_id = paper.get("arxiv_id")
            paper_url = paper["paper_url"]
            date = paper.get("date")
            alias = paper["alias"] or ""
            full_name = paper["full_name"] or ""
            abstract = paper["abstract"] or ""
            summary = paper.get("summary") or ""
            abstract_preview = abstract[:200] + "..." if abstract and len(abstract) > 200 else abstract
            
            # 生成论文链接
            paper_link = generate_paper_link(arxiv_id, paper_url)
            
            # 获取 hover 信息（传递 paper 作为 paper_data，优先使用）
            hover_info = get_paper_hover_info(paper_id, self.paper_info_map, self.database, paper)
            
            # 生成 tooltip
            title_attr = generate_tooltip(
                hover_info["full_name"] or full_name,
                hover_info["summary"] or summary,
                hover_info["company_names"],
                hover_info["university_names"],
                hover_info["tag_names"],
                hover_info["date"],
                hover_info["author_names"],
                hover_info["paper_id"]
            )
            
            # 将 Alias 转换为超链接，添加 hover 功能
            alias_link = generate_cell_content(alias, None, paper_link, title_attr) if alias else ""
            
            # 将 Full Name 转换为超链接
            full_name_link = f'<a href="{paper_link}" target="_blank">{full_name}</a>' if full_name else ""
            
            # 显示 ID：如果有 arxiv_id 显示 arxiv_id，否则显示 paper_id
            display_id = arxiv_id if arxiv_id else paper_id
            
            # 创建 Paper Link 超链接
            paper_link_html = f'<a href="{paper_link}" target="_blank" style="color: #0066cc; text-decoration: underline;">{paper_link}</a>' if paper_link else ""
            
            # 获取论文的标签
            paper_tags = self.database.get_paper_tags(paper_id)
            tag_names = [tag["tag_name"] for tag in paper_tags]
            tags_display = ", ".join(tag_names) if tag_names else ""
            
            records.append({
                "Paper ID": display_id,
                "Paper ID_original": paper_id,  # 保存原始 paper_id
                "Date": date or "",
                "Paper Link": paper_link_html,
                "Paper Link_original": paper_link,  # 保存原始数据用于搜索
                "Alias": alias_link,
                "Alias_original": alias,  # 保存原始数据用于搜索
                "Full Name": full_name_link,
                "Full Name_original": full_name,  # 保存原始数据用于搜索
                "Abstract": abstract_preview,
                "Summary": summary,
                "Authors": ", ".join(paper.get("author_names", [])) if paper.get("author_names") else "",
                "Companies": ", ".join(paper["company_names"]) if paper["company_names"] else "",
                "Universities": ", ".join(paper["university_names"]) if paper["university_names"] else "",
                "Tags": tags_display,
                # Tags_Button 列已移除，不再在论文列表中显示
            })
        self.df = pd.DataFrame(records)
        
        # 创建论文信息映射（用于 hover 显示公司和高校信息）
        self.paper_info_map = {}
        for paper in self.data:
            paper_id = paper["paper_id"]
            self.paper_info_map[paper_id] = {
                "company_names": paper.get("company_names", []),
                "university_names": paper.get("university_names", []),
                "author_names": paper.get("author_names", []),
                "arxiv_id": paper.get("arxiv_id"),
                "paper_url": paper["paper_url"],
                "date": paper.get("date", ""),
                "full_name": paper.get("full_name", ""),
                "summary": paper.get("summary", "")
            }
        
        # 加载公司-论文矩阵数据
        self.load_company_data()
        
        # 加载高校-论文矩阵数据
        self.load_university_data()
        
        # 加载作者-论文矩阵数据
        self.load_author_data()
        
        # 保存到全局缓存（供其他 session 使用）
        import time
        db_mtime = _get_db_mtime(self.db_path)
        with _cache_lock:
            _global_data_cache['data'] = self.data
            _global_data_cache['df'] = self.df
            _global_data_cache['company_df'] = self.company_df
            _global_data_cache['university_df'] = self.university_df
            _global_data_cache['author_df'] = self.author_df
            _global_data_cache['paper_info_map'] = self.paper_info_map
            _global_data_cache['data_loaded'] = True
            _global_data_cache['db_path'] = cache_key
            _global_data_cache['cache_timestamp'] = time.time()
            _global_data_cache['db_mtime'] = db_mtime
        
        # 标记数据已加载
        self._data_loaded = True
    
    def load_company_data(self):
        """加载车企-论文矩阵数据（只包含：蔚来、小鹏、理想、小米、华为、特斯拉）"""
        company_data = self.database.get_car_company_paper_matrix()
        if not company_data:
            self.company_df = pd.DataFrame()
            return
        
        # 加载配置文件以确定列顺序
        config_path = os.path.join(os.path.dirname(__file__), 'car_companies_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                company_mapping = json.load(f)
            # 获取配置文件中的顺序，过滤掉注释字段
            company_order = [key for key in company_mapping.keys() if not key.startswith('_')]
        else:
            company_order = None
        
        # 创建透视表：横轴是公司名称，纵轴是 paper_id，cell 包含 alias 和 summary
        df_raw = pd.DataFrame(company_data)
        if len(df_raw) > 0:
            # 创建一个包含 alias 和 summary 的组合值用于 pivot
            # 先创建两个独立的 pivot table
            alias_df = df_raw.pivot_table(
                index='paper_id',
                columns='company_name',
                values='alias',
                aggfunc='first',
                fill_value=''
            )
            summary_df = df_raw.pivot_table(
                index='paper_id',
                columns='company_name',
                values='summary',
                aggfunc='first',
                fill_value=''
            )
            full_name_df = df_raw.pivot_table(
                index='paper_id',
                columns='company_name',
                values='full_name',
                aggfunc='first',
                fill_value=''
            )
            
            # 重置索引，使 paper_id 成为普通列
            alias_df.reset_index(inplace=True)
            summary_df.reset_index(inplace=True)
            full_name_df.reset_index(inplace=True)
            
            # 从原始数据获取每个 paper_id 的 date 和 arxiv_id（每个 paper_id 只取一次）
            paper_info_map = {}
            for _, row in df_raw.iterrows():
                paper_id = row['paper_id']
                if paper_id not in paper_info_map:
                    paper_info_map[paper_id] = {
                        'date': row.get('date', '') or '',
                        'arxiv_id': row.get('arxiv_id', '') or ''
                    }
            
            # 保存原始数据（用于切换折行模式时重新生成）
            self.company_alias_df = alias_df.copy()
            self.company_summary_df = summary_df.copy()
            self.company_full_name_df = full_name_df.copy()
            
            # 创建合并的 DataFrame，包含 paper_id、date、arxiv_id 和所有公司列
            self.company_df = alias_df[['paper_id']].copy()
            self.company_df['date'] = self.company_df['paper_id'].map(lambda x: paper_info_map.get(x, {}).get('date', ''))
            self.company_df['arxiv_id'] = self.company_df['paper_id'].map(lambda x: paper_info_map.get(x, {}).get('arxiv_id', ''))
            
            # 遍历所有公司列，组合 alias（超链接）和 summary
            for col in alias_df.columns:
                if col != 'paper_id':
                    # 获取该列的 alias、summary 和 full_name
                    alias_values = alias_df[col]
                    summary_values = summary_df[col]
                    full_name_values = full_name_df[col]
                    paper_ids = alias_df['paper_id']
                    
                    # 创建组合的 HTML 内容（使用默认的折行模式）
                    combined_values = []
                    for paper_id, alias, summary, full_name in zip(paper_ids, alias_values, summary_values, full_name_values):
                        if alias:  # 如果有 alias
                            # 获取 hover 信息
                            hover_info = get_paper_hover_info(paper_id, self.paper_info_map, self.database)
                            
                            # 生成链接和 tooltip
                            paper_link = generate_paper_link(hover_info["arxiv_id"], hover_info["paper_url"])
                            title_attr = generate_tooltip(
                                hover_info["full_name"] or full_name,
                                hover_info["summary"] or summary,
                                hover_info["company_names"],
                                hover_info["university_names"],
                                hover_info["tag_names"],
                                hover_info["date"],
                                hover_info["author_names"],
                                hover_info["paper_id"]
                            )
                            
                            # 生成单元格内容
                            cell_content = generate_cell_content(alias, None, paper_link, title_attr)
                        else:
                            cell_content = ''
                        combined_values.append(cell_content)
                    
                    self.company_df[col] = combined_values
            
            # 按照字母顺序重新排列公司列
            # 确保 paper_id 在第一列，date 和 arxiv_id 在固定位置（如果存在）
            other_cols = [col for col in self.company_df.columns if col not in ['paper_id', 'date', 'arxiv_id']]
            # 按照字母顺序排序公司列
            sorted_cols = sorted(other_cols)
            # 重新排列：paper_id + date + arxiv_id + 按字母顺序排序的公司列
            new_column_order = ['paper_id']
            if 'date' in self.company_df.columns:
                new_column_order.append('date')
            if 'arxiv_id' in self.company_df.columns:
                new_column_order.append('arxiv_id')
            new_column_order.extend(sorted_cols)
            self.company_df = self.company_df[new_column_order]
            
            # 同时更新 company_alias_df、company_summary_df 和 company_full_name_df 的列顺序
            # 只对非 paper_id 的列进行排序
            alias_cols = [col for col in self.company_alias_df.columns if col != 'paper_id']
            sorted_alias_cols = sorted(alias_cols)
            alias_new_order = ['paper_id'] + sorted_alias_cols
            self.company_alias_df = self.company_alias_df[alias_new_order]
            self.company_summary_df = self.company_summary_df[alias_new_order]
            self.company_full_name_df = self.company_full_name_df[alias_new_order]
            
            # 按 date 倒序排序，如果 date 相同就按照 paper_id 倒序排序
            self.company_df = self.company_df.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
        else:
            self.company_df = pd.DataFrame()
    
    def create_author_table(self):
        """创建关注作者工作矩阵表格"""
        if self.author_df is None or len(self.author_df) == 0:
            return pn.pane.Str("暂无作者数据", styles={"font-size": "16px", "padding": "20px"})
        
        # 从原始数据重新生成，只显示 alias
        if hasattr(self, 'author_alias_df') and hasattr(self, 'author_summary_df'):
            df_display = self.author_alias_df[['paper_id']].copy()
            # 添加 date 列
            df_display['date'] = self.author_df['date']
            for col in self.author_alias_df.columns:
                if col != 'paper_id':
                    alias_values = self.author_alias_df[col]
                    paper_ids = self.author_alias_df['paper_id']
                    # 只创建 alias 超链接，添加 full_name、summary、公司和高校信息到 title
                    summary_values = self.author_summary_df[col]
                    full_name_values = self.author_full_name_df[col]
                    cell_values = []
                    for paper_id, alias, summary, full_name in zip(paper_ids, alias_values, summary_values, full_name_values):
                        if alias:
                            # 获取 hover 信息
                            hover_info = get_paper_hover_info(paper_id, self.paper_info_map, self.database)
                            
                            # 生成链接和 tooltip
                            paper_link = generate_paper_link(hover_info["arxiv_id"], hover_info["paper_url"])
                            title_attr = generate_tooltip(
                                hover_info["full_name"] or full_name,
                                hover_info["summary"] or summary,
                                hover_info["company_names"],
                                hover_info["university_names"],
                                hover_info["tag_names"],
                                hover_info["date"],
                                hover_info["author_names"],
                                hover_info["paper_id"]
                            )
                            
                            # 生成单元格内容
                            cell_values.append(generate_cell_content(alias, None, paper_link, title_attr))
                        else:
                            cell_values.append('')
                    df_display[col] = cell_values
            # 按 date 倒序排序，如果 date 相同就按照 paper_id 倒序排序
            df_sorted = df_display.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
        else:
            # 如果没有原始数据，使用现有数据
            df_sorted = self.author_df.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
        
        # 如果启用了聚合模式，将相同 date 的工作合并为一行
        if self.group_by_date and 'date' in df_sorted.columns:
            # 按 date 分组
            grouped = df_sorted.groupby('date', dropna=False)
            merged_rows = []
            
            for date, group in grouped:
                if pd.isna(date) or date == '':
                    # 对于空日期，保持原样
                    merged_rows.extend(group.to_dict('records'))
                else:
                    # 合并相同日期的行
                    merged_row = {'date': date}
                    
                    # 对于每个列，合并内容
                    for col in df_sorted.columns:
                        if col == 'date':
                            continue
                        
                        # 如果是 paper_id 列，在聚合模式下显示数量
                        if col == 'paper_id':
                            # 收集该列的所有非空值（去重）
                            unique_values = set()
                            for _, row in group.iterrows():
                                val = row[col]
                                if pd.notna(val) and str(val).strip():
                                    unique_values.add(str(val))
                            # 显示 paper 数量
                            merged_row[col] = str(len(unique_values))
                        else:
                            # 收集该列的所有非空值
                            values = []
                            for _, row in group.iterrows():
                                val = row[col]
                                if pd.notna(val) and str(val).strip():
                                    values.append(str(val))
                            
                            # 如果有多个值，用 <br> 连接；如果只有一个值，直接使用
                            if len(values) > 1:
                                merged_row[col] = '<br>'.join(values)
                            elif len(values) == 1:
                                merged_row[col] = values[0]
                            else:
                                merged_row[col] = ''
                    
                    merged_rows.append(merged_row)
            
            # 重新创建 DataFrame
            df_sorted = pd.DataFrame(merged_rows)
            
            # 重新排序（按 date 倒序）
            if len(df_sorted) > 0:
                df_sorted = df_sorted.sort_values('date', ascending=False, na_position='last').copy()
        
        # 重新排列列顺序：paper_id, date, ...（其他列），排除 arxiv_id
        cols = list(df_sorted.columns)
        if 'date' in cols:
            cols.remove('date')
            cols.remove('paper_id')
        if 'arxiv_id' in cols:
            cols.remove('arxiv_id')
        new_cols = ['paper_id', 'date'] + cols
        df_sorted = df_sorted[new_cols]
        
        # 为所有作者列创建 HTML formatter（除了 paper_id、date 和 arxiv_id）
        formatters = {}
        for col in df_sorted.columns:
            if col != 'paper_id' and col != 'date' and col != 'arxiv_id':
                formatters[col] = {'type': 'html'}
        
        # 创建列配置
        column_configs = []
        for col in df_sorted.columns:
            if col == 'paper_id':
                column_configs.append({
                    'field': col,
                    'width': 120,
                    'frozen': True,
                    'headerSort': True,
                    'resizable': True,
                })
            elif col == 'date':
                column_configs.append({
                    'field': col,
                    'width': 80,
                    'frozen': True,
                    'headerSort': True,
                    'resizable': True,
                })
            else:
                column_configs.append({
                    'field': col,
                    'width': 120,
                    'minWidth': 80,
                    'headerSort': True,
                    'resizable': True,
                    'formatter': 'html',
                })
        
        # 创建表格，固定前两列（paper_id 和 date）
        table = pn.widgets.Tabulator(
            df_sorted,
            pagination='remote',
            page_size=200,
            sizing_mode='stretch_width',
            height=config.TABLE_HEIGHT_DEFAULT,
            selectable=False,
            show_index=False,
            layout='fit_data_stretch',
            theme='bootstrap5',
            styles={
                'table': {'font-size': '12px'},
            },
            configuration={
                'columns': column_configs,
                'frozenColumns': 2,  # 冻结前两列
                'initialSort': [{'column': 'date', 'dir': 'desc'}],
                'resizableColumns': True,
                'autoResize': True,
            }
        )
        
        return table
    
    def create_table(self, use_grouping=None):
        """创建数据表格
        Args:
            use_grouping: 是否使用聚合模式。如果为 None，则使用 self.group_by_date；如果为 False，则禁用聚合
        """
        if self.df is None or len(self.df) == 0:
            return pn.pane.Str("暂无数据", styles={"font-size": "16px", "padding": "20px"})
        
        # 按 Date 倒序排序（如果 Date 为空则按 Paper ID）
        if 'Date' in self.df.columns:
            df_sorted = self.df.sort_values(['Date', 'Paper ID'], ascending=[False, False], na_position='last').copy()
        else:
            df_sorted = self.df.sort_values('Paper ID', ascending=False).copy()
        
        # 只显示需要的列（排除辅助列）
        # 列顺序：Paper ID, Date, Paper Link, Alias, Full Name, Authors, Companies, Universities, Tags, Abstract, Summary
        display_cols = ["Paper ID", "Date", "Paper Link", "Alias", "Full Name", "Authors", "Companies", "Universities", "Tags", "Abstract", "Summary"]
        df_display = df_sorted[display_cols].copy()
        
        # 确定是否使用聚合模式
        should_group = self.group_by_date if use_grouping is None else use_grouping
        
        # 如果启用了聚合模式，将相同 Date 的工作合并为一行
        if should_group and 'Date' in df_display.columns:
            # 按 Date 分组
            grouped = df_display.groupby('Date', dropna=False)
            merged_rows = []
            
            for date, group in grouped:
                if pd.isna(date) or date == '':
                    # 对于空日期，保持原样
                    merged_rows.extend(group.to_dict('records'))
                else:
                    # 合并相同日期的行
                    merged_row = {'Date': date}
                    
                    # 对于每个列，合并内容
                    for col in display_cols:
                        if col == 'Date':
                            continue
                        
                        # 收集该列的所有非空值
                        values = []
                        for _, row in group.iterrows():
                            val = row[col]
                            if pd.notna(val) and str(val).strip():
                                values.append(str(val))
                        
                        # 如果有多个值，用 <br> 连接；如果只有一个值，直接使用
                        if len(values) > 1:
                            merged_row[col] = '<br>'.join(values)
                        elif len(values) == 1:
                            merged_row[col] = values[0]
                        else:
                            merged_row[col] = ''
                    
                    merged_rows.append(merged_row)
            
            # 重新创建 DataFrame
            df_display = pd.DataFrame(merged_rows)
            
            # 重新排序（按 Date 倒序）
            if len(df_display) > 0:
                df_display = df_display.sort_values('Date', ascending=False, na_position='last').copy()
        
        # 创建表格，支持搜索和排序
        table = pn.widgets.Tabulator(
            df_display,
            pagination='remote',
            page_size=200,
            sizing_mode='stretch_width',
            height=config.TABLE_HEIGHT_DEFAULT,
            selectable=False,
            show_index=False,
            layout='fit_data_stretch',
            theme='bootstrap5',
            styles={
                'table': {'font-size': '12px'},
            },
            formatters={
                'Paper Link': {'type': 'html'},
                'Alias': {'type': 'html'},
                'Full Name': {'type': 'html'},
                'Companies': {'type': 'html'},
                'Universities': {'type': 'html'},
                'Tags': {'type': 'html'},
                'Abstract': {'type': 'textarea', 'maxWidth': 300},
                'Summary': {'type': 'textarea', 'maxWidth': 400},
            }
        )
        
        # 保存表格引用以便后续使用
        self.table = table
        
        return table
    
    def load_university_data(self):
        """加载高校-论文矩阵数据"""
        university_data = self.database.get_university_paper_matrix()
        if not university_data:
            self.university_df = pd.DataFrame()
            return
        
        # 加载配置文件以确定列顺序
        config_path = os.path.join(os.path.dirname(__file__), 'universities_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                university_mapping = json.load(f)
            # 获取配置文件中的顺序，过滤掉注释字段
            university_order = [key for key in university_mapping.keys() if not key.startswith('_')]
        else:
            university_order = None
        
        # 创建透视表：横轴是高校名称，纵轴是 paper_id，cell 包含 alias
        df_raw = pd.DataFrame(university_data)
        if len(df_raw) > 0:
            # 创建两个独立的 pivot table
            alias_df = df_raw.pivot_table(
                index='paper_id',
                columns='university_name',
                values='alias',
                aggfunc='first',
                fill_value=''
            )
            summary_df = df_raw.pivot_table(
                index='paper_id',
                columns='university_name',
                values='summary',
                aggfunc='first',
                fill_value=''
            )
            full_name_df = df_raw.pivot_table(
                index='paper_id',
                columns='university_name',
                values='full_name',
                aggfunc='first',
                fill_value=''
            )
            
            # 重置索引，使 paper_id 成为普通列
            alias_df.reset_index(inplace=True)
            summary_df.reset_index(inplace=True)
            full_name_df.reset_index(inplace=True)
            
            # 从原始数据获取每个 paper_id 的 date 和 arxiv_id（每个 paper_id 只取一次）
            paper_info_map = {}
            for _, row in df_raw.iterrows():
                paper_id = row['paper_id']
                if paper_id not in paper_info_map:
                    paper_info_map[paper_id] = {
                        'date': row.get('date', '') or '',
                        'arxiv_id': row.get('arxiv_id', '') or ''
                    }
            
            # 保存原始数据（用于 hover 显示）
            self.university_alias_df = alias_df.copy()
            self.university_summary_df = summary_df.copy()
            self.university_full_name_df = full_name_df.copy()
            
            # 创建合并的 DataFrame，包含 paper_id、date、arxiv_id 和所有高校列
            self.university_df = alias_df[['paper_id']].copy()
            self.university_df['date'] = self.university_df['paper_id'].map(lambda x: paper_info_map.get(x, {}).get('date', ''))
            self.university_df['arxiv_id'] = self.university_df['paper_id'].map(lambda x: paper_info_map.get(x, {}).get('arxiv_id', ''))
            
            # 遍历所有高校列，组合 alias（超链接）
            for col in alias_df.columns:
                if col != 'paper_id':
                    # 获取该列的 alias、summary 和 full_name
                    alias_values = alias_df[col]
                    summary_values = summary_df[col]
                    full_name_values = full_name_df[col]
                    paper_ids = alias_df['paper_id']
                    
                    # 创建 HTML 内容：只显示 alias，hover 显示 full_name 和 summary
                    combined_values = []
                    for paper_id, alias, summary, full_name in zip(paper_ids, alias_values, summary_values, full_name_values):
                        if alias:  # 如果有 alias
                            # 获取 hover 信息
                            hover_info = get_paper_hover_info(paper_id, self.paper_info_map, self.database)
                            
                            # 生成链接和 tooltip
                            paper_link = generate_paper_link(hover_info["arxiv_id"], hover_info["paper_url"])
                            title_attr = generate_tooltip(
                                hover_info["full_name"] or full_name,
                                hover_info["summary"] or summary,
                                hover_info["company_names"],
                                hover_info["university_names"],
                                hover_info["tag_names"],
                                hover_info["date"],
                                hover_info["author_names"],
                                hover_info["paper_id"]
                            )
                            
                            # 生成单元格内容
                            cell_content = generate_cell_content(alias, None, paper_link, title_attr)
                        else:
                            cell_content = ''
                        combined_values.append(cell_content)
                    
                    self.university_df[col] = combined_values
            
            # 按照配置文件中的顺序重新排列列（高校）
            if university_order:
                # 确保 paper_id 在第一列
                other_cols = [col for col in self.university_df.columns if col != 'paper_id']
                # 按照配置文件的顺序排列，只包含存在的列
                ordered_cols = [col for col in university_order if col in other_cols]
                # 添加不在配置文件中的其他列
                remaining_cols = [col for col in other_cols if col not in ordered_cols]
                # 重新排列：paper_id + 有序的高校列 + 其他列
                new_column_order = ['paper_id'] + ordered_cols + remaining_cols
                self.university_df = self.university_df[new_column_order]
            
            # 按 date 倒序排序，如果 date 相同就按照 paper_id 倒序排序
            self.university_df = self.university_df.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
        else:
            self.university_df = pd.DataFrame()
    
    def load_author_data(self):
        """加载关注作者-论文矩阵数据"""
        author_data = self.database.get_watched_author_paper_matrix()
        if not author_data:
            self.author_df = pd.DataFrame()
            return
        
        # 创建透视表：横轴是作者名称，纵轴是 paper_id，cell 包含 alias 和 summary
        df_raw = pd.DataFrame(author_data)
        if len(df_raw) > 0:
            # 创建三个独立的 pivot table
            alias_df = df_raw.pivot_table(
                index='paper_id',
                columns='author_name',
                values='alias',
                aggfunc='first',
                fill_value=''
            )
            summary_df = df_raw.pivot_table(
                index='paper_id',
                columns='author_name',
                values='summary',
                aggfunc='first',
                fill_value=''
            )
            full_name_df = df_raw.pivot_table(
                index='paper_id',
                columns='author_name',
                values='full_name',
                aggfunc='first',
                fill_value=''
            )
            
            # 重置索引，使 paper_id 成为普通列
            alias_df.reset_index(inplace=True)
            summary_df.reset_index(inplace=True)
            full_name_df.reset_index(inplace=True)
            
            # 从原始数据获取每个 paper_id 的 date 和 arxiv_id
            paper_info_map = {}
            for _, row in df_raw.iterrows():
                paper_id = row['paper_id']
                if paper_id not in paper_info_map:
                    paper_info_map[paper_id] = {
                        'date': row.get('date', '') or '',
                        'arxiv_id': row.get('arxiv_id', '') or ''
                    }
            
            # 保存原始数据（用于切换折行模式时重新生成）
            self.author_alias_df = alias_df.copy()
            self.author_summary_df = summary_df.copy()
            self.author_full_name_df = full_name_df.copy()
            
            # 创建合并的 DataFrame，包含 paper_id、date、arxiv_id 和所有作者列
            self.author_df = alias_df[['paper_id']].copy()
            self.author_df['date'] = self.author_df['paper_id'].map(lambda x: paper_info_map.get(x, {}).get('date', ''))
            self.author_df['arxiv_id'] = self.author_df['paper_id'].map(lambda x: paper_info_map.get(x, {}).get('arxiv_id', ''))
            
            # 遍历所有作者列，组合 alias（超链接）和 summary
            for col in alias_df.columns:
                if col != 'paper_id':
                    # 获取该列的 alias、summary 和 full_name
                    alias_values = alias_df[col]
                    summary_values = summary_df[col]
                    full_name_values = full_name_df[col]
                    paper_ids = alias_df['paper_id']
                    
                    # 创建组合的 HTML 内容
                    combined_values = []
                    for paper_id, alias, summary, full_name in zip(paper_ids, alias_values, summary_values, full_name_values):
                        if alias:  # 如果有 alias
                            # 获取 hover 信息
                            hover_info = get_paper_hover_info(paper_id, self.paper_info_map, self.database)
                            
                            # 生成链接和 tooltip
                            paper_link = generate_paper_link(hover_info["arxiv_id"], hover_info["paper_url"])
                            title_attr = generate_tooltip(
                                hover_info["full_name"] or full_name,
                                hover_info["summary"] or summary,
                                hover_info["company_names"],
                                hover_info["university_names"],
                                hover_info["tag_names"],
                                hover_info["date"],
                                hover_info["author_names"],
                                hover_info["paper_id"]
                            )
                            
                            # 生成单元格内容
                            cell_content = generate_cell_content(alias, None, paper_link, title_attr)
                        else:
                            cell_content = ''
                        combined_values.append(cell_content)
                    
                    self.author_df[col] = combined_values
            
            # 按 date 倒序排序，如果 date 相同就按照 paper_id 倒序排序
            self.author_df = self.author_df.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
        else:
            self.author_df = pd.DataFrame()
    
    def create_company_table(self):
        """创建关注公司工作矩阵表格"""
        if self.company_df is None or len(self.company_df) == 0:
            return pn.pane.Str("暂无公司数据", styles={"font-size": "16px", "padding": "20px"})
        
        # 从原始数据重新生成，只显示 alias
        if hasattr(self, 'company_alias_df') and hasattr(self, 'company_summary_df'):
            df_display = self.company_alias_df[['paper_id']].copy()
            # 添加 date 列
            df_display['date'] = self.company_df['date']
            for col in self.company_alias_df.columns:
                if col != 'paper_id':
                    alias_values = self.company_alias_df[col]
                    paper_ids = self.company_alias_df['paper_id']
                    # 只创建 alias 超链接，添加 full_name、summary、公司和高校信息到 title
                    summary_values = self.company_summary_df[col]
                    full_name_values = self.company_full_name_df[col]
                    cell_values = []
                    for paper_id, alias, summary, full_name in zip(paper_ids, alias_values, summary_values, full_name_values):
                        if alias:
                            # 获取 hover 信息
                            hover_info = get_paper_hover_info(paper_id, self.paper_info_map, self.database)
                            
                            # 生成链接和 tooltip
                            paper_link = generate_paper_link(hover_info["arxiv_id"], hover_info["paper_url"])
                            title_attr = generate_tooltip(
                                hover_info["full_name"] or full_name,
                                hover_info["summary"] or summary,
                                hover_info["company_names"],
                                hover_info["university_names"],
                                hover_info["tag_names"],
                                hover_info["date"],
                                hover_info["author_names"],
                                hover_info["paper_id"]
                            )
                            
                            # 生成单元格内容
                            cell_values.append(generate_cell_content(alias, None, paper_link, title_attr))
                        else:
                            cell_values.append('')
                    df_display[col] = cell_values
            # 按 date 倒序排序，如果 date 相同就按照 paper_id 倒序排序
            df_sorted = df_display.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
        else:
            # 如果没有原始数据，使用现有数据
            df_sorted = self.company_df.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
        
        # 如果启用了聚合模式，将相同 date 的工作合并为一行
        if self.group_by_date and 'date' in df_sorted.columns:
            # 按 date 分组
            grouped = df_sorted.groupby('date', dropna=False)
            merged_rows = []
            
            for date, group in grouped:
                if pd.isna(date) or date == '':
                    # 对于空日期，保持原样
                    merged_rows.extend(group.to_dict('records'))
                else:
                    # 合并相同日期的行
                    merged_row = {'date': date}
                    
                    # 对于每个列，合并内容
                    for col in df_sorted.columns:
                        if col == 'date':
                            continue
                        
                        # 如果是 paper_id 列，在聚合模式下显示数量
                        if col == 'paper_id':
                            # 收集该列的所有非空值（去重）
                            unique_values = set()
                            for _, row in group.iterrows():
                                val = row[col]
                                if pd.notna(val) and str(val).strip():
                                    unique_values.add(str(val))
                            # 显示 paper 数量
                            merged_row[col] = str(len(unique_values))
                        else:
                            # 收集该列的所有非空值
                            values = []
                            for _, row in group.iterrows():
                                val = row[col]
                                if pd.notna(val) and str(val).strip():
                                    values.append(str(val))
                            
                            # 如果有多个值，用 <br> 连接；如果只有一个值，直接使用
                            if len(values) > 1:
                                merged_row[col] = '<br>'.join(values)
                            elif len(values) == 1:
                                merged_row[col] = values[0]
                            else:
                                merged_row[col] = ''
                    
                    merged_rows.append(merged_row)
            
            # 重新创建 DataFrame
            df_sorted = pd.DataFrame(merged_rows)
            
            # 重新排序（按 date 倒序）
            if len(df_sorted) > 0:
                df_sorted = df_sorted.sort_values('date', ascending=False, na_position='last').copy()
        
        # 重新排列列顺序：paper_id, date, ...（其他列），排除 arxiv_id
        cols = list(df_sorted.columns)
        if 'date' in cols:
            cols.remove('date')
            cols.remove('paper_id')
        if 'arxiv_id' in cols:
            cols.remove('arxiv_id')
        new_cols = ['paper_id', 'date'] + cols
        df_sorted = df_sorted[new_cols]
        
        # 为所有公司列创建 HTML formatter（除了 paper_id、date 和 arxiv_id）
        formatters = {}
        for col in df_sorted.columns:
            if col != 'paper_id' and col != 'date' and col != 'arxiv_id':
                formatters[col] = {'type': 'html'}
        
        # 创建列配置
        column_configs = []
        for col in df_sorted.columns:
            if col == 'paper_id':
                column_configs.append({
                    'field': col,
                    'width': 120,
                    'frozen': True,
                    'headerSort': True,
                    'resizable': True,
                })
            elif col == 'date':
                column_configs.append({
                    'field': col,
                    'width': 80,
                    'frozen': True,
                    'headerSort': True,
                    'resizable': True,
                })
            else:
                column_configs.append({
                    'field': col,
                    'width': 120,
                    'minWidth': 80,
                    'headerSort': True,
                    'resizable': True,
                    'formatter': 'html',
                })
        
        # 创建表格，固定前两列（paper_id 和 date）
        table = pn.widgets.Tabulator(
            df_sorted,
            pagination='remote',
            page_size=200,
            sizing_mode='stretch_width',
            height=config.TABLE_HEIGHT_DEFAULT,
            selectable=False,
            show_index=False,
            layout='fit_data_stretch',
            theme='bootstrap5',
            frozen_columns=['paper_id', 'date'],  # 冻结前两列
            styles={
                'table': {'font-size': '11px'},
            },
            formatters=formatters,
            configuration={
                'columns': column_configs
            }
        )
        return table
    
    def create_stats(self):
        """创建统计信息面板"""
        total_papers = len(self.df) if self.df is not None else 0
        
        # 统计有公司名的论文数
        papers_with_companies = sum(1 for paper in self.data if paper["company_names"]) if self.data else 0
        
        # 统计有大学名的论文数
        papers_with_universities = sum(1 for paper in self.data if paper["university_names"]) if self.data else 0
        
        # 统计有摘要的论文数
        papers_with_abstract = sum(1 for paper in self.data if paper["abstract"]) if self.data else 0
        
        # 统计有总结的论文数
        papers_with_summary = sum(1 for paper in self.data if paper.get("summary")) if self.data else 0
        
        stats_html = f"""
        <div style="padding: 8px 15px; background: {config.GRADIENT_PURPLE}; border-radius: {config.BORDER_RADIUS_LARGE}; color: {config.TEXT_COLOR_WHITE}; display: flex; align-items: center; gap: 30px;">
            <span style="font-size: 14px; font-weight: bold;">📊 统计:</span>
            <span style="font-size: 13px;">总论文数: <strong>{total_papers}</strong></span>
            <span style="font-size: 13px;">有摘要: <strong>{papers_with_abstract}</strong></span>
            <span style="font-size: 13px;">有总结: <strong>{papers_with_summary}</strong></span>
            <span style="font-size: 13px;">有企业信息: <strong>{papers_with_companies}</strong></span>
            <span style="font-size: 13px;">有高校信息: <strong>{papers_with_universities}</strong></span>
        </div>
        """
        return pn.pane.HTML(stats_html, sizing_mode='stretch_width')
    
    def create_papers_view(self):
        """创建论文列表视图"""
        # 延迟加载数据
        if not self._data_loaded:
            self.load_data()
        
        # 确保数据已按 Date 倒序排序（如果 Date 为空则按 Paper ID）
        if self.df is not None and len(self.df) > 0:
            if 'Date' in self.df.columns:
                self.df = self.df.sort_values(['Date', 'Paper ID'], ascending=[False, False], na_position='last').copy()
            else:
                self.df = self.df.sort_values('Paper ID', ascending=False).copy()
        
        # 初始化过滤后的数据
        self.df_filtered = self.df.copy() if self.df is not None else pd.DataFrame()
        
        # 创建表格（论文列表视图不使用聚合）
        self.table = self.create_table(use_grouping=False)
        
        # 添加自定义 CSS 样式
        css_pane = get_css_pane()
        
        # 创建搜索框
        search_input = pn.widgets.TextInput(
            name="搜索论文",
            placeholder="输入 Paper ID、日期、链接、别名、标题或作者进行搜索...",
            sizing_mode='stretch_width'
        )
        
        def filter_data(event):
            query = search_input.value.lower() if search_input.value else ""
            if self.df is None or len(self.df) == 0:
                return
            # 只显示需要的列（排除辅助列）
            # 列顺序：Paper ID, Date, Paper Link, Alias, Full Name, Authors, Companies, Universities, Tags, Abstract, Summary
            display_cols = ["Paper ID", "Date", "Paper Link", "Alias", "Full Name", "Authors", "Companies", "Universities", "Tags", "Abstract", "Summary"]
            if not query:
                self.df_filtered = self.df.copy()
            else:
                mask = (
                    self.df["Paper ID"].str.lower().str.contains(query, na=False) |
                    self.df["Date"].astype(str).str.contains(query, na=False) |
                    self.df["Paper Link_original"].astype(str).str.lower().str.contains(query, na=False) |
                    self.df["Alias_original"].str.lower().str.contains(query, na=False) |
                    self.df["Full Name_original"].str.lower().str.contains(query, na=False) |
                    self.df["Authors"].str.lower().str.contains(query, na=False) |
                    self.df["Abstract"].str.lower().str.contains(query, na=False) |
                    self.df["Summary"].str.lower().str.contains(query, na=False) |
                    self.df["Tags"].str.lower().str.contains(query, na=False)
                )
                if 'Date' in self.df.columns:
                    self.df_filtered = self.df[mask].sort_values(['Date', 'Paper ID'], ascending=[False, False], na_position='last').copy()
                else:
                    self.df_filtered = self.df[mask].sort_values('Paper ID', ascending=False).copy()
            
            # 直接更新表格值
            self.table.value = self.df_filtered[display_cols] if len(self.df_filtered) > 0 else self.df_filtered
        
        search_input.param.watch(filter_data, 'value')
        
        # 创建标签管理对话框组件
        self.current_paper_id = None
        tag_modal_paper_id = pn.pane.HTML("", sizing_mode='stretch_width')
        tag_modal_current_tags = pn.Column(sizing_mode='stretch_width')  # 改为 Column 以支持动态添加按钮
        tag_input = pn.widgets.TextInput(name="标签名称", placeholder="输入标签名称（例如: a.b.c），可以输入新标签", sizing_mode='stretch_width')
        tag_add_btn = pn.widgets.Button(name=config.BTN_TEXT_ADD_TAG, button_type="primary", width=config.BUTTON_WIDTH_MEDIUM)
        tag_close_btn = pn.widgets.Button(name=config.BTN_TEXT_CLOSE, button_type="light", width=config.BUTTON_WIDTH_MEDIUM)
        
        def refresh_tag_display(paper_id):
            """刷新标签显示"""
            if not paper_id:
                tag_modal_current_tags.clear()
                return
            
            # 获取论文信息
            paper_info = None
            for paper in self.data:
                if paper["paper_id"] == paper_id:
                    paper_info = paper
                    break
            
            if not paper_info:
                tag_modal_current_tags.clear()
                return
            
            display_id = paper_info.get("arxiv_id") or paper_id
            alias = paper_info.get("alias") or ""
            
            tag_modal_paper_id.object = f"<p><strong>论文 ID:</strong> {html.escape(display_id)}<br><strong>别名:</strong> {html.escape(alias)}</p>"
            
            # 获取当前标签
            current_tags = self.database.get_paper_tags(paper_id)
            
            # 清空现有内容
            tag_modal_current_tags.clear()
            
            if current_tags:
                # 添加标题
                tag_modal_current_tags.append(pn.pane.HTML("<strong>当前标签:</strong>", sizing_mode='stretch_width'))
                
                # 创建一个包含所有标签的容器（使用 Row 让标签横向排列）
                tags_row = pn.Row(sizing_mode='stretch_width', margin=(5, 0))
                
                for tag in current_tags:
                    tag_id = tag["tag_id"]
                    tag_name = tag["tag_name"]
                    
                    # 创建删除处理函数（使用闭包捕获 tag_id）
                    def make_remove_handler(t_id):
                        def remove_handler(event):
                            remove_tag(t_id)
                        return remove_handler
                    
                    # 创建删除按钮，直接绑定 Python 回调
                    remove_btn = pn.widgets.Button(
                        name="×",
                        button_type="light",
                        width=25,
                        height=25
                    )
                    remove_btn.on_click(make_remove_handler(tag_id))
                    
                    # 创建标签显示
                    tag_label = pn.pane.HTML(
                        f"<span style='display: inline-block; background: #e3f2fd; padding: 4px 8px; margin-right: 4px; border-radius: 4px;'>{html.escape(tag_name)}</span>",
                        sizing_mode='fixed',
                        width=150
                    )
                    
                    # 将标签和按钮添加到一行（使用 Column 垂直排列）
                    tag_item = pn.Column(
                        pn.Row(tag_label, remove_btn, sizing_mode='fixed', margin=0),
                        sizing_mode='fixed',
                        width=180,
                        margin=(0, 5)
                    )
                    tags_row.append(tag_item)
                
                tag_modal_current_tags.append(tags_row)
            else:
                tag_modal_current_tags.append(pn.pane.HTML("<div style='margin: 10px 0; color: #666;'>暂无标签</div>", sizing_mode='stretch_width'))
        
        def add_tag(event):
            """添加标签"""
            if not self.current_paper_id:
                return
            
            tag_name = tag_input.value.strip()
            if not tag_name:
                return
            
            try:
                self.database.add_tag_to_paper(self.current_paper_id, tag_name)
                tag_input.value = ""
                # 刷新标签显示
                refresh_tag_display(self.current_paper_id)
                # 刷新表格数据
                self.load_data()
                # 列顺序：Paper ID, Date, Paper Link, Alias, Full Name, Companies, Universities, Tags, Abstract, Summary
                display_cols = ["Paper ID", "Date", "Paper Link", "Alias", "Full Name", "Companies", "Universities", "Tags", "Abstract", "Summary"]
                if self.df is not None and len(self.df) > 0:
                    if 'Date' in self.df.columns:
                        self.df = self.df.sort_values(['Date', 'Paper ID'], ascending=[False, False], na_position='last').copy()
                    else:
                        self.df = self.df.sort_values('Paper ID', ascending=False).copy()
                    self.df_filtered = self.df.copy()
                    # 如果启用了聚合模式，重新创建表格
                    if self.group_by_date:
                        self.table = self.create_table()
                    else:
                        self.table.value = self.df_filtered[display_cols] if len(self.df_filtered) > 0 else self.df_filtered
            except Exception as e:
                tag_modal_current_tags.object = f"<div style='color: red;'>添加标签失败: {str(e)}</div>"
        
        def remove_tag(tag_id):
            """移除标签"""
            if not self.current_paper_id:
                return
            
            try:
                self.database.remove_tag_from_paper(self.current_paper_id, tag_id)
                # 刷新标签显示
                refresh_tag_display(self.current_paper_id)
                # 刷新表格数据
                self.load_data()
                # 列顺序：Paper ID, Date, Paper Link, Alias, Full Name, Companies, Universities, Tags, Abstract, Summary
                display_cols = ["Paper ID", "Date", "Paper Link", "Alias", "Full Name", "Companies", "Universities", "Tags", "Abstract", "Summary"]
                if self.df is not None and len(self.df) > 0:
                    if 'Date' in self.df.columns:
                        self.df = self.df.sort_values(['Date', 'Paper ID'], ascending=[False, False], na_position='last').copy()
                    else:
                        self.df = self.df.sort_values('Paper ID', ascending=False).copy()
                    self.df_filtered = self.df.copy()
                    # 如果启用了聚合模式，重新创建表格
                    if self.group_by_date:
                        self.table = self.create_table()
                    else:
                        self.table.value = self.df_filtered[display_cols] if len(self.df_filtered) > 0 else self.df_filtered
            except Exception as e:
                tag_modal_current_tags.object = f"<div style='color: red;'>移除标签失败: {str(e)}</div>"
        
        tag_add_btn.on_click(add_tag)
        
        # 创建标签管理对话框
        tag_modal_content = pn.Column(
            pn.pane.HTML("<h3 style='margin-top: 0;'>管理标签</h3>", sizing_mode='stretch_width'),
            tag_modal_paper_id,
            tag_modal_current_tags,
            tag_input,
            pn.Row(tag_add_btn, tag_close_btn),
            sizing_mode='stretch_width',
            styles={'background': 'white', 'border': '2px solid #1976d2', 'border-radius': '8px', 'padding': '20px'}
        )
        
        tag_modal = pn.pane.HTML("", visible=False, sizing_mode='fixed', width=0, height=0)
        
        # 使用 Panel 的 Modal
        def open_tag_modal(paper_id):
            """打开标签管理对话框"""
            self.current_paper_id = paper_id
            refresh_tag_display(paper_id)
            # 使用 Panel 的 Modal
            tag_modal_content.visible = True
        
        def close_tag_modal(event):
            """关闭标签管理对话框"""
            tag_modal_content.visible = False
            self.current_paper_id = None
        
        tag_close_btn.on_click(close_tag_modal)
        
        # 保存引用
        self.tag_modal_content = tag_modal_content
        self.open_tag_modal = open_tag_modal
        self.remove_tag = remove_tag
        
        # 创建统计面板
        stats = self.create_stats()
        
        # 初始隐藏标签对话框
        tag_modal_content.visible = False
        
        # 创建隐藏的按钮用于触发打开标签对话框（表格中的按钮需要）
        hidden_open_btn = pn.widgets.Button(name="", visible=False, width=0, height=0)
        
        # 存储 paper_id 的临时变量
        self._temp_paper_id = None
        
        def on_open_modal(event):
            if self._temp_paper_id:
                open_tag_modal(self._temp_paper_id)
        
        hidden_open_btn.on_click(on_open_modal)
        
        # 使用简化的 JavaScript 事件处理（仅用于表格中的管理标签按钮）
        js_handler = pn.pane.HTML("""
        <script>
        (function() {
            function initTagHandlers() {
                // 使用事件委托处理按钮点击
                document.addEventListener('click', function(e) {
                    // 处理管理标签按钮
                    if (e.target.classList.contains('tag-manage-btn')) {
                        e.preventDefault();
                        e.stopPropagation();
                        const paperId = e.target.getAttribute('data-paper-id');
                        if (paperId && window.dashboardInstance) {
                            window.dashboardInstance._temp_paper_id = paperId;
                            // 触发隐藏按钮的点击
                            setTimeout(function() {
                                const buttons = document.querySelectorAll('button');
                                for (let btn of buttons) {
                                    if (btn.offsetWidth === 0 && btn.offsetHeight === 0 && btn.textContent === '') {
                                        btn.click();
                                        break;
                                    }
                                }
                            }, 50);
                        }
                    }
                });
            }
            
            // 初始化事件处理器
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initTagHandlers);
            } else {
                initTagHandlers();
            }
        })();
        </script>
        """, sizing_mode='stretch_width', height=0)
        
        # 设置全局 dashboard 实例引用以便 JavaScript 调用
        setup_global_ref = pn.pane.HTML(f"""
        <script>
        window.dashboardInstance = {{
            _temp_paper_id: null
        }};
        </script>
        """, sizing_mode='stretch_width', height=0)
        
        # 创建搜索行
        search_row = pn.Row(
            search_input,
            sizing_mode='stretch_width'
        )
        
        layout = pn.Column(
            css_pane,
            setup_global_ref,
            js_handler,
            stats,
            pn.Spacer(height=10),
            search_row,
            pn.Spacer(height=10),
            self.table,
            tag_modal_content,
            hidden_open_btn,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        
        return layout
    
    def create_university_table(self):
        """创建关注高校矩阵表格"""
        if self.university_df is None or len(self.university_df) == 0:
            return pn.pane.Str("暂无高校数据", styles={"font-size": "16px", "padding": "20px"})
        
        # 确保数据已按 date 倒序排序，如果 date 相同就按照 paper_id 倒序排序
        df_sorted = self.university_df.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
        
        # 如果启用了聚合模式，将相同 date 的工作合并为一行
        if self.group_by_date and 'date' in df_sorted.columns:
            # 按 date 分组
            grouped = df_sorted.groupby('date', dropna=False)
            merged_rows = []
            
            for date, group in grouped:
                if pd.isna(date) or date == '':
                    # 对于空日期，保持原样
                    merged_rows.extend(group.to_dict('records'))
                else:
                    # 合并相同日期的行
                    merged_row = {'date': date}
                    
                    # 对于每个列，合并内容
                    for col in df_sorted.columns:
                        if col == 'date':
                            continue
                        
                        # 如果是 paper_id 列，在聚合模式下显示数量
                        if col == 'paper_id':
                            # 收集该列的所有非空值（去重）
                            unique_values = set()
                            for _, row in group.iterrows():
                                val = row[col]
                                if pd.notna(val) and str(val).strip():
                                    unique_values.add(str(val))
                            # 显示 paper 数量
                            merged_row[col] = str(len(unique_values))
                        else:
                            # 收集该列的所有非空值
                            values = []
                            for _, row in group.iterrows():
                                val = row[col]
                                if pd.notna(val) and str(val).strip():
                                    values.append(str(val))
                            
                            # 如果有多个值，用 <br> 连接；如果只有一个值，直接使用
                            if len(values) > 1:
                                merged_row[col] = '<br>'.join(values)
                            elif len(values) == 1:
                                merged_row[col] = values[0]
                            else:
                                merged_row[col] = ''
                    
                    merged_rows.append(merged_row)
            
            # 重新创建 DataFrame
            df_sorted = pd.DataFrame(merged_rows)
            
            # 重新排序（按 date 倒序）
            if len(df_sorted) > 0:
                df_sorted = df_sorted.sort_values('date', ascending=False, na_position='last').copy()
        
        # 重新排列列顺序：paper_id, date, ...（其他列），排除 arxiv_id
        cols = list(df_sorted.columns)
        if 'date' in cols:
            cols.remove('date')
            cols.remove('paper_id')
        if 'arxiv_id' in cols:
            cols.remove('arxiv_id')
        new_cols = ['paper_id', 'date'] + cols
        df_sorted = df_sorted[new_cols]
        
        # 为所有高校列创建 HTML formatter（除了 paper_id、date 和 arxiv_id）
        formatters = {}
        for col in df_sorted.columns:
            if col != 'paper_id' and col != 'date' and col != 'arxiv_id':
                formatters[col] = {'type': 'html'}
        
        # 创建列配置
        column_configs = []
        for col in df_sorted.columns:
            if col == 'paper_id':
                column_configs.append({
                    'field': col,
                    'width': 120,
                    'frozen': True,
                    'headerSort': True,
                    'resizable': True,
                })
            elif col == 'date':
                column_configs.append({
                    'field': col,
                    'width': 80,
                    'frozen': True,
                    'headerSort': True,
                    'resizable': True,
                })
            else:
                column_configs.append({
                    'field': col,
                    'width': 120,
                    'minWidth': 80,
                    'headerSort': True,
                    'resizable': True,
                    'formatter': 'html',
                })
        
        # 创建表格，固定前两列（paper_id 和 date）
        table = pn.widgets.Tabulator(
            df_sorted,
            pagination='remote',
            page_size=200,
            sizing_mode='stretch_width',
            height=config.TABLE_HEIGHT_DEFAULT,
            selectable=False,
            show_index=False,
            layout='fit_data_stretch',
            theme='bootstrap5',
            frozen_columns=['paper_id', 'date'],  # 冻结前两列
            styles={
                'table': {'font-size': '11px'},
            },
            formatters=formatters,
            configuration={
                'columns': column_configs
            }
        )
        return table
    
    def create_university_view(self):
        """创建关注高校视图"""
        # 延迟加载数据
        if not self._data_loaded:
            self.load_data()
        
        # 创建高校表格
        self.university_table = self.create_university_table()
        
        # 添加自定义 CSS 样式
        css_pane = get_css_pane()
        
        # 创建聚合按钮
        group_button_text = '✅ 聚合相同日期' if self.group_by_date else '📋 聚合相同日期'
        group_button = pn.widgets.Button(
            name=group_button_text,
            button_type='primary' if self.group_by_date else 'light',
            width=140
        )
        
        # 统计信息（包含按钮）
        if self.university_df is not None and len(self.university_df) > 0:
            num_universities = len(self.university_df.columns) - 1  # 减去 paper_id 列
            num_papers = len(self.university_df)
            stats_html = f"""
            <div style="padding: 8px 15px; background: {config.GRADIENT_BLUE}; border-radius: {config.BORDER_RADIUS_LARGE}; color: {config.TEXT_COLOR_WHITE}; display: flex; align-items: center; justify-content: space-between; gap: 30px;">
                <div style="display: flex; align-items: center; gap: 30px;">
                    <span style="font-size: 14px; font-weight: bold;">📊 统计:</span>
                    <span style="font-size: 13px;">高校数量: <strong>{num_universities}</strong></span>
                    <span style="font-size: 13px;">论文数量: <strong>{num_papers}</strong></span>
                </div>
            </div>
            """
            stats = pn.pane.HTML(stats_html, sizing_mode='stretch_width')
        else:
            stats = pn.pane.Str("")
        
        # 创建统计和按钮行
        stats_row = pn.Row(
            stats,
            group_button,
            sizing_mode='stretch_width',
            align='center'
        )
        
        layout = pn.Column(
            css_pane,
            stats_row,
            pn.Spacer(height=10),
            self.university_table,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        def toggle_group_by_date(event):
            """切换聚合模式"""
            self.group_by_date = not self.group_by_date
            
            # 重新创建表格
            new_table = self.create_university_table()
            old_table = self.university_table
            self.university_table = new_table
            
            # 替换布局中的表格对象
            try:
                for i, obj in enumerate(layout.objects):
                    if obj is old_table:
                        layout.objects[i] = new_table
                        break
            except:
                pass
            
            # 更新 all_tabs_info 中的视图引用（如果存在）
            if hasattr(self, 'all_tabs_info') and 'universities' in self.all_tabs_info:
                self.all_tabs_info['universities']['view'] = layout
            
            # 如果当前显示的是学校视图，重新切换 tab 以刷新视图
            if hasattr(self, 'switch_tab'):
                try:
                    if hasattr(self, 'current_tab_content'):
                        # 重新切换 tab 以刷新视图
                        self.switch_tab('universities')
                except Exception as e:
                    # 如果重新切换失败，尝试直接更新 current_tab_content
                    try:
                        if hasattr(self, 'current_tab_content'):
                            self.current_tab_content.clear()
                            self.current_tab_content.append(layout)
                    except:
                        pass
            
            # 更新按钮文本和样式
            group_button.name = '✅ 聚合相同日期' if self.group_by_date else '📋 聚合相同日期'
            group_button.button_type = 'primary' if self.group_by_date else 'light'
        
        group_button.on_click(toggle_group_by_date)
        
        return layout
    
    def build_tag_tree(self, tags):
        """
        构建标签树结构
        tags: [{"tag_id": 1, "tag_name": "a.b.c"}, ...]
        返回: 树形结构字典
        """
        tree = {}
        for tag in tags:
            tag_name = tag["tag_name"]
            parts = tag_name.split(".")
            current = tree
            for i, part in enumerate(parts):
                if part not in current:
                    # 创建新节点
                    current[part] = {
                        "_tag_id": None,  # 初始化为 None，后面会根据是否是叶子节点设置
                        "_full_path": ".".join(parts[:i+1]),
                        "_children": {}
                    }
                # 如果是最后一个部分，设置 tag_id
                if i == len(parts) - 1:
                    current[part]["_tag_id"] = tag["tag_id"]
                # 注意：如果一个节点既有 tag_id 又有子节点，我们保留 tag_id，这样用户可以点击查看该标签的论文
                
                current = current[part]["_children"]
        return tree
    
    def render_tag_tree_html(self, tree, level=0, folder_id_counter=[0]):
        """
        将标签树渲染为 HTML
        folder_id_counter 用于生成唯一的文件夹 ID
        """
        html_parts = []
        
        for tag_name, node in sorted(tree.items()):
            tag_id = node.get("_tag_id")
            full_path = node.get("_full_path", tag_name)
            children = node.get("_children", {})
            has_children = bool(children)
            
            if tag_id and not has_children:
                # 纯叶子节点（有 tag_id 但没有子节点），显示标签和论文数量
                html_parts.append(f'<li class="tag-item" data-tag-id="{tag_id}" data-tag-path="{full_path}">')
                html_parts.append(f'  <span class="tag-name">{html.escape(tag_name)}</span>')
                html_parts.append(f'  <span class="tag-count" id="count-{tag_id}">(0)</span>')
                html_parts.append(f'</li>')
            else:
                # 非叶子节点（有子节点）或既有 tag_id 又有子节点，显示文件夹图标，支持折叠
                folder_id = f"folder-{folder_id_counter[0]}"
                folder_id_counter[0] += 1
                
                html_parts.append(f'<li class="tag-folder">')
                # 使用简化的内联事件处理器
                if has_children:
                    # 转义 folder_id 中的特殊字符
                    folder_id_escaped = html.escape(folder_id.replace("'", "\\'"))
                    # 简化的折叠/展开逻辑
                    onclick_handler = f"this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none';this.querySelector('.folder-toggle').textContent=this.nextElementSibling.style.display==='none'?'▶':'▼';"
                    html_parts.append(f'  <div class="folder-header" onclick="{onclick_handler}">')
                    html_parts.append(f'    <span class="folder-toggle">▶</span>')
                else:
                    html_parts.append(f'  <div class="folder-header">')
                    html_parts.append(f'    <span class="folder-toggle" style="visibility: hidden;">▶</span>')
                html_parts.append(f'    <span class="folder-icon">📁</span>')
                if tag_id:
                    # 如果既有 tag_id 又有子节点，显示为可点击的标签
                    html_parts.append(f'    <span class="folder-name tag-name" data-tag-id="{tag_id}" data-tag-path="{full_path}" style="color: #1976d2; cursor: pointer;">{html.escape(tag_name)}</span>')
                else:
                    html_parts.append(f'    <span class="folder-name">{html.escape(tag_name)}</span>')
                html_parts.append(f'  </div>')
                if has_children:
                    html_parts.append(f'  <ul class="tag-children" id="{folder_id}" style="display: none;">')
                    html_parts.append(self.render_tag_tree_html(children, level + 1, folder_id_counter))
                    html_parts.append(f'  </ul>')
                html_parts.append(f'</li>')
        
        return "\n".join(html_parts)
    
    def create_edit_paper_view(self):
        """创建论文编辑视图"""
        # 获取所有论文的搜索选项（用于 AutocompleteInput）
        def get_paper_search_options():
            """获取所有论文的搜索选项列表"""
            try:
                papers = self.database.get_all_papers_with_details()
                options = []
                for paper in papers:
                    paper_id = paper.get("paper_id", "")
                    arxiv_id = paper.get("arxiv_id", "")
                    alias = paper.get("alias", "")
                    full_name = paper.get("full_name", "")
                    
                    # 显示 ID（优先显示 arxiv_id）
                    display_id = arxiv_id if arxiv_id else paper_id
                    
                    # 创建显示文本：ID + alias/title
                    display_text = display_id
                    if alias:
                        display_text += f" - {alias}"
                    elif full_name:
                        # 如果标题太长，截断
                        short_title = full_name[:50] + "..." if len(full_name) > 50 else full_name
                        display_text += f" - {short_title}"
                    
                    # 使用 paper_id 作为值（因为这是唯一标识符）
                    options.append((display_text, paper_id))
                return options
            except:
                return []
        
        # 输入搜索关键词的组件（使用 AutocompleteInput 支持模糊搜索）
        paper_search_input = pn.widgets.AutocompleteInput(
            name="搜索论文",
            placeholder="输入 Paper ID、arXiv ID、别名或标题进行搜索",
            options=get_paper_search_options(),
            case_sensitive=False,
            search_strategy='includes',
            sizing_mode='stretch_width',
            width=config.PANEL_WIDTH_DEFAULT
        )
        
        # 搜索结果列表（如果有多个匹配）- 保留用于兼容
        search_results_pane = pn.pane.HTML("", sizing_mode='stretch_width', visible=False)
        
        # 论文信息显示区域
        paper_info_pane = pn.pane.HTML(
            "<div style='padding: 20px; color: #666;'>请输入 Paper ID、别名或标题查看论文信息</div>",
            sizing_mode='stretch_width'
        )
        
        # 当前标签显示区域
        current_tags_pane = pn.pane.HTML(
            "<div style='padding: 20px; color: #666;'>暂无标签</div>",
            sizing_mode='stretch_width'
        )
        
        # 创建日期编辑区域（需要在 load_paper_info 之前定义）
        date_input = pn.widgets.TextInput(
            name="日期",
            placeholder="格式: yyyyMM (例如: 202401)",
            sizing_mode='stretch_width',
            width=config.INPUT_WIDTH_DEFAULT
        )
        save_date_btn = pn.widgets.Button(name="保存日期", button_type="primary", width=120)
        
        # 编辑区域
        edit_section = pn.Column(
            pn.pane.HTML("<h3 style='margin-top: 0;'>编辑信息</h3>", sizing_mode='stretch_width'),
            pn.Row(
                date_input,
                save_date_btn,
                sizing_mode='stretch_width'
            ),
            sizing_mode='stretch_width',
            styles={'background': '#f0f7ff', 'padding': '15px', 'border-radius': '8px', 'border': '1px solid #b3d9ff'},
            visible=False  # 初始隐藏，选择论文后显示
        )
        
        # 获取所有已有标签作为选项
        def get_all_tag_names():
            """获取所有标签名称列表"""
            try:
                tags = self.database.get_all_tags()
                return [tag["tag_name"] for tag in tags]
            except:
                return []
        
        # 添加标签的输入框（使用 AutocompleteInput 支持模糊搜索，同时允许输入新标签）
        new_tag_input = pn.widgets.AutocompleteInput(
            name="新标签",
            placeholder="输入标签名称（例如: a.b.c），可从下拉框选择已有标签或直接输入新标签",
            options=get_all_tag_names(),
            case_sensitive=False,
            search_strategy='includes',
            restrict=False,  # 允许输入不在选项中的值（即允许创建新标签）
            sizing_mode='stretch_width',
            width=config.INPUT_WIDTH_DEFAULT
        )
        add_tag_btn = pn.widgets.Button(name="添加标签", button_type="primary", width=120)
        
        # 刷新标签选项的函数
        def refresh_tag_options():
            """刷新标签选项列表"""
            new_tag_input.options = get_all_tag_names()
        
        # 当前选中的 paper_id
        current_paper_id = [None]
        
        def load_paper_info(query_or_paper_id):
            """加载论文信息（支持通过 paper_id/alias/title 搜索）"""
            # 处理 AutocompleteInput 可能返回 tuple 的情况
            if isinstance(query_or_paper_id, tuple):
                # 如果是元组，取第二个元素（paper_id）
                query_or_paper_id = query_or_paper_id[1] if len(query_or_paper_id) > 1 else query_or_paper_id[0]
            
            # 转换为字符串并去除空白
            if query_or_paper_id:
                query_or_paper_id = str(query_or_paper_id).strip()
            
            if not query_or_paper_id:
                paper_info_pane.object = "<div style='padding: 20px; color: #666;'>请输入搜索关键词</div>"
                current_tags_pane.object = "<div style='padding: 20px; color: #666;'>暂无标签</div>"
                search_results_pane.visible = False
                edit_section.visible = False
                return
            
            try:
                # 如果输入的是 paper_id（从 AutocompleteInput 选择的值），直接使用
                # 否则使用搜索方法
                paper_info = None
                
                # 先尝试作为 paper_id 直接查找（可能是从下拉框选择的）
                try:
                    paper_info = self.database.get_paper_info(paper_id=query_or_paper_id)
                except:
                    pass
                
                # 如果没找到，使用搜索方法
                if not paper_info:
                    papers = self.database.search_paper(query_or_paper_id)
                    if papers:
                        # 如果只有一个结果，直接使用
                        if len(papers) == 1:
                            paper_info = papers[0]
                            search_results_pane.visible = False
                        else:
                            # 多个结果，显示选择列表
                            results_html = "<div style='padding: 20px; background: #f0f0f0; border-radius: 8px; margin-bottom: 20px;'><h4>找到多个匹配结果，请选择：</h4><div style='max-height: 300px; overflow-y: auto;'>"
                            for i, paper in enumerate(papers):
                                paper_id_val = paper.get("paper_id", "")
                                arxiv_id = paper.get("arxiv_id", "")
                                alias = paper.get("alias", "")
                                full_name = paper.get("full_name", "")
                                display_id = arxiv_id if arxiv_id else paper_id_val
                                display_name = alias if alias else (full_name[:50] + "..." if full_name and len(full_name) > 50 else full_name)
                                
                                results_html += f"""
                                <div style='padding: 10px; margin: 5px 0; background: white; border-radius: 4px; cursor: pointer; border: 2px solid #1976d2;' 
                                     onclick='document.querySelector("[name=\\"搜索论文\\"]").value = "{html.escape(paper_id_val)}"; document.querySelector("[name=\\"搜索论文\\"]").dispatchEvent(new Event("input"));'>
                                    <strong>{html.escape(display_id)}</strong>
                                    {f"<br><span style='color: #666;'>{html.escape(display_name)}</span>" if display_name else ""}
                                </div>
                                """
                            results_html += "</div></div>"
                            search_results_pane.object = results_html
                            search_results_pane.visible = True
                            
                            # 默认选择第一个结果
                            paper_info = papers[0]
                
                if not paper_info:
                    paper_info_pane.object = f"<div style='padding: 20px; color: red;'>未找到匹配的论文: {html.escape(query_or_paper_id)}</div>"
                    current_tags_pane.object = "<div style='padding: 20px; color: #666;'>暂无标签</div>"
                    search_results_pane.visible = False
                    current_paper_id[0] = None
                    edit_section.visible = False
                    return
                
                # 显示论文信息
                paper_id_val = paper_info.get("paper_id", "")
                arxiv_id = paper_info.get("arxiv_id", "")
                paper_url = paper_info.get("paper_url", "")
                date = paper_info.get("date", "")
                alias = paper_info.get("alias", "")
                full_name = paper_info.get("full_name", "")
                abstract = paper_info.get("abstract", "")
                summary = paper_info.get("summary", "")
                company_names = paper_info.get("company_names", [])
                university_names = paper_info.get("university_names", [])
                
                display_id = arxiv_id if arxiv_id else paper_id_val
                
                info_html = f"""
                <div style='padding: 20px; background: #f9f9f9; border-radius: 8px;'>
                    <h3 style='margin-top: 0;'>论文信息</h3>
                    <p><strong>Paper ID:</strong> {html.escape(paper_id_val)}</p>
                    <p><strong>显示 ID:</strong> {html.escape(display_id)}</p>
                    {f"<p><strong>arXiv ID:</strong> {html.escape(arxiv_id)}</p>" if arxiv_id else ""}
                    <p><strong>URL:</strong> <a href="{html.escape(paper_url)}" target="_blank">{html.escape(paper_url)}</a></p>
                    {f"<p><strong>日期:</strong> {html.escape(date)}</p>" if date else ""}
                    {f"<p><strong>别名:</strong> {html.escape(alias)}</p>" if alias else ""}
                    {f"<p><strong>完整名称:</strong> {html.escape(full_name)}</p>" if full_name else ""}
                    {f"<p><strong>摘要:</strong> {html.escape(abstract[:200])}...</p>" if abstract else ""}
                    {f"<p><strong>总结:</strong> {html.escape(summary)}</p>" if summary else ""}
                    {f"<p><strong>公司:</strong> {', '.join([html.escape(c) for c in company_names])}</p>" if company_names else ""}
                    {f"<p><strong>高校:</strong> {', '.join([html.escape(u) for u in university_names])}</p>" if university_names else ""}
                </div>
                """
                paper_info_pane.object = info_html
                
                # 加载并显示当前标签
                refresh_tags(paper_id_val)
                current_paper_id[0] = paper_id_val
                # 刷新标签选项（确保下拉框中的选项是最新的）
                refresh_tag_options()
                
                # 更新编辑区域的日期输入框并显示编辑区域
                date_input.value = date if date else ""
                edit_section.visible = True
                
            except Exception as e:
                paper_info_pane.object = f"<div style='padding: 20px; color: red;'>加载论文信息时出错: {str(e)}</div>"
                current_tags_pane.object = "<div style='padding: 20px; color: #666;'>暂无标签</div>"
                current_paper_id[0] = None
                edit_section.visible = False
        
        # 创建标签删除按钮区域（动态更新）
        tag_delete_buttons_pane = pn.Column(sizing_mode='stretch_width')
        
        def refresh_tags(paper_id):
            """刷新标签显示"""
            if not paper_id:
                current_tags_pane.object = "<div style='padding: 20px; color: #666;'>暂无标签</div>"
                return
            
            try:
                tags = self.database.get_paper_tags(paper_id)
                if tags:
                    tags_html = "<div style='padding: 20px;'><h4>当前标签:</h4><div style='margin-top: 10px;'>"
                    for tag in tags:
                        tag_name = tag["tag_name"]
                        tags_html += f"""
                        <div style='display: inline-block; background: #e3f2fd; padding: 6px 12px; margin: 4px 4px 4px 0; border-radius: 4px;'>
                            {html.escape(tag_name)}
                        </div>
                        """
                    tags_html += "</div></div>"
                    current_tags_pane.object = tags_html
                    
                    # 更新删除按钮区域
                    update_tag_delete_buttons(paper_id)
                else:
                    current_tags_pane.object = "<div style='padding: 20px; color: #666;'>暂无标签</div>"
                    tag_delete_buttons_pane.clear()
            except Exception as e:
                current_tags_pane.object = f"<div style='padding: 20px; color: red;'>加载标签时出错: {str(e)}</div>"
                tag_delete_buttons_pane.clear()
        
        def update_tag_delete_buttons(paper_id):
            """更新标签删除按钮"""
            if not paper_id:
                tag_delete_buttons_pane.clear()
                return
            
            try:
                tags = self.database.get_paper_tags(paper_id)
                tag_delete_buttons_pane.clear()
                
                if tags:
                    tag_delete_buttons_pane.append(pn.pane.HTML("<h4>删除标签:</h4>", sizing_mode='stretch_width'))
                    for tag in tags:
                        tag_id = tag["tag_id"]
                        tag_name = tag["tag_name"]
                        
                        remove_btn = pn.widgets.Button(
                            name=f"删除: {tag_name}",
                            button_type="light",
                            width=200
                        )
                        
                        def make_remove_handler(t_id, t_name):
                            def remove_handler(event):
                                try:
                                    self.database.remove_tag_from_paper(paper_id, t_id)
                                    refresh_tags(paper_id)
                                    # 重新加载论文信息以更新显示
                                    load_paper_info(paper_id)
                                except Exception as e:
                                    current_tags_pane.object = f"<div style='padding: 20px; color: red;'>删除标签失败: {str(e)}</div>"
                            return remove_handler
                        
                        remove_btn.on_click(make_remove_handler(tag_id, tag_name))
                        tag_delete_buttons_pane.append(remove_btn)
            except Exception as e:
                pass
        
        def on_search_change(event):
            """搜索输入变化时的处理"""
            # AutocompleteInput 的 value 可能是选项的值（paper_id）或整个选项元组
            selected_value = paper_search_input.value
            
            # 处理 tuple 情况
            if isinstance(selected_value, tuple):
                # 如果是元组，取第二个元素（paper_id）
                selected_value = selected_value[1] if len(selected_value) > 1 else selected_value[0]
            
            if selected_value:
                # 转换为字符串
                selected_value = str(selected_value).strip()
                if selected_value:
                    # 如果是从下拉框选择的，直接使用 paper_id
                    load_paper_info(selected_value)
                else:
                    # 清空显示
                    paper_info_pane.object = "<div style='padding: 20px; color: #666;'>请输入搜索关键词</div>"
                    current_tags_pane.object = "<div style='padding: 20px; color: #666;'>暂无标签</div>"
                    search_results_pane.visible = False
                    current_paper_id[0] = None
                    edit_section.visible = False
            else:
                # 清空显示
                paper_info_pane.object = "<div style='padding: 20px; color: #666;'>请输入搜索关键词</div>"
                current_tags_pane.object = "<div style='padding: 20px; color: #666;'>暂无标签</div>"
                search_results_pane.visible = False
                current_paper_id[0] = None
                edit_section.visible = False
        
        # 同时监听 value 和 value_input 的变化
        # value_input 是用户输入的原始文本
        def on_search_input_change(event):
            """监听用户输入文本的变化"""
            # 获取当前输入的文本
            # Panel 的 AutocompleteInput 在用户输入时会触发 value_input 变化
            # 我们可以使用这个来实时搜索
            pass  # 暂时不实现实时搜索，只在选择时触发
        
        # 监听 value 变化（选择时触发）
        paper_search_input.param.watch(on_search_change, 'value')
        
        def on_add_tag(event):
            """添加标签"""
            if not current_paper_id[0]:
                add_tag_btn.name = "❌ 请先输入 Paper ID"
                return
            
            tag_name = new_tag_input.value.strip()
            if not tag_name:
                add_tag_btn.name = "❌ 请输入标签名称"
                return
            
            try:
                add_tag_btn.disabled = True
                add_tag_btn.name = "⏳ 添加中..."
                self.database.add_tag_to_paper(current_paper_id[0], tag_name)
                new_tag_input.value = ""
                # 刷新标签选项（因为可能添加了新标签）
                refresh_tag_options()
                refresh_tags(current_paper_id[0])
                add_tag_btn.name = "✅ 添加成功"
                # 重新加载论文信息
                load_paper_info(current_paper_id[0])
            except Exception as e:
                add_tag_btn.name = f"❌ 错误: {str(e)}"
            finally:
                add_tag_btn.disabled = False
                # 2秒后恢复按钮文本
                import threading
                def reset_button():
                    import time
                    time.sleep(config.API_DELAY_MEDIUM)
                    add_tag_btn.name = "添加标签"
                threading.Thread(target=reset_button, daemon=True).start()
        
        def on_save_date(event):
            """保存日期"""
            if not current_paper_id[0]:
                save_date_btn.name = "❌ 请先选择论文"
                return
            
            date_value = date_input.value.strip()
            if not date_value:
                save_date_btn.name = "❌ 请输入日期"
                return
            
            try:
                save_date_btn.disabled = True
                save_date_btn.name = "⏳ 保存中..."
                # 更新数据库
                self.database.update_paper_info([{
                    "paper_id": current_paper_id[0],
                    "date": date_value
                }])
                # 重新加载论文信息
                load_paper_info(current_paper_id[0])
                save_date_btn.name = "✅ 保存成功"
            except Exception as e:
                save_date_btn.name = f"❌ 错误: {str(e)}"
            finally:
                save_date_btn.disabled = False
                # 2秒后恢复按钮文本
                import threading
                def reset_button():
                    import time
                    time.sleep(config.API_DELAY_MEDIUM)
                    save_date_btn.name = "保存日期"
                threading.Thread(target=reset_button, daemon=True).start()
        
        save_date_btn.on_click(on_save_date)
        
        paper_search_input.param.watch(on_search_change, 'value')
        add_tag_btn.on_click(on_add_tag)
        
        
        # 创建左右分栏布局
        # 左侧：论文搜索和信息
        left_panel = pn.Column(
            pn.Row(
                paper_search_input,
                sizing_mode='stretch_width'
            ),
            pn.Spacer(height=10),
            search_results_pane,
            pn.Spacer(height=10),
            paper_info_pane,
            pn.Spacer(height=10),
            edit_section,
            sizing_mode='stretch_width'
        )
        
        # 右侧：标签管理
        right_panel = pn.Column(
            pn.pane.HTML("<h3 style='margin-top: 0;'>标签管理</h3>", sizing_mode='stretch_width'),
            current_tags_pane,
            tag_delete_buttons_pane,
            pn.Spacer(height=10),
            pn.Row(
                new_tag_input,
                add_tag_btn,
                sizing_mode='stretch_width'
            ),
            sizing_mode='stretch_width',
            styles={'background': '#f9f9f9', 'padding': '15px', 'border-radius': '8px', 'border': '1px solid #ddd'}
        )
        
        # 合并为左右分栏布局
        # 设置右侧面板固定宽度，左侧自适应
        right_panel.width = 400
        layout = pn.Column(
            pn.Row(
                left_panel,
                pn.Spacer(width=20),
                right_panel,
                sizing_mode='stretch_width'
            ),
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        return layout
    
    def create_edit_tag_view(self):
        """创建标签编辑视图"""
        # 获取所有标签的搜索选项（用于 AutocompleteInput）
        def get_tag_search_options():
            """获取所有标签的搜索选项列表"""
            try:
                tags = self.database.get_all_tags()
                options = []
                for tag in tags:
                    tag_id = tag["tag_id"]
                    tag_name = tag["tag_name"]
                    # 使用标签名称作为显示文本和值
                    options.append((tag_name, tag_id))
                return options
            except:
                return []
        
        # 输入搜索关键词的组件（使用 AutocompleteInput 支持模糊搜索）
        tag_search_input = pn.widgets.AutocompleteInput(
            name="搜索标签",
            placeholder="输入标签名称进行搜索",
            options=get_tag_search_options(),
            case_sensitive=False,
            search_strategy='includes',
            sizing_mode='stretch_width',
            width=config.PANEL_WIDTH_DEFAULT
        )
        
        # 标签信息显示区域
        tag_info_pane = pn.pane.HTML(
            "<div style='padding: 20px; color: #666;'>请输入标签名称查看标签信息</div>",
            sizing_mode='stretch_width'
        )
        
        # 关联论文列表显示区域
        papers_list_pane = pn.pane.HTML(
            "<div style='padding: 20px; color: #666;'>暂无关联论文</div>",
            sizing_mode='stretch_width'
        )
        
        # 当前选中的 tag_id
        current_tag_id = [None]
        
        def load_tag_info(query_or_tag_id):
            """加载标签信息（支持通过 tag_id/标签名称搜索）"""
            # 处理 AutocompleteInput 可能返回 tuple 的情况
            if isinstance(query_or_tag_id, tuple):
                # 如果是元组，取第二个元素（tag_id）
                query_or_tag_id = query_or_tag_id[1] if len(query_or_tag_id) > 1 else query_or_tag_id[0]
            
            # 转换为字符串并去除空白
            if query_or_tag_id:
                query_or_tag_id = str(query_or_tag_id).strip()
            
            if not query_or_tag_id:
                tag_info_pane.object = "<div style='padding: 20px; color: #666;'>请输入搜索关键词</div>"
                papers_list_pane.object = "<div style='padding: 20px; color: #666;'>暂无关联论文</div>"
                edit_section.visible = False
                return
            
            try:
                # 如果输入的是 tag_id（从 AutocompleteInput 选择的值），直接使用
                # 否则通过标签名称查找
                tag_info = None
                tag_id_val = None
                
                # 先尝试作为 tag_id 直接查找（可能是从下拉框选择的）
                try:
                    tag_id_val = int(query_or_tag_id)
                    # 通过 tag_id 查找标签
                    tags = self.database.get_all_tags()
                    for tag in tags:
                        if tag["tag_id"] == tag_id_val:
                            tag_info = tag
                            break
                except:
                    # 不是数字，尝试通过标签名称查找
                    tags = self.database.get_all_tags()
                    for tag in tags:
                        if tag["tag_name"] == query_or_tag_id or query_or_tag_id in tag["tag_name"]:
                            tag_info = tag
                            tag_id_val = tag["tag_id"]
                            break
                
                if not tag_info:
                    tag_info_pane.object = f"<div style='padding: 20px; color: red;'>未找到匹配的标签: {html.escape(query_or_tag_id)}</div>"
                    papers_list_pane.object = "<div style='padding: 20px; color: #666;'>暂无关联论文</div>"
                    current_tag_id[0] = None
                    edit_section.visible = False
                    return
                
                # 显示标签信息
                tag_id_val = tag_info["tag_id"]
                tag_name = tag_info["tag_name"]
                
                # 获取关联的论文
                papers = self.database.get_papers_by_tag(tag_id_val)
                num_papers = len(papers)
                
                info_html = f"""
                <div style='padding: 20px; background: #f9f9f9; border-radius: 8px;'>
                    <h3 style='margin-top: 0;'>标签信息</h3>
                    <p><strong>标签 ID:</strong> {tag_id_val}</p>
                    <p><strong>标签名称:</strong> {html.escape(tag_name)}</p>
                    <p><strong>关联论文数:</strong> {num_papers}</p>
                </div>
                """
                tag_info_pane.object = info_html
                
                # 显示关联论文列表
                if papers:
                    papers_html = "<div style='padding: 20px;'><h4>关联论文:</h4><div style='max-height: 400px; overflow-y: auto;'>"
                    for paper in papers:
                        paper_id = paper.get("paper_id", "")
                        arxiv_id = paper.get("arxiv_id", "")
                        paper_url = paper.get("paper_url", "")
                        alias = paper.get("alias", "")
                        full_name = paper.get("full_name", "")
                        
                        display_id = arxiv_id if arxiv_id else paper_id
                        display_name = alias if alias else (full_name[:50] + "..." if full_name and len(full_name) > 50 else full_name)
                        
                        papers_html += f"""
                        <div style='padding: 10px; margin: 5px 0; background: white; border-radius: 4px; border-left: 3px solid #1976d2;'>
                            <p style='margin: 0;'><strong>{html.escape(display_id)}</strong></p>
                            {f"<p style='margin: 5px 0 0 0; color: #666;'>{html.escape(display_name)}</p>" if display_name else ""}
                            {f"<p style='margin: 5px 0 0 0;'><a href='{html.escape(paper_url)}' target='_blank'>{html.escape(paper_url)}</a></p>" if paper_url else ""}
                        </div>
                        """
                    papers_html += "</div></div>"
                    papers_list_pane.object = papers_html
                else:
                    papers_list_pane.object = "<div style='padding: 20px; color: #666;'>暂无关联论文</div>"
                
                current_tag_id[0] = tag_id_val
                # 更新编辑区域的标签名称输入框并显示编辑区域
                tag_name_input.value = tag_name
                edit_section.visible = True
                
            except Exception as e:
                tag_info_pane.object = f"<div style='padding: 20px; color: red;'>加载标签信息时出错: {str(e)}</div>"
                papers_list_pane.object = "<div style='padding: 20px; color: #666;'>暂无关联论文</div>"
                current_tag_id[0] = None
                edit_section.visible = False
        
        # 创建标签名称编辑区域
        tag_name_input = pn.widgets.TextInput(
            name="标签名称",
            placeholder="输入新的标签名称",
            sizing_mode='stretch_width',
            width=config.INPUT_WIDTH_DEFAULT
        )
        save_tag_name_btn = pn.widgets.Button(name="保存标签名称", button_type="primary", width=150)
        delete_tag_btn = pn.widgets.Button(name="删除标签", button_type="danger", width=150)
        
        # 编辑区域
        edit_section = pn.Column(
            pn.pane.HTML("<h3 style='margin-top: 0;'>编辑标签</h3>", sizing_mode='stretch_width'),
            pn.Row(
                tag_name_input,
                save_tag_name_btn,
                sizing_mode='stretch_width'
            ),
            pn.Spacer(height=10),
            pn.Row(
                delete_tag_btn,
                sizing_mode='stretch_width'
            ),
            sizing_mode='stretch_width',
            styles={'background': '#f0f7ff', 'padding': '15px', 'border-radius': '8px', 'border': '1px solid #b3d9ff'},
            visible=False  # 初始隐藏，选择标签后显示
        )
        
        def on_search_change(event):
            """搜索输入变化时的处理"""
            selected_value = tag_search_input.value
            
            # 处理 tuple 情况
            if isinstance(selected_value, tuple):
                selected_value = selected_value[1] if len(selected_value) > 1 else selected_value[0]
            
            if selected_value:
                selected_value = str(selected_value).strip()
                if selected_value:
                    load_tag_info(selected_value)
                else:
                    tag_info_pane.object = "<div style='padding: 20px; color: #666;'>请输入搜索关键词</div>"
                    papers_list_pane.object = "<div style='padding: 20px; color: #666;'>暂无关联论文</div>"
                    current_tag_id[0] = None
                    edit_section.visible = False
            else:
                tag_info_pane.object = "<div style='padding: 20px; color: #666;'>请输入搜索关键词</div>"
                papers_list_pane.object = "<div style='padding: 20px; color: #666;'>暂无关联论文</div>"
                current_tag_id[0] = None
                edit_section.visible = False
        
        def on_save_tag_name(event):
            """保存标签名称"""
            if not current_tag_id[0]:
                save_tag_name_btn.name = "❌ 请先选择标签"
                return
            
            new_tag_name = tag_name_input.value.strip()
            if not new_tag_name:
                save_tag_name_btn.name = "❌ 请输入标签名称"
                return
            
            try:
                save_tag_name_btn.disabled = True
                save_tag_name_btn.name = "⏳ 保存中..."
                
                # 保存旧的 tag_id，用于检查是否被合并
                old_tag_id = current_tag_id[0]
                
                # 更新数据库（如果新标签名已存在，会自动合并）
                self.database.update_tag_name(old_tag_id, new_tag_name)
                
                # 检查标签是否还存在（如果被合并了，原来的标签会被删除）
                tags = self.database.get_all_tags()
                tag_exists = any(tag["tag_id"] == old_tag_id for tag in tags)
                
                if tag_exists:
                    # 标签名称已更新，重新加载当前标签
                    load_tag_info(old_tag_id)
                    save_tag_name_btn.name = "✅ 保存成功"
                else:
                    # 标签已被合并，加载合并后的标签（使用新标签名）
                    load_tag_info(new_tag_name)
                    save_tag_name_btn.name = "✅ 合并成功"
                
                # 刷新标签选项
                tag_search_input.options = get_tag_search_options()
            except Exception as e:
                save_tag_name_btn.name = f"❌ 错误: {str(e)}"
            finally:
                save_tag_name_btn.disabled = False
                # 2秒后恢复按钮文本
                import threading
                def reset_button():
                    import time
                    time.sleep(config.API_DELAY_MEDIUM)
                    save_tag_name_btn.name = "保存标签名称"
                threading.Thread(target=reset_button, daemon=True).start()
        
        def on_delete_tag(event):
            """删除标签"""
            if not current_tag_id[0]:
                delete_tag_btn.name = "❌ 请先选择标签"
                return
            
            try:
                # 获取标签名称用于显示
                tags = self.database.get_all_tags()
                tag_name = ""
                for tag in tags:
                    if tag["tag_id"] == current_tag_id[0]:
                        tag_name = tag["tag_name"]
                        break
                
                # 确认删除
                delete_tag_btn.disabled = True
                delete_tag_btn.name = "⏳ 删除中..."
                # 删除标签（会自动删除所有 paper_tag 关联记录）
                self.database.delete_tag(current_tag_id[0])
                # 清空显示
                tag_info_pane.object = "<div style='padding: 20px; color: green;'>标签已删除</div>"
                papers_list_pane.object = "<div style='padding: 20px; color: #666;'>暂无关联论文</div>"
                current_tag_id[0] = None
                edit_section.visible = False
                # 刷新标签选项
                tag_search_input.options = get_tag_search_options()
                tag_search_input.value = ""
                delete_tag_btn.name = "✅ 删除成功"
            except Exception as e:
                delete_tag_btn.name = f"❌ 错误: {str(e)}"
            finally:
                delete_tag_btn.disabled = False
                # 2秒后恢复按钮文本
                import threading
                def reset_button():
                    import time
                    time.sleep(config.API_DELAY_MEDIUM)
                    delete_tag_btn.name = "删除标签"
                threading.Thread(target=reset_button, daemon=True).start()
        
        tag_search_input.param.watch(on_search_change, 'value')
        save_tag_name_btn.on_click(on_save_tag_name)
        delete_tag_btn.on_click(on_delete_tag)
        
        # 创建布局
        layout = pn.Column(
            pn.Row(
                tag_search_input,
                sizing_mode='stretch_width'
            ),
            pn.Spacer(height=10),
            tag_info_pane,
            pn.Spacer(height=10),
            edit_section,
            pn.Spacer(height=10),
            papers_list_pane,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        return layout
    
    def create_edit_watched_companies_view(self):
        """创建关注公司编辑视图"""
        # 按名称分组的数据
        grouped_data = {}
        
        # 刷新数据函数
        def refresh_table():
            """刷新表格数据，按名称分组"""
            try:
                companies = self.database.get_all_watched_companies()
                grouped_data.clear()
                
                # 按名称分组
                for item in companies:
                    name = item["name"]
                    if name not in grouped_data:
                        grouped_data[name] = []
                    grouped_data[name].append({
                        "id": item["id"],
                        "match_rule": item["match_rule"]
                    })
                
                # 创建表格数据
                data = []
                for name, rules in sorted(grouped_data.items()):
                    rules_str = ", ".join([r["match_rule"] for r in rules])
                    data.append({
                        "名称": name,
                        "匹配规则": rules_str,
                        "规则数量": len(rules)
                    })
                
                if data:
                    df = pd.DataFrame(data)
                    table.value = df
                else:
                    table.value = pd.DataFrame(columns=["名称", "匹配规则", "规则数量"])
            except Exception as e:
                print(f"刷新表格时出错: {e}")
        
        # 创建表格（禁用编辑，确保可以正常选中）
        table = pn.widgets.Tabulator(
            pd.DataFrame(columns=["名称", "匹配规则", "规则数量"]),
            layout="fit_data_table",
            selectable=1,
            show_index=False,
            pagination="local",
            page_size=20,
            height=400,
            sizing_mode='stretch_width',
            disabled=True,  # 禁用编辑，确保可以正常选中行
            editors={}  # 禁用所有列的编辑功能
        )
        
        # 添加新公司的输入框
        new_name_input = pn.widgets.TextInput(
            name="新公司名称",
            placeholder="例如: 蔚来",
            sizing_mode='stretch_width',
            width=config.INPUT_WIDTH_DEFAULT
        )
        new_match_rule_input = pn.widgets.TextInput(
            name="匹配规则",
            placeholder="例如: NIO 或 NIO* (支持通配符 * 和 ?)",
            sizing_mode='stretch_width',
            width=config.INPUT_WIDTH_DEFAULT
        )
        add_new_btn = pn.widgets.Button(name="添加新公司", button_type="primary", width=150)
        
        # 编辑区域 - 显示选中公司的所有匹配规则
        edit_section = pn.Column(
            sizing_mode='stretch_width',
            styles={'background': '#f0f7ff', 'padding': '15px', 'border-radius': '8px', 'border': '1px solid #b3d9ff'},
            visible=False
        )
        
        # 当前选中的公司名称
        current_name = [None]
        
        def refresh_rules_display():
            """刷新匹配规则显示"""
            edit_section.clear()
            if current_name[0] and current_name[0] in grouped_data:
                rules = grouped_data[current_name[0]]
                
                # 标题
                edit_section.append(pn.pane.HTML("<h3 style='margin-top: 0;'>编辑公司配置</h3>", sizing_mode='stretch_width'))
                
                # 显示公司名称（可编辑）
                name_input = pn.widgets.TextInput(
                    name="公司名称",
                    value=current_name[0],
                    sizing_mode='stretch_width',
                    width=config.INPUT_WIDTH_DEFAULT
                )
                save_name_btn = pn.widgets.Button(name="保存名称", button_type="primary", width=120)
                
                def save_name(event):
                    """保存修改后的名称"""
                    try:
                        new_name = name_input.value.strip()
                        if not new_name:
                            pn.state.notifications.error("公司名称不能为空", duration=3000)
                            return
                        if new_name == current_name[0]:
                            return
                        # 更新所有该名称的记录
                        for rule_item in rules:
                            self.database.update_watched_company(rule_item["id"], name=new_name)
                        current_name[0] = new_name
                        refresh_table()
                        refresh_rules_display()
                        pn.state.notifications.success("名称已更新", duration=2000)
                    except Exception as e:
                        pn.state.notifications.error(f"更新失败: {str(e)}", duration=3000)
                
                save_name_btn.on_click(save_name)
                edit_section.append(pn.Row(name_input, save_name_btn, sizing_mode='stretch_width'))
                
                # 显示所有匹配规则
                edit_section.append(pn.pane.HTML("<h4 style='margin-top: 15px;'>匹配规则列表:</h4>", sizing_mode='stretch_width'))
                
                for rule_item in rules:
                    rule_id = rule_item["id"]
                    match_rule = rule_item["match_rule"]
                    
                    delete_btn = pn.widgets.Button(
                        name=f"删除: {match_rule}",
                        button_type="danger",
                        width=200
                    )
                    
                    def create_delete_handler(rid, rule):
                        def delete_handler(event):
                            try:
                                self.database.delete_watched_company(rid)
                                refresh_table()
                                refresh_rules_display()
                                pn.state.notifications.success(f"已删除规则: {rule}", duration=2000)
                            except Exception as e:
                                pn.state.notifications.error(f"删除失败: {str(e)}", duration=3000)
                        return delete_handler
                    
                    delete_btn.on_click(create_delete_handler(rule_id, match_rule))
                    edit_section.append(pn.Row(
                        pn.pane.HTML(f"<span style='padding: 8px; background: white; border-radius: 4px; margin-right: 10px;'>{match_rule}</span>", sizing_mode='fixed', width=400),
                        delete_btn,
                        sizing_mode='stretch_width'
                    ))
                
                # 添加新匹配规则的输入框
                edit_section.append(pn.pane.HTML("<h4 style='margin-top: 15px;'>添加新匹配规则:</h4>", sizing_mode='stretch_width'))
                new_rule_input = pn.widgets.TextInput(
                    name="新匹配规则",
                    placeholder="例如: NIO* (支持通配符 * 和 ?)",
                    sizing_mode='stretch_width',
                    width=config.INPUT_WIDTH_DEFAULT
                )
                add_rule_btn = pn.widgets.Button(name="添加规则", button_type="success", width=120)
                
                def add_rule(event):
                    """添加新的匹配规则"""
                    try:
                        new_rule = new_rule_input.value.strip()
                        if not new_rule:
                            pn.state.notifications.error("请输入匹配规则", duration=3000)
                            return
                        # 检查是否已存在
                        if any(r["match_rule"] == new_rule for r in grouped_data.get(current_name[0], [])):
                            pn.state.notifications.error("该匹配规则已存在", duration=3000)
                            return
                        self.database.add_watched_company(current_name[0], new_rule)
                        new_rule_input.value = ""
                        refresh_table()
                        refresh_rules_display()
                        pn.state.notifications.success("规则已添加", duration=2000)
                    except Exception as e:
                        pn.state.notifications.error(f"添加失败: {str(e)}", duration=3000)
                
                add_rule_btn.on_click(add_rule)
                edit_section.append(pn.Row(new_rule_input, add_rule_btn, sizing_mode='stretch_width'))
        
        def add_new_company(event):
            """添加新公司"""
            try:
                name = new_name_input.value.strip()
                match_rule = new_match_rule_input.value.strip()
                if not name or not match_rule:
                    pn.state.notifications.error("请输入公司名称和匹配规则", duration=3000)
                    return
                self.database.add_watched_company(name, match_rule)
                new_name_input.value = ""
                new_match_rule_input.value = ""
                refresh_table()
                pn.state.notifications.success("添加成功", duration=2000)
            except Exception as e:
                pn.state.notifications.error(f"添加失败: {str(e)}", duration=3000)
        
        def on_table_select(event):
            """处理表格选择事件"""
            if event.new:
                selected_row = event.new[0]
                row_data = table.value.iloc[selected_row]
                current_name[0] = row_data["名称"]
                refresh_rules_display()
                edit_section.visible = True
            else:
                current_name[0] = None
                edit_section.visible = False
        
        # 绑定事件
        add_new_btn.on_click(add_new_company)
        table.param.watch(on_table_select, "selection")
        
        # 初始化表格
        refresh_table()
        
        layout = pn.Column(
            pn.pane.HTML("<h2>编辑关注公司</h2>", sizing_mode='stretch_width'),
            pn.Row(new_name_input, new_match_rule_input, add_new_btn, sizing_mode='stretch_width'),
            pn.Spacer(height=10),
            table,
            pn.Spacer(height=10),
            edit_section,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        return layout
    
    def create_edit_watched_universities_view(self):
        """创建关注高校编辑视图"""
        # 按名称分组的数据
        grouped_data = {}
        
        # 刷新数据函数
        def refresh_table():
            """刷新表格数据，按名称分组"""
            try:
                universities = self.database.get_all_watched_universities()
                grouped_data.clear()
                
                # 按名称分组
                for item in universities:
                    name = item["name"]
                    if name not in grouped_data:
                        grouped_data[name] = []
                    grouped_data[name].append({
                        "id": item["id"],
                        "match_rule": item["match_rule"]
                    })
                
                # 创建表格数据
                data = []
                for name, rules in sorted(grouped_data.items()):
                    rules_str = ", ".join([r["match_rule"] for r in rules])
                    data.append({
                        "名称": name,
                        "匹配规则": rules_str,
                        "规则数量": len(rules)
                    })
                
                if data:
                    df = pd.DataFrame(data)
                    table.value = df
                else:
                    table.value = pd.DataFrame(columns=["名称", "匹配规则", "规则数量"])
            except Exception as e:
                print(f"刷新表格时出错: {e}")
        
        # 创建表格（禁用编辑，确保可以正常选中）
        table = pn.widgets.Tabulator(
            pd.DataFrame(columns=["名称", "匹配规则", "规则数量"]),
            layout="fit_data_table",
            selectable=1,
            show_index=False,
            pagination="local",
            page_size=20,
            height=400,
            sizing_mode='stretch_width',
            disabled=True,  # 禁用编辑，确保可以正常选中行
            editors={}  # 禁用所有列的编辑功能
        )
        
        # 添加新高校的输入框
        new_name_input = pn.widgets.TextInput(
            name="新高校名称",
            placeholder="例如: 清华大学",
            sizing_mode='stretch_width',
            width=config.INPUT_WIDTH_DEFAULT
        )
        new_match_rule_input = pn.widgets.TextInput(
            name="匹配规则",
            placeholder="例如: Tsinghua University 或 Tsinghua* (支持通配符 * 和 ?)",
            sizing_mode='stretch_width',
            width=config.INPUT_WIDTH_DEFAULT
        )
        add_new_btn = pn.widgets.Button(name="添加新高校", button_type="primary", width=150)
        
        # 编辑区域 - 显示选中高校的所有匹配规则
        edit_section = pn.Column(
            sizing_mode='stretch_width',
            styles={'background': '#f0f7ff', 'padding': '15px', 'border-radius': '8px', 'border': '1px solid #b3d9ff'},
            visible=False
        )
        
        # 当前选中的高校名称
        current_name = [None]
        
        def refresh_rules_display():
            """刷新匹配规则显示"""
            edit_section.clear()
            if current_name[0] and current_name[0] in grouped_data:
                rules = grouped_data[current_name[0]]
                
                # 标题
                edit_section.append(pn.pane.HTML("<h3 style='margin-top: 0;'>编辑高校配置</h3>", sizing_mode='stretch_width'))
                
                # 显示高校名称（可编辑）
                name_input = pn.widgets.TextInput(
                    name="高校名称",
                    value=current_name[0],
                    sizing_mode='stretch_width',
                    width=config.INPUT_WIDTH_DEFAULT
                )
                save_name_btn = pn.widgets.Button(name="保存名称", button_type="primary", width=120)
                
                def save_name(event):
                    """保存修改后的名称"""
                    try:
                        new_name = name_input.value.strip()
                        if not new_name:
                            pn.state.notifications.error("高校名称不能为空", duration=3000)
                            return
                        if new_name == current_name[0]:
                            return
                        # 更新所有该名称的记录
                        for rule_item in rules:
                            self.database.update_watched_university(rule_item["id"], name=new_name)
                        current_name[0] = new_name
                        refresh_table()
                        refresh_rules_display()
                        pn.state.notifications.success("名称已更新", duration=2000)
                    except Exception as e:
                        pn.state.notifications.error(f"更新失败: {str(e)}", duration=3000)
                
                save_name_btn.on_click(save_name)
                edit_section.append(pn.Row(name_input, save_name_btn, sizing_mode='stretch_width'))
                
                # 显示所有匹配规则
                edit_section.append(pn.pane.HTML("<h4 style='margin-top: 15px;'>匹配规则列表:</h4>", sizing_mode='stretch_width'))
                
                for rule_item in rules:
                    rule_id = rule_item["id"]
                    match_rule = rule_item["match_rule"]
                    
                    delete_btn = pn.widgets.Button(
                        name=f"删除: {match_rule}",
                        button_type="danger",
                        width=200
                    )
                    
                    def create_delete_handler(rid, rule):
                        def delete_handler(event):
                            try:
                                self.database.delete_watched_university(rid)
                                refresh_table()
                                refresh_rules_display()
                                pn.state.notifications.success(f"已删除规则: {rule}", duration=2000)
                            except Exception as e:
                                pn.state.notifications.error(f"删除失败: {str(e)}", duration=3000)
                        return delete_handler
                    
                    delete_btn.on_click(create_delete_handler(rule_id, match_rule))
                    edit_section.append(pn.Row(
                        pn.pane.HTML(f"<span style='padding: 8px; background: white; border-radius: 4px; margin-right: 10px;'>{match_rule}</span>", sizing_mode='fixed', width=400),
                        delete_btn,
                        sizing_mode='stretch_width'
                    ))
                
                # 添加新匹配规则的输入框
                edit_section.append(pn.pane.HTML("<h4 style='margin-top: 15px;'>添加新匹配规则:</h4>", sizing_mode='stretch_width'))
                new_rule_input = pn.widgets.TextInput(
                    name="新匹配规则",
                    placeholder="例如: Tsinghua* (支持通配符 * 和 ?)",
                    sizing_mode='stretch_width',
                    width=config.INPUT_WIDTH_DEFAULT
                )
                add_rule_btn = pn.widgets.Button(name="添加规则", button_type="success", width=120)
                
                def add_rule(event):
                    """添加新的匹配规则"""
                    try:
                        new_rule = new_rule_input.value.strip()
                        if not new_rule:
                            pn.state.notifications.error("请输入匹配规则", duration=3000)
                            return
                        # 检查是否已存在
                        if any(r["match_rule"] == new_rule for r in grouped_data.get(current_name[0], [])):
                            pn.state.notifications.error("该匹配规则已存在", duration=3000)
                            return
                        self.database.add_watched_university(current_name[0], new_rule)
                        new_rule_input.value = ""
                        refresh_table()
                        refresh_rules_display()
                        pn.state.notifications.success("规则已添加", duration=2000)
                    except Exception as e:
                        pn.state.notifications.error(f"添加失败: {str(e)}", duration=3000)
                
                add_rule_btn.on_click(add_rule)
                edit_section.append(pn.Row(new_rule_input, add_rule_btn, sizing_mode='stretch_width'))
        
        def add_new_university(event):
            """添加新高校"""
            try:
                name = new_name_input.value.strip()
                match_rule = new_match_rule_input.value.strip()
                if not name or not match_rule:
                    pn.state.notifications.error("请输入高校名称和匹配规则", duration=3000)
                    return
                self.database.add_watched_university(name, match_rule)
                new_name_input.value = ""
                new_match_rule_input.value = ""
                refresh_table()
                pn.state.notifications.success("添加成功", duration=2000)
            except Exception as e:
                pn.state.notifications.error(f"添加失败: {str(e)}", duration=3000)
        
        def on_table_select(event):
            """处理表格选择事件"""
            if event.new:
                selected_row = event.new[0]
                row_data = table.value.iloc[selected_row]
                current_name[0] = row_data["名称"]
                refresh_rules_display()
                edit_section.visible = True
            else:
                current_name[0] = None
                edit_section.visible = False
        
        # 绑定事件
        add_new_btn.on_click(add_new_university)
        table.param.watch(on_table_select, "selection")
        
        # 初始化表格
        refresh_table()
        
        layout = pn.Column(
            pn.pane.HTML("<h2>编辑关注高校</h2>", sizing_mode='stretch_width'),
            pn.Row(new_name_input, new_match_rule_input, add_new_btn, sizing_mode='stretch_width'),
            pn.Spacer(height=10),
            table,
            pn.Spacer(height=10),
            edit_section,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        return layout
    
    def create_edit_watched_authors_view(self):
        """创建关注作者编辑视图"""
        # 按名称分组的数据
        grouped_data = {}
        
        # 刷新数据函数
        def refresh_table():
            """刷新表格数据，按名称分组"""
            try:
                authors = self.database.get_all_watched_authors()
                grouped_data.clear()
                
                # 按名称分组
                for item in authors:
                    name = item["name"]
                    if name not in grouped_data:
                        grouped_data[name] = []
                    grouped_data[name].append({
                        "id": item["id"],
                        "match_rule": item["match_rule"]
                    })
                
                # 创建表格数据
                data = []
                for name, rules in sorted(grouped_data.items()):
                    rules_str = ", ".join([r["match_rule"] for r in rules])
                    data.append({
                        "名称": name,
                        "匹配规则": rules_str,
                        "规则数量": len(rules)
                    })
                
                if data:
                    df = pd.DataFrame(data)
                    table.value = df
                else:
                    table.value = pd.DataFrame(columns=["名称", "匹配规则", "规则数量"])
            except Exception as e:
                print(f"刷新表格时出错: {e}")
        
        # 创建表格（禁用编辑，确保可以正常选中）
        table = pn.widgets.Tabulator(
            pd.DataFrame(columns=["名称", "匹配规则", "规则数量"]),
            layout="fit_data_table",
            selectable=1,
            show_index=False,
            pagination="local",
            page_size=20,
            height=400,
            sizing_mode='stretch_width',
            disabled=True,  # 禁用编辑，确保可以正常选中行
            editors={}  # 禁用所有列的编辑功能
        )
        
        # 添加新作者的输入框
        new_name_input = pn.widgets.TextInput(
            name="新作者名称",
            placeholder="例如: 张三",
            sizing_mode='stretch_width',
            width=config.INPUT_WIDTH_DEFAULT
        )
        new_match_rule_input = pn.widgets.TextInput(
            name="匹配规则",
            placeholder="例如: Zhang San 或 Zhang* (支持通配符 * 和 ?)",
            sizing_mode='stretch_width',
            width=config.INPUT_WIDTH_DEFAULT
        )
        add_new_btn = pn.widgets.Button(name="添加新作者", button_type="primary", width=150)
        
        # 编辑区域 - 显示选中作者的所有匹配规则
        edit_section = pn.Column(
            sizing_mode='stretch_width',
            styles={'background': '#f0f7ff', 'padding': '15px', 'border-radius': '8px', 'border': '1px solid #b3d9ff'},
            visible=False
        )
        
        # 当前选中的作者名称
        current_name = [None]
        
        def refresh_rules_display():
            """刷新匹配规则显示"""
            edit_section.clear()
            if current_name[0] and current_name[0] in grouped_data:
                rules = grouped_data[current_name[0]]
                
                # 标题
                edit_section.append(pn.pane.HTML("<h3 style='margin-top: 0;'>编辑作者配置</h3>", sizing_mode='stretch_width'))
                
                # 显示作者名称（可编辑）
                name_input = pn.widgets.TextInput(
                    name="作者名称",
                    value=current_name[0],
                    sizing_mode='stretch_width',
                    width=config.INPUT_WIDTH_DEFAULT
                )
                save_name_btn = pn.widgets.Button(name="保存名称", button_type="primary", width=120)
                
                def save_name(event):
                    """保存修改后的名称"""
                    try:
                        new_name = name_input.value.strip()
                        if not new_name:
                            pn.state.notifications.error("作者名称不能为空", duration=3000)
                            return
                        if new_name == current_name[0]:
                            return
                        # 更新所有该名称的记录
                        for rule_item in rules:
                            self.database.update_watched_author(rule_item["id"], name=new_name)
                        current_name[0] = new_name
                        refresh_table()
                        refresh_rules_display()
                        pn.state.notifications.success("名称已更新", duration=2000)
                    except Exception as e:
                        pn.state.notifications.error(f"更新失败: {str(e)}", duration=3000)
                
                save_name_btn.on_click(save_name)
                edit_section.append(pn.Row(name_input, save_name_btn, sizing_mode='stretch_width'))
                
                # 显示所有匹配规则
                edit_section.append(pn.pane.HTML("<h4 style='margin-top: 15px;'>匹配规则列表:</h4>", sizing_mode='stretch_width'))
                
                for rule_item in rules:
                    rule_id = rule_item["id"]
                    match_rule = rule_item["match_rule"]
                    
                    delete_btn = pn.widgets.Button(
                        name=f"删除: {match_rule}",
                        button_type="danger",
                        width=200
                    )
                    
                    def create_delete_handler(rid, rule):
                        def delete_handler(event):
                            try:
                                self.database.delete_watched_author(rid)
                                refresh_table()
                                refresh_rules_display()
                                pn.state.notifications.success(f"已删除规则: {rule}", duration=2000)
                            except Exception as e:
                                pn.state.notifications.error(f"删除失败: {str(e)}", duration=3000)
                        return delete_handler
                    
                    delete_btn.on_click(create_delete_handler(rule_id, match_rule))
                    edit_section.append(pn.Row(
                        pn.pane.HTML(f"<span style='padding: 8px; background: white; border-radius: 4px; margin-right: 10px;'>{match_rule}</span>", sizing_mode='fixed', width=400),
                        delete_btn,
                        sizing_mode='stretch_width'
                    ))
                
                # 添加新匹配规则的输入框
                edit_section.append(pn.pane.HTML("<h4 style='margin-top: 15px;'>添加新匹配规则:</h4>", sizing_mode='stretch_width'))
                new_rule_input = pn.widgets.TextInput(
                    name="新匹配规则",
                    placeholder="例如: Zhang* (支持通配符 * 和 ?)",
                    sizing_mode='stretch_width',
                    width=config.INPUT_WIDTH_DEFAULT
                )
                add_rule_btn = pn.widgets.Button(name="添加规则", button_type="success", width=120)
                
                def add_rule(event):
                    """添加新的匹配规则"""
                    try:
                        new_rule = new_rule_input.value.strip()
                        if not new_rule:
                            pn.state.notifications.error("请输入匹配规则", duration=3000)
                            return
                        # 检查是否已存在
                        if any(r["match_rule"] == new_rule for r in grouped_data.get(current_name[0], [])):
                            pn.state.notifications.error("该匹配规则已存在", duration=3000)
                            return
                        self.database.add_watched_author(current_name[0], new_rule)
                        new_rule_input.value = ""
                        refresh_table()
                        refresh_rules_display()
                        pn.state.notifications.success("规则已添加", duration=2000)
                    except Exception as e:
                        pn.state.notifications.error(f"添加失败: {str(e)}", duration=3000)
                
                add_rule_btn.on_click(add_rule)
                edit_section.append(pn.Row(new_rule_input, add_rule_btn, sizing_mode='stretch_width'))
        
        def add_new_author(event):
            """添加新作者"""
            try:
                name = new_name_input.value.strip()
                match_rule = new_match_rule_input.value.strip()
                if not name or not match_rule:
                    pn.state.notifications.error("请输入作者名称和匹配规则", duration=3000)
                    return
                self.database.add_watched_author(name, match_rule)
                new_name_input.value = ""
                new_match_rule_input.value = ""
                refresh_table()
                pn.state.notifications.success("添加成功", duration=2000)
            except Exception as e:
                pn.state.notifications.error(f"添加失败: {str(e)}", duration=3000)
        
        def on_table_select(event):
            """处理表格选择事件"""
            if event.new:
                selected_row = event.new[0]
                row_data = table.value.iloc[selected_row]
                current_name[0] = row_data["名称"]
                refresh_rules_display()
                edit_section.visible = True
            else:
                current_name[0] = None
                edit_section.visible = False
        
        # 绑定事件
        add_new_btn.on_click(add_new_author)
        table.param.watch(on_table_select, "selection")
        
        # 初始化表格
        refresh_table()
        
        layout = pn.Column(
            pn.pane.HTML("<h2>编辑关注作者</h2>", sizing_mode='stretch_width'),
            pn.Row(new_name_input, new_match_rule_input, add_new_btn, sizing_mode='stretch_width'),
            pn.Spacer(height=10),
            table,
            pn.Spacer(height=10),
            edit_section,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        return layout
    
    def create_tag_matrix_view(self, top_level_tag_name):
        """为一级标签创建矩阵视图（横轴是标签，纵轴是时间）"""
        # 获取该一级标签下的所有标签（包括一级标签本身）
        tags = self.database.get_tags_by_prefix(top_level_tag_name)
        if not tags:
            return pn.pane.HTML(f"<div style='padding: 20px;'>一级标签 '{top_level_tag_name}' 下暂无标签</div>")
        
        # 获取所有标签的 ID
        tag_ids = [tag["tag_id"] for tag in tags]
        tag_id_to_name = {tag["tag_id"]: tag["tag_name"] for tag in tags}
        
        # 获取标签-论文矩阵数据
        matrix_data = self.database.get_tag_paper_matrix(tag_ids)
        if not matrix_data:
            return pn.pane.HTML(f"<div style='padding: 20px;'>一级标签 '{top_level_tag_name}' 下暂无论文</div>")
        
        # 创建 DataFrame
        df_raw = pd.DataFrame(matrix_data)
        
        # 创建透视表：横轴是标签名称，纵轴是 paper_id，cell 包含 alias
        alias_df = df_raw.pivot_table(
            index='paper_id',
            columns='tag_name',
            values='alias',
            aggfunc='first',
            fill_value=''
        )
        summary_df = df_raw.pivot_table(
            index='paper_id',
            columns='tag_name',
            values='summary',
            aggfunc='first',
            fill_value=''
        )
        full_name_df = df_raw.pivot_table(
            index='paper_id',
            columns='tag_name',
            values='full_name',
            aggfunc='first',
            fill_value=''
        )
        date_df = df_raw.pivot_table(
            index='paper_id',
            columns='tag_name',
            values='date',
            aggfunc='first',
            fill_value=''
        )
        arxiv_id_df = df_raw.pivot_table(
            index='paper_id',
            columns='tag_name',
            values='arxiv_id',
            aggfunc='first',
            fill_value=''
        )
        paper_url_df = df_raw.pivot_table(
            index='paper_id',
            columns='tag_name',
            values='paper_url',
            aggfunc='first',
            fill_value=''
        )
        
        # 重置索引，使 paper_id 成为普通列
        alias_df.reset_index(inplace=True)
        summary_df.reset_index(inplace=True)
        full_name_df.reset_index(inplace=True)
        date_df.reset_index(inplace=True)
        arxiv_id_df.reset_index(inplace=True)
        paper_url_df.reset_index(inplace=True)
        
        # 创建合并的 DataFrame，包含 paper_id、date 和所有标签列
        # 先从 date_df 获取每个 paper_id 对应的 date（取第一个非空值）
        paper_date_map = {}
        for paper_id in date_df['paper_id']:
            # 找到该 paper_id 对应的第一个非空 date
            paper_row = date_df[date_df['paper_id'] == paper_id].iloc[0]
            for col in date_df.columns:
                if col != 'paper_id' and paper_row[col]:
                    paper_date_map[paper_id] = paper_row[col]
                    break
        
        tag_df = alias_df[['paper_id']].copy()
        # 添加 date 列
        tag_df['date'] = tag_df['paper_id'].map(paper_date_map).fillna('')
        
        # 按照标签名称排序（确保一级标签在前）
        tag_names_sorted = sorted(tag_id_to_name.values(), key=lambda x: (x != top_level_tag_name, x))
        
        # 遍历所有标签列，组合 alias（超链接）和 summary
        # 包含一级标签本身（如果它有数据的话）
        for tag_name in tag_names_sorted:
            # 检查该标签是否在所有必要的 DataFrame 中都存在
            if tag_name not in alias_df.columns:
                continue
            
            # 使用 tag_df 的 paper_id 作为基准，确保长度匹配
            # 直接使用 tag_df 的索引和列，确保长度一致
            # 创建映射字典，以 paper_id 为键
            alias_map = dict(zip(alias_df['paper_id'], alias_df[tag_name]))
            summary_map = dict(zip(summary_df['paper_id'], summary_df[tag_name])) if tag_name in summary_df.columns else {}
            full_name_map = dict(zip(full_name_df['paper_id'], full_name_df[tag_name])) if tag_name in full_name_df.columns else {}
            arxiv_id_map = dict(zip(arxiv_id_df['paper_id'], arxiv_id_df[tag_name])) if tag_name in arxiv_id_df.columns else {}
            paper_url_map = dict(zip(paper_url_df['paper_id'], paper_url_df[tag_name])) if tag_name in paper_url_df.columns else {}
            
            # 创建组合的 HTML 内容，使用 Series 确保索引对齐
            # 直接使用 tag_df 的索引，确保长度匹配
            # 获取 tag_df 的 paper_id 列（确保顺序和索引一致）
            paper_ids_series = tag_df['paper_id']
            
            # 使用 apply 方法，确保索引对齐
            def generate_cell_for_paper(paper_id):
                alias = alias_map.get(paper_id, '')
                summary = summary_map.get(paper_id, '')
                full_name = full_name_map.get(paper_id, '')
                arxiv_id = arxiv_id_map.get(paper_id, '')
                paper_url = paper_url_map.get(paper_id, '')
                
                if alias or full_name:  # 如果有 alias 或 full_name
                    # 获取 hover 信息
                    hover_info = get_paper_hover_info(paper_id, self.paper_info_map, self.database)
                    
                    # 使用传入的 arxiv_id 和 paper_url，如果没有则使用 hover_info 中的
                    final_arxiv_id = arxiv_id or hover_info["arxiv_id"]
                    final_paper_url = paper_url or hover_info["paper_url"]
                    
                    # 生成链接和 tooltip
                    paper_link = generate_paper_link(final_arxiv_id, final_paper_url) if final_arxiv_id or final_paper_url else "#"
                    title_attr = generate_tooltip(
                        hover_info["full_name"] or full_name,
                        hover_info["summary"] or summary,
                        hover_info["company_names"],
                        hover_info["university_names"],
                        hover_info["tag_names"],
                        hover_info["date"],
                        hover_info["author_names"],
                        hover_info["paper_id"]
                    )
                    
                    # 生成单元格内容
                    cell_content = generate_cell_content(alias, full_name, paper_link, title_attr)
                else:
                    cell_content = ''
                return cell_content
            
            # 使用 apply 确保索引对齐
            combined_values = paper_ids_series.apply(generate_cell_for_paper)
            
            # 确保索引完全匹配
            combined_values = combined_values.reindex(tag_df.index, fill_value='')
            tag_df[tag_name] = combined_values
        
        # 按 date 倒序排序，然后按 paper_id 倒序排序（空值排在最后）
        tag_df = tag_df.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
        
        # 如果启用了聚合模式，将相同 date 的工作合并为一行
        if self.group_by_date and 'date' in tag_df.columns:
            # 按 date 分组
            grouped = tag_df.groupby('date', dropna=False)
            merged_rows = []
            
            for date, group in grouped:
                if pd.isna(date) or date == '':
                    # 对于空日期，保持原样
                    merged_rows.extend(group.to_dict('records'))
                else:
                    # 合并相同日期的行
                    merged_row = {'date': date}
                    
                    # 对于每个列，合并内容
                    for col in tag_df.columns:
                        if col == 'date':
                            continue
                        
                        # 收集该列的所有非空值
                        values = []
                        for _, row in group.iterrows():
                            val = row[col]
                            if pd.notna(val) and str(val).strip():
                                values.append(str(val))
                        
                        # 如果有多个值，用 <br> 连接；如果只有一个值，直接使用
                        if len(values) > 1:
                            merged_row[col] = '<br>'.join(values)
                        elif len(values) == 1:
                            merged_row[col] = values[0]
                        else:
                            merged_row[col] = ''
                    
                    merged_rows.append(merged_row)
            
            # 重新创建 DataFrame
            tag_df = pd.DataFrame(merged_rows)
            
            # 重新排序（按 date 倒序）
            if len(tag_df) > 0:
                tag_df = tag_df.sort_values('date', ascending=False, na_position='last').copy()
        
        # 过滤掉所有值都为空字符串的标签列
        # 检查每个标签列是否至少有一个非空值（排除空字符串和只包含空白字符的值）
        columns_to_keep = ['paper_id', 'date']  # 始终保留这两列
        for col in tag_df.columns:
            if col in ['paper_id', 'date']:
                continue
            # 检查该列是否有非空数据
            # 对于 HTML 内容，需要检查是否所有值都是空字符串
            col_values = tag_df[col].astype(str)
            # 移除 HTML 标签后检查是否为空（简单检查，移除常见的 HTML 标签）
            non_empty_values = col_values.str.replace(r'<[^>]+>', '', regex=True).str.strip()
            # 如果至少有一个非空值，保留该列
            if (non_empty_values != '').any():
                columns_to_keep.append(col)
        
        # 只保留有数据的列
        tag_df = tag_df[columns_to_keep].copy()
        
        # 创建列名映射：将标签名中的 '.' 替换为换行符用于显示
        # 但保留原始列名用于数据访问
        column_definitions = []
        for col in tag_df.columns:
            if col == 'paper_id':
                column_definitions.append({
                    'field': col,
                    'title': col,
                    'width': 120,
                    'frozen': True,
                    'headerSort': True,
                    'resizable': True,
                })
            elif col == 'date':
                column_definitions.append({
                    'field': col,
                    'title': col,
                    'headerSort': True,
                    'resizable': True,
                })
            else:
                # 将标签名中的 '.' 替换为换行符用于显示
                parts = col.split('.')
                display_title_html = '<br>'.join(parts)
                column_definitions.append({
                    'field': col,
                    'title': display_title_html,  # 直接在 title 中使用 HTML
                    'headerSort': True,
                    'resizable': True,
                    'formatter': 'html',
                })
        
        # 创建表格
        tag_table = pn.widgets.Tabulator(
            tag_df,
            pagination='remote',
            page_size=100,
            sizing_mode='stretch_width',
            height=config.TABLE_HEIGHT_DEFAULT,
            selectable=False,
            show_index=False,
            layout='fit_data_stretch',
            theme='bootstrap5',
            frozen_columns=['paper_id'],  # 冻结 paper_id 列
            styles={
                'table': {'font-size': '11px'},
            },
            formatters={
                col: {'type': 'html'} for col in tag_df.columns if col != 'date'
            },
            configuration={
                'columns': column_definitions
            }
        )
        
        # 添加自定义 CSS 样式
        css_pane = get_css_pane()
        
        # 创建聚合按钮
        group_button_text = '✅ 聚合相同日期' if self.group_by_date else '📋 聚合相同日期'
        group_button = pn.widgets.Button(
            name=group_button_text,
            button_type='primary' if self.group_by_date else 'light',
            width=140
        )
        
        # 统计信息（包含按钮）
        num_tags = len(tag_names_sorted)
        num_papers = len(df_raw['paper_id'].unique())
        stats_html = f"""
        <div style="padding: 8px 15px; background: {config.GRADIENT_PURPLE}; border-radius: {config.BORDER_RADIUS_LARGE}; color: {config.TEXT_COLOR_WHITE}; display: flex; align-items: center; justify-content: space-between; gap: 30px;">
            <div style="display: flex; align-items: center; gap: 30px;">
                <span style="font-size: 14px; font-weight: bold;">📊 统计:</span>
                <span style="font-size: 13px;">一级标签: <strong>{html.escape(top_level_tag_name)}</strong></span>
                <span style="font-size: 13px;">子标签数量: <strong>{num_tags}</strong></span>
                <span style="font-size: 13px;">论文数量: <strong>{num_papers}</strong></span>
            </div>
        </div>
        """
        stats = pn.pane.HTML(stats_html, sizing_mode='stretch_width')
        
        # 创建统计和按钮行
        stats_row = pn.Row(
            stats,
            group_button,
            sizing_mode='stretch_width',
            align='center'
        )
        
        layout = pn.Column(
            css_pane,
            stats_row,
            pn.Spacer(height=10),
            tag_table,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        def toggle_group_by_date(event):
            """切换聚合模式"""
            self.group_by_date = not self.group_by_date
            
            # 重新创建整个 tag_matrix_view（因为需要重新生成数据）
            new_view = self.create_tag_matrix_view(top_level_tag_name)
            
            # 更新字典中的视图
            if hasattr(self, 'tag_matrix_views_dict') and self.tag_matrix_views_dict:
                self.tag_matrix_views_dict[top_level_tag_name] = new_view
            
            # 更新布局中的表格对象
            try:
                # 找到表格在布局中的位置并替换
                old_table = tag_table
                new_table = new_view.tag_table
                for i, obj in enumerate(layout.objects):
                    if obj is old_table:
                        layout.objects[i] = new_table
                        break
                # 更新保存的引用
                if hasattr(layout, 'tag_table'):
                    layout.tag_table = new_table
                if hasattr(layout, 'tag_df'):
                    layout.tag_df = new_view.tag_df
            except Exception as e:
                # 如果上面的方法失败，尝试直接更新 value
                try:
                    if hasattr(layout, 'tag_table') and layout.tag_table:
                        layout.tag_table.value = new_view.tag_table.value
                        layout.tag_df = new_view.tag_df
                except:
                    pass
            
            # 更新 all_tabs_info 中的视图引用（如果存在）
            if hasattr(self, 'all_tabs_info'):
                # tag view 的 tab_id 格式是 "tag_" + tag_name.replace(".", "_").replace(" ", "_").replace("-", "_")
                tag_id = "tag_" + top_level_tag_name.replace(".", "_").replace(" ", "_").replace("-", "_")
                if tag_id in self.all_tabs_info:
                    self.all_tabs_info[tag_id]['view'] = new_view
            
            # 如果当前显示的是这个 tag view，重新切换 tab 以刷新视图
            if hasattr(self, 'switch_tab'):
                try:
                    tag_id = "tag_" + top_level_tag_name.replace(".", "_").replace(" ", "_").replace("-", "_")
                    if hasattr(self, 'current_tab_content'):
                        # 重新切换 tab 以刷新视图
                        self.switch_tab(tag_id)
                except Exception as e:
                    # 如果重新切换失败，尝试直接更新 current_tab_content
                    try:
                        if hasattr(self, 'current_tab_content'):
                            self.current_tab_content.clear()
                            self.current_tab_content.append(new_view)
                    except:
                        pass
            
            # 更新按钮文本和样式
            group_button.name = '✅ 聚合相同日期' if self.group_by_date else '📋 聚合相同日期'
            group_button.button_type = 'primary' if self.group_by_date else 'light'
        
        group_button.on_click(toggle_group_by_date)
        
        # 保存表格和 DataFrame 引用以便刷新时更新
        layout.tag_table = tag_table
        layout.tag_df = tag_df
        layout.top_level_tag_name = top_level_tag_name
        layout.group_button = group_button  # 保存按钮引用
        
        return layout
    
    def create_tag_tree_view(self):
        """创建标签表格视图"""
        try:
            tags = self.database.get_all_tags()
        except Exception as e:
            print(f"Error loading tags: {e}")
            tags = []
        
        if not tags:
            return pn.pane.HTML("<div style='padding: 20px;'>暂无标签数据</div>")
        
        # 获取每个标签的论文数量
        tag_data = []
        for tag in tags:
            tag_id = tag["tag_id"]
            tag_name = tag["tag_name"]
            try:
                papers = self.database.get_papers_by_tag(tag_id)
                paper_count = len(papers)
            except:
                paper_count = 0
            
            tag_data.append({
                "Tag ID": tag_id,
                "Tag Name": tag_name,
                "Paper Count": paper_count
            })
        
        # 创建 DataFrame
        tag_df = pd.DataFrame(tag_data)
        
        # 创建论文列表显示区域
        paper_list_pane = pn.pane.HTML("<div style='padding: 20px; color: #666;'>点击表格中的标签查看关联论文</div>", sizing_mode='stretch_width')
        
        # 创建标签表格
        tag_table = pn.widgets.Tabulator(
            tag_df,
            pagination='remote',
            page_size=50,
            sizing_mode='stretch_width',
            height=config.TABLE_HEIGHT_SMALL,
            selectable=False,
            show_index=False,
            layout='fit_data_stretch',
            theme='bootstrap5',
            styles={
                'table': {'font-size': '12px'},
            }
        )
        
        # 保存引用以便刷新时更新
        self.tag_table = tag_table
        self.tag_df = tag_df
        self.paper_list_pane = paper_list_pane
        
        def on_tag_table_select(event):
            """选择标签时加载论文列表"""
            if not tag_table.selection:
                paper_list_pane.object = "<div style='padding: 20px; color: #666;'>请选择标签查看关联论文</div>"
                return
            
            # 获取选中的行
            selected_indices = tag_table.selection
            if not selected_indices:
                return
            
            # 获取第一个选中的标签
            selected_row = tag_df.iloc[selected_indices[0]]
            tag_id = selected_row["Tag ID"]
            tag_name = selected_row["Tag Name"]
            
            try:
                papers = self.database.get_papers_by_tag(tag_id)
                
                if not papers:
                    paper_list_pane.object = f"<div style='padding: 20px; color: #666;'>标签 \"{html.escape(tag_name)}\" 下暂无论文</div>"
                    return
                
                # 生成论文列表 HTML
                paper_items = []
                for paper in papers:
                    paper_id = paper["paper_id"]
                    arxiv_id = paper.get("arxiv_id")
                    paper_url = paper["paper_url"]
                    alias = paper["alias"]
                    full_name = paper["full_name"]
                    summary = paper["summary"]
                    
                    # 根据是否有 arxiv_id 生成链接
                    if arxiv_id:
                        paper_link = f"https://arxiv.org/abs/{arxiv_id}"
                    else:
                        paper_link = paper_url
                    
                    display_id = arxiv_id if arxiv_id else paper_id
                    
                    paper_html = f"""
                    <div class="paper-item">
                        <div>
                            <a href="{paper_link}" target="_blank" style="font-weight: bold; color: #1976d2; text-decoration: none;">
                                {html.escape(alias) if alias else html.escape(full_name)}
                            </a>
                            <span style="color: #666; font-size: 0.9em; margin-left: 10px;">({display_id})</span>
                        </div>
                        {f'<div class="paper-summary">{html.escape(summary)}</div>' if summary else ''}
                    </div>
                    """
                    paper_items.append(paper_html)
                
                paper_list_html = f"""
                <div class="paper-list">
                    <h3 style="margin-top: 0;">标签 "{html.escape(tag_name)}" 的关联论文 ({len(papers)} 篇)</h3>
                    {"".join(paper_items)}
                </div>
                """
                paper_list_pane.object = paper_list_html
            except Exception as e:
                paper_list_pane.object = f"<div style='padding: 20px; color: red;'>加载论文时出错: {str(e)}</div>"
        
        tag_table.param.watch(on_tag_table_select, 'selection')
        
        # 创建 CSS 样式
        css_pane = get_css_pane()
        
        # 创建布局
        layout = pn.Column(
            css_pane,
            tag_table,
            pn.Spacer(height=20),
            paper_list_pane,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        return layout
    
    def create_company_view(self):
        """创建关注公司工作视图"""
        # 延迟加载数据
        if not self._data_loaded:
            self.load_data()
        
        # 创建公司表格
        self.company_table = self.create_company_table()
        
        # 添加自定义 CSS 样式
        css_pane = get_css_pane()
        
        # 创建聚合按钮
        group_button_text = '✅ 聚合相同日期' if self.group_by_date else '📋 聚合相同日期'
        group_button = pn.widgets.Button(
            name=group_button_text,
            button_type='primary' if self.group_by_date else 'light',
            width=140
        )
        
        # 统计信息（包含按钮）
        if self.company_df is not None and len(self.company_df) > 0:
            num_companies = len(self.company_df.columns) - 1  # 减去 paper_id 列
            num_papers = len(self.company_df)
            stats_html = f"""
            <div style="padding: 8px 15px; background: {config.GRADIENT_PINK}; border-radius: {config.BORDER_RADIUS_LARGE}; color: {config.TEXT_COLOR_WHITE}; display: flex; align-items: center; justify-content: space-between; gap: 30px;">
                <div style="display: flex; align-items: center; gap: 30px;">
                    <span style="font-size: 14px; font-weight: bold;">📊 统计:</span>
                    <span style="font-size: 13px;">公司数量: <strong>{num_companies}</strong></span>
                    <span style="font-size: 13px;">论文数量: <strong>{num_papers}</strong></span>
                </div>
            </div>
            """
            stats = pn.pane.HTML(stats_html, sizing_mode='stretch_width')
        else:
            stats = pn.pane.Str("")
        
        # 创建统计和按钮行
        stats_row = pn.Row(
            stats,
            group_button,
            sizing_mode='stretch_width',
            align='center'
        )
        
        layout = pn.Column(
            css_pane,
            stats_row,
            pn.Spacer(height=10),
            self.company_table,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        def toggle_group_by_date(event):
            """切换聚合模式"""
            self.group_by_date = not self.group_by_date
            
            # 重新创建表格
            new_table = self.create_company_table()
            old_table = self.company_table
            self.company_table = new_table
            
            # 替换布局中的表格对象
            try:
                for i, obj in enumerate(layout.objects):
                    if obj is old_table:
                        layout.objects[i] = new_table
                        break
            except:
                pass
            
            # 更新 all_tabs_info 中的视图引用（如果存在）
            if hasattr(self, 'all_tabs_info') and 'companies' in self.all_tabs_info:
                self.all_tabs_info['companies']['view'] = layout
            
            # 如果当前显示的是公司视图，重新切换 tab 以刷新视图
            if hasattr(self, 'switch_tab'):
                try:
                    # 检查当前 tab ID（通过检查 current_tab_content 的内容）
                    if hasattr(self, 'current_tab_content'):
                        # 重新切换 tab 以刷新视图
                        self.switch_tab('companies')
                except Exception as e:
                    # 如果重新切换失败，尝试直接更新 current_tab_content
                    try:
                        if hasattr(self, 'current_tab_content'):
                            self.current_tab_content.clear()
                            self.current_tab_content.append(layout)
                    except:
                        pass
            
            # 更新按钮文本和样式
            group_button.name = '✅ 聚合相同日期' if self.group_by_date else '📋 聚合相同日期'
            group_button.button_type = 'primary' if self.group_by_date else 'light'
        
        group_button.on_click(toggle_group_by_date)
        
        return layout
    
    def create_author_view(self):
        """创建关注作者工作视图"""
        # 延迟加载数据
        if not self._data_loaded:
            self.load_data()
        
        # 创建作者表格
        self.author_table = self.create_author_table()
        
        # 添加自定义 CSS 样式
        css_pane = get_css_pane()
        
        # 创建聚合按钮
        group_button_text = '✅ 聚合相同日期' if self.group_by_date else '📋 聚合相同日期'
        group_button = pn.widgets.Button(
            name=group_button_text,
            button_type='primary' if self.group_by_date else 'light',
            width=140
        )
        
        # 统计信息（包含按钮）
        if self.author_df is not None and len(self.author_df) > 0:
            num_authors = len(self.author_df.columns) - 1  # 减去 paper_id 列
            num_papers = len(self.author_df)
            stats_html = f"""
            <div style="padding: 8px 15px; background: {config.GRADIENT_PINK}; border-radius: {config.BORDER_RADIUS_LARGE}; color: {config.TEXT_COLOR_WHITE}; display: flex; align-items: center; justify-content: space-between; gap: 30px;">
                <div style="display: flex; align-items: center; gap: 30px;">
                    <span style="font-size: 14px; font-weight: bold;">📊 统计:</span>
                    <span style="font-size: 13px;">作者数量: <strong>{num_authors}</strong></span>
                    <span style="font-size: 13px;">论文数量: <strong>{num_papers}</strong></span>
                </div>
            </div>
            """
            stats = pn.pane.HTML(stats_html, sizing_mode='stretch_width')
        else:
            stats = pn.pane.Str("")
        
        # 创建统计和按钮行
        stats_row = pn.Row(
            stats,
            group_button,
            sizing_mode='stretch_width',
            align='center'
        )
        
        layout = pn.Column(
            css_pane,
            stats_row,
            pn.Spacer(height=10),
            self.author_table,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        def toggle_group_by_date(event):
            """切换聚合模式"""
            self.group_by_date = not self.group_by_date
            
            # 重新创建表格
            new_table = self.create_author_table()
            old_table = self.author_table
            self.author_table = new_table
            
            # 替换布局中的表格对象
            try:
                for i, obj in enumerate(layout.objects):
                    if obj is old_table:
                        layout.objects[i] = new_table
                        break
            except:
                pass
            
            # 更新 all_tabs_info 中的视图引用（如果存在）
            if hasattr(self, 'all_tabs_info') and 'authors' in self.all_tabs_info:
                self.all_tabs_info['authors']['view'] = layout
            
            # 如果当前显示的是作者视图，重新切换 tab 以刷新视图
            if hasattr(self, 'switch_tab'):
                try:
                    # 检查当前 tab ID（通过检查 current_tab_content 的内容）
                    if hasattr(self, 'current_tab_content'):
                        # 重新切换 tab 以刷新视图
                        self.switch_tab('authors')
                except Exception as e:
                    # 如果重新切换失败，尝试直接更新 current_tab_content
                    try:
                        if hasattr(self, 'current_tab_content'):
                            self.current_tab_content.clear()
                            self.current_tab_content.append(layout)
                    except:
                        pass
            
            # 更新按钮文本和样式
            group_button.name = '✅ 聚合相同日期' if self.group_by_date else '📋 聚合相同日期'
            group_button.button_type = 'primary' if self.group_by_date else 'light'
        
        group_button.on_click(toggle_group_by_date)
        
        return layout
    
    def create_collect_view(self):
        """创建论文收集视图"""
        # 默认关键词
        default_keywords = [
            "3dgs",
            "world_model",
            "3d gaussian splatting",
            "3d gaussian",
            "novel view synthesis"
        ]
        
        # 关键词输入框（多行文本，每行一个关键词）
        keywords_textarea = pn.widgets.TextAreaInput(
            name="搜索关键词（每行一个）",
            value="\n".join(default_keywords),
            height=150,
            placeholder="每行输入一个关键词，例如：\n3dgs\nworld_model\n3d gaussian splatting",
            sizing_mode='stretch_width'
        )
        
        # 设置默认日期：开始日期为7天前，结束日期为今天
        default_start_date = datetime.now() - timedelta(days=7)
        default_end_date = datetime.now()
        
        collect_start_date = pn.widgets.DatePicker(
            name="开始日期",
            value=default_start_date.date(),
            width=config.INPUT_WIDTH_DATE
        )
        
        collect_end_date = pn.widgets.DatePicker(
            name="结束日期",
            value=default_end_date.date(),
            width=config.INPUT_WIDTH_DATE
        )
        
        collect_btn = pn.widgets.Button(
            name="📥 开始收集",
            button_type="primary",
            width=config.BUTTON_WIDTH_LARGE
        )
        
        # 收集结果弹窗
        collect_modal_content = pn.Column(
            pn.pane.HTML("<h3 style='margin-top: 0;'>论文收集结果</h3>", sizing_mode='stretch_width'),
            pn.pane.Str("", styles={'font-family': 'monospace', 'font-size': '12px', 'white-space': 'pre-wrap', 'background': '#f5f5f5', 'padding': '10px', 'border-radius': '5px', 'max-height': '400px', 'overflow-y': 'auto'}),
            pn.Row(
                pn.widgets.Button(name="✅ 插入数据库", button_type="success", width=150),
                pn.widgets.Button(name="❌ 取消", button_type="light", width=150),
                sizing_mode='stretch_width'
            ),
            sizing_mode='stretch_width',
            styles={'background': 'white', 'border': '2px solid #1976d2', 'border-radius': '8px', 'padding': '20px'},
            visible=False
        )
        
        collect_result_output = collect_modal_content[1]  # 获取输出面板
        collect_insert_btn = collect_modal_content[2][0]  # 获取插入按钮
        collect_cancel_btn = collect_modal_content[2][1]  # 获取取消按钮
        
        # 存储收集到的论文
        collected_papers = []
        
        def collect_papers(event):
            """收集论文"""
            try:
                collect_btn.disabled = True
                collect_btn.name = "⏳ 收集中..."
                
                # 获取关键词（从文本区域解析，每行一个）
                keywords_text = keywords_textarea.value.strip()
                if not keywords_text:
                    collect_result_output.object = "错误: 请输入至少一个关键词\n"
                    collect_modal_content.visible = True
                    collect_btn.name = "❌ 请输入关键词"
                    collect_btn.disabled = False
                    return
                
                keywords = [kw.strip() for kw in keywords_text.split('\n') if kw.strip()]
                if not keywords:
                    collect_result_output.object = "错误: 请输入至少一个关键词\n"
                    collect_modal_content.visible = True
                    collect_btn.name = "❌ 请输入关键词"
                    collect_btn.disabled = False
                    return
                
                # 获取日期范围
                start_date = collect_start_date.value
                end_date = collect_end_date.value
                
                # 创建论文收集器
                collector = PaperCollector(db_path=self.database._path)
                
                # 获取已存在的 arxiv_id
                existing_arxiv_ids = collector.get_existing_arxiv_ids()
                
                # 转换日期格式
                start_dt = None
                end_dt = None
                if start_date:
                    if isinstance(start_date, datetime):
                        start_dt = start_date
                    else:
                        start_dt = datetime.combine(start_date, datetime.min.time())
                if end_date:
                    if isinstance(end_date, datetime):
                        end_dt = end_date
                    else:
                        end_dt = datetime.combine(end_date, datetime.min.time())
                
                # 捕获输出
                output_buffer = io.StringIO()
                with redirect_stdout(output_buffer):
                    papers = collector.search_arxiv_papers(
                        keywords=keywords,
                        start_date=start_dt,
                        end_date=end_dt,
                        max_results=2000,
                        existing_arxiv_ids=existing_arxiv_ids
                    )
                
                # 保存收集到的论文
                collected_papers.clear()
                collected_papers.extend(papers)
                
                # 获取捕获的输出
                captured_output = output_buffer.getvalue()
                
                # 格式化结果显示
                result_text = captured_output if captured_output else "搜索完成，无输出。\n"
                if papers:
                    result_text += f"\n找到 {len(papers)} 篇论文:\n"
                    result_text += "=" * 80 + "\n"
                    for i, paper in enumerate(papers, 1):
                        result_text += f"\n[{i}] {paper['arxiv_id']}\n"
                        result_text += f"    标题: {paper['full_name']}\n"
                        result_text += f"    日期: {paper['date'] or 'N/A'}\n"
                        result_text += f"    URL: {paper['paper_url']}\n"
                        if paper['abstract']:
                            abstract_preview = paper['abstract'][:200].replace('\n', ' ')
                            result_text += f"    摘要: {abstract_preview}...\n"
                        result_text += "-" * 80 + "\n"
                else:
                    result_text += "\n没有找到符合条件的论文\n"
                
                collect_result_output.object = result_text
                
                # 显示弹窗
                collect_modal_content.visible = True
                
                collect_btn.name = "✅ 收集完成"
                
            except Exception as e:
                error_msg = f"收集出错: {str(e)}\n"
                import traceback
                traceback_output = traceback.format_exc()
                collect_result_output.object = error_msg + traceback_output
                collect_modal_content.visible = True
                collect_btn.name = f"❌ 错误: {str(e)}"
                print(f"Collect error: {e}")
                traceback.print_exc()
            finally:
                collect_btn.disabled = False
        
        def insert_collected_papers(event):
            """插入收集到的论文"""
            try:
                collect_insert_btn.disabled = True
                collect_insert_btn.name = "⏳ 插入中..."
                
                if not collected_papers:
                    collect_result_output.object = "没有论文需要插入\n"
                    return
                
                # 创建论文收集器
                collector = PaperCollector(db_path=self.database._path)
                
                # 插入论文
                success = collector.insert_papers(collected_papers)
                
                if success:
                    # 插入后清除缓存，确保数据及时更新
                    _clear_global_cache(self.db_path)
                    collect_result_output.object = f"成功插入 {len(collected_papers)} 篇论文\n"
                    collect_insert_btn.name = "✅ 插入成功"
                    # 关闭弹窗
                    collect_modal_content.visible = False
                    # 刷新数据
                    self._data_loaded = False
                    self.load_data()
                    # 清空收集的论文
                    collected_papers.clear()
                else:
                    collect_result_output.object = "插入失败\n"
                    collect_insert_btn.name = "❌ 插入失败"
                    
            except Exception as e:
                error_msg = f"插入出错: {str(e)}\n"
                import traceback
                traceback_output = traceback.format_exc()
                collect_result_output.object = error_msg + traceback_output
                collect_insert_btn.name = f"❌ 错误: {str(e)}"
                print(f"Insert collected papers error: {e}")
                traceback.print_exc()
            finally:
                collect_insert_btn.disabled = False
        
        def cancel_collect(event):
            """取消收集"""
            collect_modal_content.visible = False
            collected_papers.clear()
            collect_result_output.object = ""
        
        collect_btn.on_click(collect_papers)
        collect_insert_btn.on_click(insert_collected_papers)
        collect_cancel_btn.on_click(cancel_collect)
        
        # 创建布局
        layout = pn.Column(
            pn.pane.HTML("<h2>📥 论文收集</h2>", sizing_mode='stretch_width'),
            pn.Spacer(height=10),
            pn.pane.HTML("<p>通过 arXiv API 搜索论文并插入数据库</p>", sizing_mode='stretch_width'),
            pn.Spacer(height=10),
            keywords_textarea,
            pn.Spacer(height=10),
            pn.Row(
                collect_start_date,
                collect_end_date,
                collect_btn,
                sizing_mode='stretch_width',
                align='start'
            ),
            pn.Spacer(height=20),
            collect_modal_content,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        return layout
    
    def create_view(self):
        """创建完整的视图"""
        def refresh_data(event):
            # 刷新数据：检查数据库是否变化，如果变化才重新加载
            # 如果缓存仍然有效，直接使用缓存（避免不必要的数据库查询）
            if not _is_cache_valid(self.db_path):
                # 数据库已变化，清除缓存并重新加载
                _clear_global_cache(self.db_path)
                self._data_loaded = False
                self.load_data()
            else:
                # 数据库未变化，只需从缓存重新加载到当前实例
                self._data_loaded = False
                self.load_data()
            # 刷新论文视图
            if hasattr(self, 'table'):
                # 确保数据已排序
                if self.df is not None and len(self.df) > 0:
                    if 'Date' in self.df.columns:
                        self.df = self.df.sort_values(['Date', 'Paper ID'], ascending=[False, False], na_position='last').copy()
                    else:
                        self.df = self.df.sort_values('Paper ID', ascending=False).copy()
                self.df_filtered = self.df.copy() if self.df is not None else pd.DataFrame()
                # 如果启用了聚合模式，重新创建表格以应用聚合
                if self.group_by_date:
                    self.table = self.create_table()
                else:
                    # 只显示需要的列（排除辅助列）
                    display_cols = ["Paper ID", "Date", "Paper Link", "Alias", "Full Name", "Abstract", "Summary", "Companies", "Universities", "Tags", "Tags_Button"]
                    self.table.value = self.df_filtered[display_cols] if len(self.df_filtered) > 0 else self.df_filtered
            # 刷新公司视图
            if hasattr(self, 'company_table'):
                # 如果启用了聚合模式，重新创建表格
                if self.group_by_date:
                    self.company_table = self.create_company_table()
                else:
                    # 确保数据已排序
                    if self.company_df is not None and len(self.company_df) > 0:
                        if 'date' in self.company_df.columns:
                            self.company_df = self.company_df.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
                        else:
                            self.company_df = self.company_df.sort_values('paper_id', ascending=False).copy()
                    self.company_table.value = self.company_df
            # 刷新高校视图
            if hasattr(self, 'university_table'):
                # 如果启用了聚合模式，重新创建表格
                if self.group_by_date:
                    self.university_table = self.create_university_table()
                else:
                    # 确保数据已排序
                    if self.university_df is not None and len(self.university_df) > 0:
                        if 'date' in self.university_df.columns:
                            self.university_df = self.university_df.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
                        else:
                            self.university_df = self.university_df.sort_values('paper_id', ascending=False).copy()
                    self.university_table.value = self.university_df
            # 刷新标签表格视图
            try:
                # 重新加载标签数据
                tags = self.database.get_all_tags()
                
                if tags and hasattr(self, 'tag_table') and self.tag_table:
                    # 重新计算每个标签的论文数量
                    tag_data = []
                    for tag in tags:
                        tag_id = tag["tag_id"]
                        tag_name = tag["tag_name"]
                        try:
                            papers = self.database.get_papers_by_tag(tag_id)
                            paper_count = len(papers)
                        except:
                            paper_count = 0
                        
                        tag_data.append({
                            "Tag ID": tag_id,
                            "Tag Name": tag_name,
                            "Paper Count": paper_count
                        })
                    
                    # 更新 DataFrame
                    self.tag_df = pd.DataFrame(tag_data)
                    # 更新表格
                    self.tag_table.value = self.tag_df
                
                # 重置论文列表
                if hasattr(self, 'paper_list_pane') and self.paper_list_pane:
                    self.paper_list_pane.object = "<div style='padding: 20px; color: #666;'>点击表格中的标签查看关联论文</div>"
            except Exception as e:
                print(f"Error refreshing tag table view: {e}")
                import traceback
                traceback.print_exc()
            
            # 刷新一级标签矩阵视图
            try:
                if hasattr(self, 'tag_matrix_views_dict') and self.tag_matrix_views_dict:
                    for tag_name, tag_view in self.tag_matrix_views_dict.items():
                        if hasattr(tag_view, 'tag_table') and hasattr(tag_view, 'tag_df'):
                            # 重新创建该一级标签的矩阵数据
                            # 获取该一级标签下的所有标签
                            tags = self.database.get_tags_by_prefix(tag_name)
                            if not tags:
                                continue
                            
                            # 获取所有标签的 ID
                            tag_ids = [tag["tag_id"] for tag in tags]
                            
                            # 获取标签-论文矩阵数据
                            matrix_data = self.database.get_tag_paper_matrix(tag_ids)
                            if not matrix_data:
                                continue
                            
                            # 创建 DataFrame
                            df_raw = pd.DataFrame(matrix_data)
                            
                            # 创建透视表：横轴是标签名称，纵轴是 paper_id，cell 包含 alias
                            alias_df = df_raw.pivot_table(
                                index='paper_id',
                                columns='tag_name',
                                values='alias',
                                aggfunc='first',
                                fill_value=''
                            )
                            summary_df = df_raw.pivot_table(
                                index='paper_id',
                                columns='tag_name',
                                values='summary',
                                aggfunc='first',
                                fill_value=''
                            )
                            full_name_df = df_raw.pivot_table(
                                index='paper_id',
                                columns='tag_name',
                                values='full_name',
                                aggfunc='first',
                                fill_value=''
                            )
                            date_df = df_raw.pivot_table(
                                index='paper_id',
                                columns='tag_name',
                                values='date',
                                aggfunc='first',
                                fill_value=''
                            )
                            arxiv_id_df = df_raw.pivot_table(
                                index='paper_id',
                                columns='tag_name',
                                values='arxiv_id',
                                aggfunc='first',
                                fill_value=''
                            )
                            paper_url_df = df_raw.pivot_table(
                                index='paper_id',
                                columns='tag_name',
                                values='paper_url',
                                aggfunc='first',
                                fill_value=''
                            )
                            
                            # 重置索引，使 paper_id 成为普通列
                            alias_df.reset_index(inplace=True)
                            summary_df.reset_index(inplace=True)
                            full_name_df.reset_index(inplace=True)
                            date_df.reset_index(inplace=True)
                            arxiv_id_df.reset_index(inplace=True)
                            paper_url_df.reset_index(inplace=True)
                            
                            # 创建合并的 DataFrame，包含 paper_id、date 和所有标签列
                            # 先从 date_df 获取每个 paper_id 对应的 date（取第一个非空值）
                            paper_date_map = {}
                            for paper_id in date_df['paper_id']:
                                # 找到该 paper_id 对应的第一个非空 date
                                paper_row = date_df[date_df['paper_id'] == paper_id].iloc[0]
                                for col in date_df.columns:
                                    if col != 'paper_id' and paper_row[col]:
                                        paper_date_map[paper_id] = paper_row[col]
                                        break
                            
                            tag_id_to_name = {tag["tag_id"]: tag["tag_name"] for tag in tags}
                            tag_names_sorted = sorted(tag_id_to_name.values(), key=lambda x: (x != tag_name, x))
                            new_tag_df = alias_df[['paper_id']].copy()
                            # 添加 date 列
                            new_tag_df['date'] = new_tag_df['paper_id'].map(paper_date_map).fillna('')
                            
                            # 创建 paper_id 到各 DataFrame 行的映射，以便安全地获取值
                            # 使用 paper_id 作为键来对齐数据，而不是依赖索引
                            alias_dict = alias_df.set_index('paper_id').to_dict('index')
                            summary_dict = summary_df.set_index('paper_id').to_dict('index') if len(summary_df) > 0 else {}
                            full_name_dict = full_name_df.set_index('paper_id').to_dict('index') if len(full_name_df) > 0 else {}
                            arxiv_id_dict = arxiv_id_df.set_index('paper_id').to_dict('index') if len(arxiv_id_df) > 0 else {}
                            paper_url_dict = paper_url_df.set_index('paper_id').to_dict('index') if len(paper_url_df) > 0 else {}
                            
                            # 遍历所有标签列，组合 alias（超链接）和 summary
                            for tag_name_col in tag_names_sorted:
                                if tag_name_col not in alias_df.columns:
                                    continue
                                
                                # 创建组合的 HTML 内容
                                # 按照 new_tag_df 的 paper_id 顺序遍历
                                combined_values = []
                                for paper_id in new_tag_df['paper_id']:
                                    # 安全地从各个字典中获取值
                                    alias = alias_dict.get(paper_id, {}).get(tag_name_col, '') or ''
                                    summary = summary_dict.get(paper_id, {}).get(tag_name_col, '') or ''
                                    full_name = full_name_dict.get(paper_id, {}).get(tag_name_col, '') or ''
                                    arxiv_id = arxiv_id_dict.get(paper_id, {}).get(tag_name_col, '') or ''
                                    paper_url = paper_url_dict.get(paper_id, {}).get(tag_name_col, '') or ''
                                    
                                    if alias or full_name:
                                        # 获取 hover 信息
                                        hover_info = get_paper_hover_info(paper_id, self.paper_info_map, self.database)
                                        
                                        # 使用传入的 arxiv_id 和 paper_url，如果没有则使用 hover_info 中的
                                        final_arxiv_id = arxiv_id or hover_info["arxiv_id"]
                                        final_paper_url = paper_url or hover_info["paper_url"]
                                        
                                        # 生成链接和 tooltip
                                        paper_link = generate_paper_link(final_arxiv_id, final_paper_url) if final_arxiv_id or final_paper_url else "#"
                                        title_attr = generate_tooltip(
                                            hover_info["full_name"] or full_name,
                                            hover_info["summary"] or summary,
                                            hover_info["company_names"],
                                            hover_info["university_names"],
                                            hover_info["tag_names"],
                                            hover_info["date"],
                                            hover_info["author_names"],
                                            hover_info["paper_id"]
                                        )
                                        
                                        # 生成单元格内容
                                        cell_content = generate_cell_content(alias, full_name, paper_link, title_attr)
                                    else:
                                        cell_content = ''
                                    combined_values.append(cell_content)
                                
                                # 确保 combined_values 的长度与 new_tag_df 的行数一致
                                if len(combined_values) != len(new_tag_df):
                                    # 如果长度不匹配，记录警告并填充或截断
                                    print(f"Warning: Length mismatch for tag {tag_name_col}: combined_values={len(combined_values)}, new_tag_df={len(new_tag_df)}")
                                    if len(combined_values) < len(new_tag_df):
                                        # 填充缺失的值
                                        combined_values.extend([''] * (len(new_tag_df) - len(combined_values)))
                                    else:
                                        # 截断多余的值
                                        combined_values = combined_values[:len(new_tag_df)]
                                
                                new_tag_df[tag_name_col] = combined_values
                            
                            # 按 date 倒序排序，然后按 paper_id 倒序排序（空值排在最后）
                            new_tag_df = new_tag_df.sort_values(['date', 'paper_id'], ascending=[False, False], na_position='last').copy()
                            
                            # 如果启用了聚合模式，将相同 date 的工作合并为一行
                            if self.group_by_date and 'date' in new_tag_df.columns:
                                # 按 date 分组
                                grouped = new_tag_df.groupby('date', dropna=False)
                                merged_rows = []
                                
                                for date, group in grouped:
                                    if pd.isna(date) or date == '':
                                        # 对于空日期，保持原样
                                        merged_rows.extend(group.to_dict('records'))
                                    else:
                                        # 合并相同日期的行
                                        merged_row = {'date': date}
                                        
                                        # 对于每个列，合并内容
                                        for col in new_tag_df.columns:
                                            if col == 'date':
                                                continue
                                            
                                            # 收集该列的所有非空值
                                            values = []
                                            for _, row in group.iterrows():
                                                val = row[col]
                                                if pd.notna(val) and str(val).strip():
                                                    values.append(str(val))
                                            
                                            # 如果有多个值，用 <br> 连接；如果只有一个值，直接使用
                                            if len(values) > 1:
                                                merged_row[col] = '<br>'.join(values)
                                            elif len(values) == 1:
                                                merged_row[col] = values[0]
                                            else:
                                                merged_row[col] = ''
                                        
                                        merged_rows.append(merged_row)
                                
                                # 重新创建 DataFrame
                                new_tag_df = pd.DataFrame(merged_rows)
                                
                                # 重新排序（按 date 倒序）
                                if len(new_tag_df) > 0:
                                    new_tag_df = new_tag_df.sort_values('date', ascending=False, na_position='last').copy()
                            
                            # 过滤掉所有值都为空字符串的标签列
                            columns_to_keep = ['paper_id', 'date']  # 始终保留这两列
                            for col in new_tag_df.columns:
                                if col in ['paper_id', 'date']:
                                    continue
                                # 检查该列是否有非空数据
                                col_values = new_tag_df[col].astype(str)
                                non_empty_values = col_values.str.replace(r'<[^>]+>', '', regex=True).str.strip()
                                if (non_empty_values != '').any():
                                    columns_to_keep.append(col)
                            
                            # 只保留有数据的列
                            new_tag_df = new_tag_df[columns_to_keep].copy()
                            
                            # 更新表格
                            tag_view.tag_df = new_tag_df
                            tag_view.tag_table.value = new_tag_df
                            
                            # 更新统计信息
                            num_tags = len(tag_names_sorted)
                            num_papers = len(df_raw['paper_id'].unique())
                            stats_html = f"""
                            <div style="padding: 8px 15px; background: {config.GRADIENT_PURPLE}; border-radius: {config.BORDER_RADIUS_LARGE}; color: {config.TEXT_COLOR_WHITE}; display: flex; align-items: center; gap: 30px;">
                                <span style="font-size: 14px; font-weight: bold;">📊 统计:</span>
                                <span style="font-size: 13px;">一级标签: <strong>{html.escape(tag_name)}</strong></span>
                                <span style="font-size: 13px;">子标签数量: <strong>{num_tags}</strong></span>
                                <span style="font-size: 13px;">论文数量: <strong>{num_papers}</strong></span>
                            </div>
                            """
                            # 更新统计信息（stats 是 layout 的第二个子元素）
                            if len(tag_view.objects) > 1:
                                tag_view.objects[1].object = stats_html
            except Exception as e:
                print(f"Error refreshing tag matrix views: {e}")
                import traceback
                traceback.print_exc()
            
            # 检查是否有新增的一级标签，如果有则创建对应的视图
            try:
                if hasattr(self, 'tabs') and self.tabs:
                    # 获取当前所有一级标签
                    current_top_level_tags = self.database.get_top_level_tags()
                    current_tag_names = {tag["tag_name"] for tag in current_top_level_tags}
                    
                    # 获取已有的标签视图名称
                    existing_tag_names = set(self.tag_matrix_views_dict.keys()) if hasattr(self, 'tag_matrix_views_dict') else set()
                    
                    # 找出新增的一级标签
                    new_tag_names = current_tag_names - existing_tag_names
                    
                    # 为新增的一级标签创建视图并添加到 tabs
                    if new_tag_names:
                        # 获取当前 tabs 的所有对象
                        current_tabs = list(self.tabs.objects) if hasattr(self.tabs, 'objects') else []
                        
                        for tag_name in new_tag_names:
                            try:
                                # 创建新的标签矩阵视图
                                tag_view = self.create_tag_matrix_view(tag_name)
                                
                                # 添加到 tag_matrix_views_dict
                                if not hasattr(self, 'tag_matrix_views_dict'):
                                    self.tag_matrix_views_dict = {}
                                self.tag_matrix_views_dict[tag_name] = tag_view
                                
                                # 创建新的 tab 项（Panel Tabs 使用 (name, content) 元组）
                                new_tab = (f"🏷️ {tag_name}", tag_view)
                                
                                # 找到编辑论文 tab 的位置，在其后插入新标签 tab
                                edit_paper_index = None
                                for i, tab in enumerate(current_tabs):
                                    # Panel Tabs 的 objects 是 (name, content) 元组列表
                                    if isinstance(tab, tuple) and len(tab) >= 1:
                                        if tab[0] == "✏️ 编辑论文":
                                            edit_paper_index = i
                                            break
                                
                                # 如果找到了编辑论文 tab，在其后插入；否则追加到末尾
                                if edit_paper_index is not None:
                                    current_tabs.insert(edit_paper_index + 1, new_tab)
                                else:
                                    current_tabs.append(new_tab)
                                
                                print(f"已添加新的一级标签视图: {tag_name}")
                            except Exception as e:
                                print(f"创建新标签视图失败 {tag_name}: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # 更新 tabs 对象
                        if new_tag_names:
                            try:
                                # Panel 的 Tabs 组件支持通过 objects 属性更新
                                # 但需要确保格式正确：objects 应该是 Panel 对象的列表
                                # 实际上，Panel Tabs 的构造方式是通过 *args 传递 (name, content) 元组
                                # 我们可以尝试直接更新 objects 属性
                                if hasattr(self.tabs, 'objects'):
                                    # 尝试更新 objects
                                    self.tabs.objects = current_tabs
                                    print(f"已更新 tabs，新增 {len(new_tag_names)} 个标签视图")
                                else:
                                    # 如果不支持直接更新，打印提示信息
                                    print(f"检测到 {len(new_tag_names)} 个新的一级标签，但需要刷新页面才能看到新标签视图")
                                    print(f"新增标签: {', '.join(new_tag_names)}")
                            except Exception as e:
                                print(f"更新 tabs 失败: {e}")
                                print(f"检测到 {len(new_tag_names)} 个新的一级标签: {', '.join(new_tag_names)}")
                                print("提示：可能需要刷新页面才能看到新标签视图")
                                import traceback
                                traceback.print_exc()
            except Exception as e:
                print(f"检查新增一级标签时出错: {e}")
                import traceback
                traceback.print_exc()
        
        # InsertPaper 输入框和按钮
        paper_link_input = pn.widgets.TextInput(
            name="论文链接",
            placeholder="输入论文链接 (arXiv 或其他链接)",
            sizing_mode='stretch_width',
            width=config.INPUT_WIDTH_DEFAULT
        )
        
        # 日期输入框（用于非 arXiv 链接）
        date_input = pn.widgets.TextInput(
            name="日期 (yyyymm)",
            placeholder="yyyymm",
            sizing_mode='fixed',
            width=config.INPUT_WIDTH_DATE,
            height=config.INPUT_HEIGHT_DEFAULT,
            visible=False
        )
        
        # 日期提示文本
        date_hint = pn.pane.HTML(
            "<div style='color: #666; font-size: 12px; margin-top: -10px;'>非 arXiv 链接需要输入日期</div>",
            visible=False,
            margin=(0, 0, 5, 0)
        )
        
        # Tags 输入框
        tags_input = pn.widgets.TextInput(
            name="Tags",
            placeholder="输入标签，多个标签用逗号分割",
            sizing_mode='fixed',
            width=config.INPUT_WIDTH_DEFAULT,
            height=config.INPUT_HEIGHT_DEFAULT
        )
        
        # 监听链接输入，如果是非 arXiv 链接则显示日期输入框
        def on_link_change(event):
            paper_link = paper_link_input.value
            if paper_link:
                try:
                    parsed = parse_paper_link(paper_link)
                    if parsed and parsed.get('arxiv_id') is None:
                        # 非 arXiv 链接，显示日期输入框
                        date_input.visible = True
                        date_hint.visible = True
                    else:
                        # arXiv 链接，隐藏日期输入框
                        date_input.visible = False
                        date_hint.visible = False
                        date_input.value = ""  # 清空日期输入
                except:
                    pass
            else:
                date_input.visible = False
                date_hint.visible = False
        
        paper_link_input.param.watch(on_link_change, 'value')
        
        insert_paper_btn = pn.widgets.Button(name=config.BTN_TEXT_INSERT, button_type="warning", width=config.BUTTON_WIDTH_SMALL)
        
        def insert_paper(event):
            paper_link = paper_link_input.value
            if not paper_link:
                insert_paper_btn.name = "❌ 请输入论文链接"
                return
            
            try:
                insert_paper_btn.disabled = True
                insert_paper_btn.name = "⏳ 处理中..."
                
                # 解析链接
                parsed = parse_paper_link(paper_link)
                if not parsed:
                    insert_paper_btn.name = "❌ 无法解析链接"
                    return
                
                paper_id = parsed['paper_id']
                arxiv_id = parsed['arxiv_id']
                paper_url = parsed['paper_url']
                date = parsed.get('date')  # 从链接解析器获取日期
                
                # 如果是非 arXiv 链接且日期为空，检查用户输入的日期
                if arxiv_id is None:
                    user_date = date_input.value.strip()
                    if not user_date:
                        insert_paper_btn.name = "❌ 请输入日期 (yyyymm 格式)"
                        insert_paper_btn.disabled = False
                        return
                    
                    # 验证日期格式
                    import re
                    if not re.match(r'^\d{6}$', user_date):
                        insert_paper_btn.name = "❌ 日期格式错误 (应为 yyyymm)"
                        insert_paper_btn.disabled = False
                        return
                    
                    # 验证日期有效性（年份应该在合理范围内，月份应该在 01-12）
                    year = int(user_date[:4])
                    month = int(user_date[4:6])
                    if year < 1900 or year > 2100 or month < 1 or month > 12:
                        insert_paper_btn.name = "❌ 日期无效 (年份 1900-2100, 月份 01-12)"
                        insert_paper_btn.disabled = False
                        return
                    
                    date = user_date
                
                # 插入数据库（使用新格式）
                paper_data = {
                    "paper_id": paper_id,
                    "paper_url": paper_url,
                    "arxiv_id": arxiv_id,
                    "date": date,
                    "alias": None,
                    "full_name": None,
                    "abstract": None
                }
                self.database.insert_paper([paper_data])
                
                # 插入后清除缓存，确保数据及时更新
                _clear_global_cache(self.db_path)
                
                display_id = arxiv_id if arxiv_id else paper_id
                
                # 处理 tags（如果有输入）
                tags_str = tags_input.value.strip() if tags_input.value else ""
                if tags_str:
                    # 解析 tags（逗号分割）
                    tag_names = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
                    # 为论文添加 tags
                    for tag_name in tag_names:
                        try:
                            self.database.add_tag_to_paper(paper_id, tag_name)
                        except Exception as e:
                            print(f"添加标签失败 {tag_name} 到 {paper_id}: {e}")
                
                insert_paper_btn.name = f"✅ 已插入: {display_id}"
                paper_link_input.value = ""  # 清空输入框
                date_input.value = ""  # 清空日期输入框
                date_input.visible = False  # 隐藏日期输入框
                date_hint.visible = False  # 隐藏提示
                tags_input.value = ""  # 清空 tags 输入框
                
                # 立即刷新数据（显示插入的论文）
                refresh_data(None)
                
                # 异步执行 complete（只处理刚插入的论文）
                import threading
                
                def run_complete():
                    """在后台线程中执行 complete"""
                    try:
                        # 更新按钮状态
                        def update_btn_start():
                            insert_paper_btn.name = f"⏳ Complete 中: {display_id}"
                        
                        try:
                            pn.io.push(update_btn_start)
                        except:
                            try:
                                pn.state.execute(update_btn_start)
                            except:
                                update_btn_start()
                        
                        # 执行 complete
                        complete_log = self.completer.complete_single_paper(paper_id)
                        
                        # 更新按钮状态
                        def update_btn_complete():
                            insert_paper_btn.name = f"✅ Complete 完成: {display_id}"
                            insert_paper_btn.disabled = False
                            # 完成后刷新数据
                            refresh_data(None)
                        
                        try:
                            pn.io.push(update_btn_complete)
                        except:
                            try:
                                pn.state.execute(update_btn_complete)
                            except:
                                update_btn_complete()
                        
                    except Exception as e:
                        import traceback
                        error_msg = f"Complete 错误: {str(e)}\n{traceback.format_exc()}"
                        
                        def update_error():
                            insert_paper_btn.name = f"⚠️ Complete 失败: {display_id}"
                            insert_paper_btn.disabled = False
                        
                        try:
                            pn.io.push(update_error)
                        except:
                            try:
                                pn.state.execute(update_error)
                            except:
                                update_error()
                        
                        print(f"Complete error for {paper_id}: {e}")
                        traceback.print_exc()
                
                # 启动后台线程
                thread = threading.Thread(target=run_complete, daemon=True)
                thread.start()
                
            except Exception as e:
                insert_paper_btn.name = f"❌ 错误: {str(e)}"
                insert_paper_btn.disabled = False
                print(f"Insert paper error: {e}")
                import traceback
                traceback.print_exc()
            # 注意：如果插入成功，按钮状态将在 complete 完成后恢复
            # 如果插入失败，在 except 块中已经恢复
        
        insert_paper_btn.on_click(insert_paper)
        
        # 定义视图创建函数字典（用于懒加载）
        def create_papers_view_func():
            return self.create_papers_view()

        def create_company_view_func():
            return self.create_company_view()

        def create_university_view_func():
            return self.create_university_view()

        def create_author_view_func():
            return self.create_author_view()

        def create_tag_tree_view_func():
            return self.create_tag_tree_view()

        def create_collect_view_func():
            return self.create_collect_view()

        def create_edit_paper_view_func():
            return self.create_edit_paper_view()

        def create_edit_tag_view_func():
            return self.create_edit_tag_view()

        def create_edit_watched_companies_view_func():
            return self.create_edit_watched_companies_view()

        def create_edit_watched_universities_view_func():
            return self.create_edit_watched_universities_view()

        def create_edit_watched_authors_view_func():
            return self.create_edit_watched_authors_view()

        # 创建视图创建函数的映射
        view_creators = {
            "papers": create_papers_view_func,
            "companies": create_company_view_func,
            "universities": create_university_view_func,
            "authors": create_author_view_func,
            "tags": create_tag_tree_view_func,
            "collect": create_collect_view_func,
            "edit_paper": create_edit_paper_view_func,
            "edit_tag": create_edit_tag_view_func,
            "edit_companies": create_edit_watched_companies_view_func,
            "edit_universities": create_edit_watched_universities_view_func,
            "edit_authors": create_edit_watched_authors_view_func,
        }
        
        # 为每个一级标签创建视图
        top_level_tags = self.database.get_top_level_tags()
        tag_matrix_views_dict = {}  # 保存视图引用以便刷新
        
        # 创建所有标签页的定义（包含英文标识符用于 URL，使用懒加载）
        tab_items_with_id = [
            (("📚 论文列表", "papers"), None),  # None 表示使用懒加载
            (("🏢 关注的公司工作", "companies"), None),
            (("🎓 关注的高校工作", "universities"), None),
            (("👤 关注的作者工作", "authors"), None),
            (("🏷️ 标签树", "tags"), None),
            (("📥 论文收集", "collect"), None),
            (("✏️ 编辑论文", "edit_paper"), None),
            (("✏️ 编辑标签", "edit_tag"), None),
            (("🏢 编辑关注公司", "edit_companies"), None),
            (("🎓 编辑关注高校", "edit_universities"), None),
            (("👤 编辑关注作者", "edit_authors"), None),
        ]
        
        # 为一级标签创建带 ID 的定义（使用懒加载）
        tag_views_with_id = []
        for top_tag in top_level_tags:
            tag_name = top_tag["tag_name"]
            # 使用标签名称作为 ID（去除特殊字符，只保留字母数字和点）
            tag_id = "tag_" + tag_name.replace(".", "_").replace(" ", "_").replace("-", "_")
            tag_views_with_id.append(((f"🏷️ {tag_name}", tag_id), None))  # None 表示使用懒加载
        
        # 创建所有 tab 的映射（名称、ID、创建函数）
        all_tabs_info = {}  # {tab_id: {'name': name, 'view': None, 'creator': func, 'type': 'main' or 'tag'}}

        # 添加主要 tab
        for (name, tab_id), _ in tab_items_with_id:
            creator = view_creators.get(tab_id)
            all_tabs_info[tab_id] = {'name': name, 'view': None, 'creator': creator, 'type': 'main'}

        # 添加 tag tab
        for (name, tab_id), _ in tag_views_with_id:
            # 为标签 tab 创建动态创建函数
            tag_name = name.replace("🏷️ ", "")  # 从显示名称中提取标签名称
            def create_tag_view_func(tag_name=tag_name):
                return self.create_tag_matrix_view(tag_name)
            all_tabs_info[tab_id] = {'name': name, 'view': None, 'creator': create_tag_view_func, 'type': 'tag'}
        
        # 创建内容显示区域（显示当前选中的 tab 内容）
        current_tab_content = pn.Column(sizing_mode='stretch_width')
        
        # 当前选中的 tab ID
        current_tab_id = [None]
        
        def switch_tab(tab_id):
            """切换到指定的 tab（支持懒加载）"""
            if tab_id in all_tabs_info:
                current_tab_id[0] = tab_id
                tab_info = all_tabs_info[tab_id]

                # 懒加载：如果视图还没有创建，则创建它
                if tab_info['view'] is None and tab_info['creator'] is not None:
                    print(f"懒加载创建 tab: {tab_id}")  # 调试信息
                    tab_info['view'] = tab_info['creator']()

                    # 如果是标签视图，保存到 tag_matrix_views_dict 以支持刷新
                    if tab_info['type'] == 'tag':
                        tag_name = tab_info['name'].replace("🏷️ ", "")
                        if not hasattr(self, 'tag_matrix_views_dict'):
                            self.tag_matrix_views_dict = {}
                        self.tag_matrix_views_dict[tag_name] = tab_info['view']

                # 更新内容区域
                current_tab_content.clear()
                if tab_info['view'] is not None:
                    current_tab_content.append(tab_info['view'])

                # 更新按钮样式
                update_tab_buttons_style()

                # 更新 URL
                update_url_from_tab(tab_id)
        
        def update_tab_buttons_style():
            """更新 tab 按钮的样式（高亮当前选中的）"""
            for tab_id, tab_info in all_tabs_info.items():
                if tab_id in main_tab_buttons:
                    btn = main_tab_buttons[tab_id]
                    if tab_id == current_tab_id[0]:
                        btn.button_type = 'primary'
                    else:
                        btn.button_type = 'light'
                if tab_id in tag_tab_buttons:
                    btn = tag_tab_buttons[tab_id]
                    if tab_id == current_tab_id[0]:
                        btn.button_type = 'primary'
                    else:
                        btn.button_type = 'light'
        
        def update_url_from_tab(tab_id):
            """从 tab ID 更新 URL"""
            try:
                if hasattr(pn.state, 'location') and pn.state.location:
                    # 获取当前查询参数
                    current_params = {}
                    try:
                        if hasattr(pn.state.location, 'query_params'):
                            current_params = dict(pn.state.location.query_params or {})
                        elif hasattr(pn.state.location, 'search_params'):
                            current_params = dict(pn.state.location.search_params or {})
                    except:
                        pass
                    
                    # 更新 tab 参数
                    current_params['tab'] = tab_id
                    
                    # 更新 URL
                    from urllib.parse import urlencode
                    new_search = '?' + urlencode(current_params, doseq=True)
                    
                    if hasattr(pn.state.location, 'update_query'):
                        pn.state.location.update_query(tab=tab_id)
                    elif hasattr(pn.state.location, 'search'):
                        pn.state.location.search = new_search
                    elif hasattr(pn.state.location, 'search_params'):
                        pn.state.location.search_params = current_params
            except Exception as e:
                print(f"更新 URL 时出错: {e}")
        
        # 创建第一行 tab 按钮（主要 tab）
        main_tab_buttons = {}
        main_tab_row_items = []
        for (name, tab_id), _ in tab_items_with_id:
            btn = pn.widgets.Button(
                name=name,
                button_type='light',
                width=150,
                margin=(2, 2)
            )
            
            def create_click_handler(tid):
                def handler(event):
                    switch_tab(tid)
                return handler
            
            btn.on_click(create_click_handler(tab_id))
            main_tab_buttons[tab_id] = btn
            main_tab_row_items.append(btn)
        
        # 创建第二行 tab 按钮（tag tab）
        tag_tab_buttons = {}
        tag_tab_row_items = []
        for (name, tab_id), _ in tag_views_with_id:
            btn = pn.widgets.Button(
                name=name,
                button_type='light',
                width=150,
                margin=(2, 2)
            )
            
            def create_click_handler(tid):
                def handler(event):
                    switch_tab(tid)
                return handler
            
            btn.on_click(create_click_handler(tab_id))
            tag_tab_buttons[tab_id] = btn
            tag_tab_row_items.append(btn)
        
        # 创建两行 tab header
        main_tabs_row = pn.Row(
            *main_tab_row_items,
            sizing_mode='stretch_width',
            margin=(0, 0, 5, 0)
        )
        
        tag_tabs_row = pn.Row(
            *tag_tab_row_items,
            sizing_mode='stretch_width',
            margin=(0, 0, 5, 0)
        ) if tag_tab_row_items else None
        
        # 创建 tab ID 到信息的映射（用于 URL 参数）
        tab_id_to_info = {}
        for tab_id, info in all_tabs_info.items():
            tab_id_to_info[tab_id] = info
        
        # 创建完整的 tabs 布局
        tabs_layout_items = [main_tabs_row]
        if tag_tabs_row:
            tabs_layout_items.append(tag_tabs_row)
        tabs_layout_items.append(current_tab_content)
        
        tabs_layout = pn.Column(
            *tabs_layout_items,
            sizing_mode='stretch_width'
        )
        
        # 为了兼容性，创建一个统一的 tabs 对象引用
        tabs = tabs_layout
        
        # 从 URL 参数读取初始 tab
        def get_initial_tab_id():
            """从 URL 参数获取初始 tab ID"""
            try:
                if hasattr(pn.state, 'location') and pn.state.location:
                    # 尝试多种方式获取查询参数
                    query_params = {}
                    if hasattr(pn.state.location, 'query_params'):
                        query_params = pn.state.location.query_params or {}
                    elif hasattr(pn.state.location, 'search_params'):
                        query_params = pn.state.location.search_params or {}
                    elif hasattr(pn.state.location, 'search'):
                        from urllib.parse import parse_qs
                        search_str = pn.state.location.search.lstrip('?')
                        if search_str:
                            query_params = parse_qs(search_str)
                            # 将列表值转换为单个值
                            query_params = {k: v[0] if isinstance(v, list) and len(v) > 0 else v 
                                          for k, v in query_params.items()}
                    
                    if 'tab' in query_params:
                        tab_id = query_params['tab']
                        if tab_id in all_tabs_info:
                            return tab_id
            except Exception as e:
                print(f"读取 URL 参数时出错: {e}")
            # 默认返回第一个主要 tab
            if tab_items_with_id:
                return tab_items_with_id[0][0][1]  # 返回第一个 tab 的 ID
            return None
        
        # 设置初始 tab
        initial_tab_id = get_initial_tab_id()
        if initial_tab_id:
            switch_tab(initial_tab_id)
        else:
            # 如果没有初始 tab，显示第一个主要 tab
            if tab_items_with_id:
                first_tab_id = tab_items_with_id[0][0][1]
                switch_tab(first_tab_id)
        
        # 保存 tabs 引用以便刷新时更新
        self.tabs = tabs
        self.main_tab_buttons = main_tab_buttons
        self.tag_tab_buttons = tag_tab_buttons
        self.current_tab_content = current_tab_content
        self.switch_tab = switch_tab  # 保存函数引用以便外部调用
        self.all_tabs_info = all_tabs_info  # 保存所有 tab 信息
        self.tag_matrix_views_dict = {}  # 初始化标签视图字典（用于刷新）
        
        # 布局
        # 将标题、按钮和输入框合并为一行，更紧凑
        # 标题样式：使用渐变背景和更好的视觉效果 - PaperMap 风格
        title_html = f"""
        <div style='
            background: {config.GRADIENT_BLUE};
            padding: 12px 20px;
            border-radius: {config.BORDER_RADIUS_LARGE};
            margin: 0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            height: 100%;
            display: flex;
            align-items: center;
        '>
            <h1 style='
                margin: 0;
                font-size: {config.FONT_SIZE_TITLE};
                line-height: 1.2;
                color: white;
                font-weight: 600;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
            '>{config.TITLE_MAIN}</h1>
        </div>
        """
        
        header = pn.Row(
            pn.pane.HTML(title_html, sizing_mode='fixed', width=350, height=60),
            pn.Spacer(width=15),
            paper_link_input,
            date_input,
            tags_input,
            insert_paper_btn,
            sizing_mode='stretch_width',
            margin=(15, 20),
            align='center'
        )
        
        # 日期提示放在输入框下方（如果需要显示）
        date_hint_row = pn.Row(
            pn.Spacer(width=350 + 15 + 300),  # 对齐到日期输入框位置（标题+间距+论文链接输入框）
            date_hint,
            sizing_mode='stretch_width',
            margin=(0, 20, 5, 20)
        )
        
        layout = pn.Column(
            header,
            date_hint_row,
            pn.Spacer(height=10),
            tabs,
            sizing_mode='stretch_width',
            margin=(10, 20)
        )
        
        return layout

# 创建应用的函数，参考 session_server.py 的实现方式
# 每次调用时创建新的 dashboard 实例，确保每个 session 都有独立的数据
def session_app():
    """创建 dashboard 应用，为每个 session 创建独立的实例
    可参考 session-based 多用户 Panel 应用的实现方式
    每次调用时都创建新的 PaperDashboard 实例，确保数据是最新的
    """
    import time
    start_time = time.time()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Session app function called - creating new session")
    
    try:
        # 每次调用都创建新的 dashboard 实例，重新加载数据
        dashboard = PaperDashboard()
        app_view = dashboard.create_view()
        
        # 创建新的模板实例（每个 session 都有独立的模板）
        # 直接在创建模板时传入 main 内容
        template = pn.template.BootstrapTemplate(
            title=config.DASHBOARD_TITLE,
            sidebar=[],
            main=[app_view],  # 直接传入视图列表
            header_background=config.THEME_PRIMARY,
            header_color="white"
        )
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Session app function completed in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"Error during initialization: {error_msg}")
        # 创建错误信息的模板
        error_pane = pn.Column(
            pn.pane.HTML(
                f"<div style='padding: 20px; color: red;'>初始化应用时出错: {str(e)}</div>",
                sizing_mode='stretch_width'
            ),
            sizing_mode='stretch_width'
        )
        template = pn.template.BootstrapTemplate(
            title=config.DASHBOARD_TITLE,
            sidebar=[],
            main=[error_pane],
            header_background=config.THEME_PRIMARY,
            header_color="white"
        )
    
    return template

if __name__ == "__main__":
    import sys
    import socket
    try:
        # 设置环境变量，允许任何来源的WebSocket连接
        os.environ["BOKEH_ALLOW_WS_ORIGIN"] = "*"
        
        # 直接运行时启动服务器
        print("正在启动 Panel 服务器...")
        port = config.get_dashboard_port()
        print(f"服务器将在端口 {port} 启动")
        print("按 Ctrl+C 停止服务器")
        
        # 获取本机IP地址
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            print(f"- 本机IP: http://{ip}:{port}")
        except:
            print("- 无法检测到本机IP")
        
        print(f"- 本机: http://localhost:{port}")
        print("- 其他设备: http://<本机IP>:{}".format(port))
        print("=" * 50)
        
        # 使用 pn.serve 方式，参考 session_server.py 的实现
        pn.serve(
            session_app,
            port=port,
            show=False,  # 不自动打开浏览器
            autoreload=True,
            address="0.0.0.0",  # 绑定到所有网络接口
            websocket_max_message_size=104857600,  # 100MB - 增加WebSocket消息大小限制
            check_unused_sessions=10000,  # 增加未使用会话的检查时间间隔
        )
    except KeyboardInterrupt:
        print("\n服务器已停止")
        sys.exit(0)
    except Exception as e:
        print(f"启动服务器时出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
else:
    # 使用 panel serve 时，需要将 session_app 标记为可服务
    # 这样 Panel 会为每个 session 调用这个函数
    session_app.servable()

