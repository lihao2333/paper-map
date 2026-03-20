try:
    import pysqlite3 as sqlite3
except ImportError:
    import sqlite3
import json
import os
import re
from typing import List, Optional, Tuple


def _dedupe_author_names(author_names_raw: str) -> list:
    """解析作者列表并去重，保持首次出现顺序"""
    if not author_names_raw:
        return []
    names = [n.strip() for n in author_names_raw.split(",") if n.strip()]
    return list(dict.fromkeys(names))


def _paper_dict_from_view_row(row) -> dict:
    """paper_based_view 行列序：
    [0]paper_id [1]arxiv_id [2]paper_url [3]date [4]alias [5]full_name
    [6]abstract [7]summary
    [8]company_names [9]university_names [10]author_names
    [11]arxiv_comments [12]is_comment_used [13]tag_names [14]github_url
    """
    tag_raw = row[13] if len(row) > 13 else None
    tags = (
        [t.strip() for t in str(tag_raw).split(",") if t.strip()]
        if tag_raw
        else []
    )
    return {
        "paper_id": row[0],
        "arxiv_id": row[1],
        "paper_url": row[2],
        "date": row[3],
        "alias": row[4] or "",
        "full_name": row[5] or "",
        "abstract": row[6] or "",
        "summary": row[7] or "",
        "company_names": row[8].split(",") if row[8] else [],
        "university_names": row[9].split(",") if row[9] else [],
        "author_names": _dedupe_author_names(row[10] or ""),
        # NULL 须保持为 None：若写成 ""，completer 会误判「已拉取过」而永远不调 arXiv API
        "arxiv_comments": row[11],
        "is_comment_used": bool(row[12]) if row[12] is not None else False,
        "tags": tags,
        "github_url": row[14] if len(row) > 14 else None,
    }


def paper_list_sort_key(p: dict) -> tuple:
    """
    论文列表倒序排序用 key：先有 arxiv_id 的论文按 arxiv_id 再 date 再 paper_id；
    无 arxiv_id 的排在后面，按 date 再 paper_id。
    配合 sort(..., key=paper_list_sort_key, reverse=True) 使用。
    """
    aid = (p.get("arxiv_id") or "").strip()
    d = (p.get("date") or "").strip()
    pid = (p.get("paper_id") or "").strip()
    if aid:
        return (1, aid, d, pid)
    return (0, "", d, pid)


class Database:

    def __init__(self, path):
        self._path = path
    
    @staticmethod
    def _extract_date_from_arxiv_id(arxiv_id: str) -> str:
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

    def construct(self):
        conn = sqlite3.connect(self._path)
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        # 新表结构：支持 paper_id (主键) 和 paper_url，arxiv_id 可选
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper (
                paper_id TEXT PRIMARY KEY,
                arxiv_id TEXT UNIQUE,
                paper_url TEXT NOT NULL,
                date TEXT,
                alias TEXT,
                full_name TEXT,
                abstract TEXT,
                summary TEXT,
                github_url TEXT
            )
        """) 
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_company (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                company_name TEXT,
                FOREIGN KEY (paper_id) REFERENCES paper(paper_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_university (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                university_name TEXT,
                FOREIGN KEY (paper_id) REFERENCES paper(paper_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tag (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT NOT NULL UNIQUE
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_tag (
                paper_id TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (paper_id, tag_id),
                FOREIGN KEY (paper_id) REFERENCES paper(paper_id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tag(tag_id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_author (
                paper_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                author_order INTEGER,
                PRIMARY KEY (paper_id, author_name),
                FOREIGN KEY (paper_id) REFERENCES paper(paper_id) ON DELETE CASCADE
            )
        """)
        
        # 为现有表添加 author_order 字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE paper_author ADD COLUMN author_order INTEGER")
        except sqlite3.OperationalError:
            # 字段已存在，忽略错误
            pass

        try:
            cursor.execute("ALTER TABLE paper ADD COLUMN arxiv_comments TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute(
                "ALTER TABLE paper ADD COLUMN is_comment_used INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass
        # 为现有表添加 github_url 字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE paper ADD COLUMN github_url TEXT")
        except sqlite3.OperationalError:
            pass
        
        # 创建关注公司配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watched_company (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                match_rule TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建关注高校配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watched_university (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                match_rule TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建关注作者配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watched_author (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                match_rule TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paper_arxiv_id ON paper(arxiv_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paper_company_paper_id ON paper_company(paper_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paper_university_paper_id ON paper_university(paper_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tag_name ON tag(tag_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paper_tag_paper_id_tag_id ON paper_tag(paper_id, tag_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paper_author_paper_id_order ON paper_author(paper_id, author_order)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_watched_company_name ON watched_company(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_watched_university_name ON watched_university(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_watched_author_name ON watched_author(name)")
        
        # 删除旧视图（如果存在），然后重新创建以包含 author_names
        cursor.execute("DROP VIEW IF EXISTS paper_based_view")
        
        # 创建 paper_based_view，包含 company_names、university_names 和 author_names
        # 使用 GROUP_CONCAT 聚合多个值，用逗号分隔
        # 作者按 author_order 排序（一作、二作等）
        cursor.execute("""
            CREATE VIEW paper_based_view AS
            SELECT
                p.paper_id,
                p.arxiv_id,
                p.paper_url,
                p.date,
                p.alias,
                p.full_name,
                p.abstract,
                p.summary,
                GROUP_CONCAT(DISTINCT pc.company_name) AS company_names,
                GROUP_CONCAT(DISTINCT pu.university_name) AS university_names,
                GROUP_CONCAT(pa.author_name, ', ' ORDER BY pa.author_order) AS author_names,
                p.arxiv_comments,
                p.is_comment_used,
                GROUP_CONCAT(DISTINCT tg.tag_name) AS tag_names,
                p.github_url
            FROM paper p
            LEFT JOIN paper_company pc ON p.paper_id = pc.paper_id
            LEFT JOIN paper_university pu ON p.paper_id = pu.paper_id
            LEFT JOIN paper_author pa ON p.paper_id = pa.paper_id
            LEFT JOIN paper_tag plt ON p.paper_id = plt.paper_id
            LEFT JOIN tag tg ON plt.tag_id = tg.tag_id
            GROUP BY p.paper_id, p.arxiv_id, p.paper_url, p.date, p.alias, p.full_name, p.abstract, p.summary,
                p.arxiv_comments, p.is_comment_used, p.github_url
        """)
        
        conn.commit()
        conn.close()

        self._migrate_tags()

    # 历史标签重命名记录：old_name -> new_name
    # 只追加，不删除（幂等：旧标签不存在时自动跳过）
    _TAG_MIGRATIONS: List[Tuple[str, str]] = [
        ("hf_daily_paper",    "hf.daily"),
        ("hf_trending_paper", "hf.trending"),
        ("hf_weekly_paper",   "hf.weekly"),
        ("hf_monthly_paper",  "hf.monthly"),
    ]

    def _migrate_tags(self) -> None:
        """将历史标签名迁移到新名称，幂等（旧名不存在则跳过）。"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tag_id, tag_name FROM tag")
            tags = {name: tid for tid, name in cursor.fetchall()}

        for old, new in self._TAG_MIGRATIONS:
            if old in tags:
                self.update_tag_name(tags[old], new)

    def insert_paper(self, data):
        """
        插入论文数据
        data: 可以是两种格式：
        1. 旧格式（向后兼容）: [(arxiv_id, alias, full_name, abstract), ...]
        2. 新格式: [
            {
                "paper_id": "...",
                "paper_url": "...",
                "arxiv_id": "..." (可选),
                "alias": "...",
                "full_name": "...",
                "abstract": "..."
            },
            ...
        ]
        """
        conn = sqlite3.connect(self._path)
        cursor = conn.cursor()
        
        # 检测数据格式
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            
            # 如果是字典格式（新格式）
            if isinstance(first_item, dict):
                for item in data:
                    paper_id = item.get("paper_id")
                    paper_url = item.get("paper_url")
                    arxiv_id = item.get("arxiv_id")
                    date = item.get("date")
                    alias = item.get("alias")
                    full_name = item.get("full_name")
                    abstract = item.get("abstract")
                    github_url = item.get("github_url")

                    if not paper_id or not paper_url:
                        print(f"警告: 跳过无效数据，缺少 paper_id 或 paper_url: {item}")
                        continue

                    cursor.execute("""
                        INSERT OR IGNORE INTO paper
                        (paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, github_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, github_url))
            
            # 如果是元组格式（旧格式，向后兼容）
            elif isinstance(first_item, tuple):
                # 旧格式: (arxiv_id, alias, full_name, abstract) 或 (arxiv_id, alias, full_name, abstract, None)
                for item in data:
                    if len(item) >= 1:
                        arxiv_id = item[0]
                        alias = item[1] if len(item) > 1 else None
                        full_name = item[2] if len(item) > 2 else None
                        abstract = item[3] if len(item) > 3 else None
                        
                        if not arxiv_id:
                            continue
                        
                        # 对于旧格式，paper_id = arxiv_id, paper_url = arxiv URL
                        paper_id = arxiv_id
                        paper_url = f"https://arxiv.org/abs/{arxiv_id}"
                        
                        # 从 arxiv_id 提取日期
                        date = Database._extract_date_from_arxiv_id(arxiv_id)
                        
                        cursor.execute("""
                            INSERT OR IGNORE INTO paper 
                            (paper_id, arxiv_id, paper_url, date, alias, full_name, abstract) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (paper_id, arxiv_id, paper_url, date, alias, full_name, abstract))
        
        conn.commit()
        conn.close()
    
    def update_paper_abstract(self, data):
        """
        批量更新 paper 表的 abstract 字段（向后兼容方法）
        :param data: 列表，每个元素是 (arxiv_id, abstract) 元组，格式：[(arxiv_id1, abstract1), (arxiv_id2, abstract2), ...]
        """
        # 转换数据格式：从 (arxiv_id, abstract) 元组列表转为字典列表
        dict_data = []
        for arxiv_id, abstract in data:
            if arxiv_id:
                # 通过 arxiv_id 查找 paper_id
                paper_info = self.get_paper_info(arxiv_id=arxiv_id)
                if paper_info:
                    dict_data.append({"paper_id": paper_info["paper_id"], "abstract": abstract})
        # 调用新的通用方法
        self.update_paper_info(dict_data)


    def get_arxiv_ids(self):
        """获取所有 arXiv ID（向后兼容方法，只返回有 arxiv_id 的记录）"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT arxiv_id FROM paper WHERE arxiv_id IS NOT NULL
            """)
            return [row[0] for row in cursor.fetchall()]
    
    def get_paper_ids(self):
        """获取所有论文 ID"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT paper_id FROM paper
            """)
            return [row[0] for row in cursor.fetchall()]

    def get_arxiv_ids_having_no_abstarct(self):
        """获取没有摘要的 arXiv ID（向后兼容方法）"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT arxiv_id FROM paper 
                WHERE arxiv_id IS NOT NULL AND abstract IS NULL
            """)
            return [row[0] for row in cursor.fetchall()]

    def get_arxiv_ids_having_no_company_university_names(self):
        """
        返回没有公司或高校信息的 arXiv ID（向后兼容方法）
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT p.arxiv_id 
                FROM paper p
                WHERE p.arxiv_id IS NOT NULL
                AND p.paper_id NOT IN (
                    SELECT DISTINCT paper_id FROM paper_company WHERE paper_id IS NOT NULL
                )
                AND p.paper_id NOT IN (
                    SELECT DISTINCT paper_id FROM paper_university WHERE paper_id IS NOT NULL
                )
            """)
            return [row[0] for row in cursor.fetchall()]

    def get_arxiv_ids_having_no_alias(self):
        """获取没有别名的 arXiv ID（向后兼容方法）"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT arxiv_id FROM paper 
                WHERE arxiv_id IS NOT NULL AND (alias IS NULL OR alias = '')
            """)
            return [row[0] for row in cursor.fetchall()]

    def get_arxiv_ids_having_no_full_name(self):
        """获取没有完整标题的 arXiv ID（向后兼容方法）"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT arxiv_id FROM paper 
                WHERE arxiv_id IS NOT NULL AND full_name IS NULL
            """)
            return [row[0] for row in cursor.fetchall()]

    def get_arxiv_ids_having_no_authors(self):
        """获取没有作者信息的 arXiv ID"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT p.arxiv_id 
                FROM paper p
                WHERE p.arxiv_id IS NOT NULL
                AND p.paper_id NOT IN (
                    SELECT DISTINCT paper_id FROM paper_author WHERE paper_id IS NOT NULL
                )
            """)
            return [row[0] for row in cursor.fetchall()]

    def get_paper_info(self, paper_id: str = None, arxiv_id: str = None):
        """
        获取论文信息
        可以通过 paper_id 或 arxiv_id 查询（优先使用 paper_id）
        return json format:
        {
            "paper_id": "xx",
            "arxiv_id": "xx" (可能为 None),
            "paper_url": "xx",
            "date": "xx" (可能为 None),
            "alias": "xx",
            "full_name": "xx",
            "abstract": "xx",
            "summary": "xx",
            "company_names": ["xx", "xx"],
            "university_names": ["xx", "xx"],
            "author_names": ["xx", "xx"],
            "arxiv_comments": "xx",
            "is_comment_used": bool,
            "tags": ["xx", "xx"]
        }
        """
        if not paper_id and not arxiv_id:
            return None
        
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            if paper_id:
                cursor.execute("""
                    SELECT paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, summary, company_names, university_names, author_names, arxiv_comments, is_comment_used, tag_names, github_url
                    FROM paper_based_view WHERE paper_id = ?
                """, (paper_id,))
            else:
                cursor.execute("""
                    SELECT paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, summary, company_names, university_names, author_names, arxiv_comments, is_comment_used, tag_names, github_url
                    FROM paper_based_view WHERE arxiv_id = ?
                """, (arxiv_id,))

            row = cursor.fetchone()
            if row is None:
                return None
            return _paper_dict_from_view_row(row)

    def get_papers_info_batch(self, paper_ids: list) -> dict:
        """
        批量获取论文信息，返回 {paper_id: {...}}
        格式同 get_paper_info，用于矩阵 hover 批量加载，避免 N+1 查询
        """
        if not paper_ids:
            return {}
        result = {}
        # SQLite 单次 IN 子句最多约 999 个参数，分批查询
        chunk_size = 500
        for i in range(0, len(paper_ids), chunk_size):
            chunk = paper_ids[i : i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            with sqlite3.connect(self._path) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, summary, company_names, university_names, author_names, arxiv_comments, is_comment_used, tag_names, github_url
                    FROM paper_based_view WHERE paper_id IN ({placeholders})
                """, chunk)
                for row in cursor.fetchall():
                    result[row[0]] = _paper_dict_from_view_row(row)
        return result

    def get_papers_tags_batch(self, paper_ids: list) -> dict:
        """
        批量获取论文标签，返回 {paper_id: [{"tag_id": n, "tag_name": "..."}, ...]}
        用于矩阵 hover 批量加载及删除操作
        """
        if not paper_ids:
            return {}
        result = {pid: [] for pid in paper_ids}
        chunk_size = 500
        for i in range(0, len(paper_ids), chunk_size):
            chunk = paper_ids[i : i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            with sqlite3.connect(self._path) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT pt.paper_id, t.tag_id, t.tag_name
                    FROM paper_tag pt
                    INNER JOIN tag t ON pt.tag_id = t.tag_id
                    WHERE pt.paper_id IN ({placeholders})
                    ORDER BY pt.paper_id, t.tag_name
                """, chunk)
                for paper_id, tag_id, tag_name in cursor.fetchall():
                    result[paper_id].append({"tag_id": tag_id, "tag_name": tag_name})
        return result

    def search_paper(self, query: str):
        """
        搜索论文，支持通过 paper_id、arxiv_id、alias、full_name 搜索
        query: 搜索关键词
        return: 匹配的论文信息列表，格式同 get_paper_info
        """
        if not query:
            return []
        
        query = query.strip()
        if not query:
            return []
        
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            # 使用 LIKE 进行模糊匹配，支持 paper_id、arxiv_id、alias、full_name
            search_pattern = f"%{query}%"
            cursor.execute("""
                SELECT paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, summary, company_names, university_names, author_names, arxiv_comments, is_comment_used, tag_names, github_url
                FROM paper_based_view
                WHERE paper_id LIKE ?
                   OR arxiv_id LIKE ?
                   OR alias LIKE ?
                   OR full_name LIKE ?
                ORDER BY 
                    CASE 
                        WHEN paper_id = ? THEN 1
                        WHEN arxiv_id = ? THEN 2
                        WHEN alias = ? THEN 3
                        WHEN full_name = ? THEN 4
                        WHEN paper_id LIKE ? THEN 5
                        WHEN arxiv_id LIKE ? THEN 6
                        WHEN alias LIKE ? THEN 7
                        WHEN full_name LIKE ? THEN 8
                        ELSE 9
                    END,
                    date DESC, paper_id
                LIMIT 20
            """, (search_pattern, search_pattern, search_pattern, search_pattern,
                  query, query, query, query,
                  f"{query}%", f"{query}%", f"{query}%", f"{query}%"))
            
            results = []
            for row in cursor.fetchall():
                results.append(_paper_dict_from_view_row(row))
            return results

    def update_paper_info(self, data):
        """
        批量更新 paper 表的信息（abstract、alias、full_name、summary、date）
        data: 
        [
          {
              "paper_id": "xx",        # 优先使用
              "arxiv_id": "xx",        # 如果没有 paper_id，可以使用 arxiv_id（向后兼容）
              "alias": "xx",           # 可选
              "full_name": "xx",       # 可选
              "abstract": "xx",        # 可选
              "summary": "xx",        # 可选
              "date": "xx"            # 可选
              "company_names": ["xx", "xx"],
              "university_names": ["xx", "xx"],
          }
        ]
        """
        # 验证数据格式
        if not isinstance(data, list) or len(data) == 0:
            print("数据为空或格式错误，无需更新")
            return
        
        # 转换数据格式：分离 abstract、alias、full_name、summary、date、company_names、university_names、author_names 数据
        abstract_data = []
        alias_data = []
        full_name_data = []
        summary_data = []
        date_data = []
        company_data = []
        university_data = []
        author_data = []
        arxiv_comments_data = []
        is_comment_used_data = []
        
        for item in data:
            # 优先使用 paper_id，如果没有则使用 arxiv_id（向后兼容）
            paper_id = item.get("paper_id")
            if not paper_id:
                arxiv_id = item.get("arxiv_id")
                if arxiv_id:
                    # 向后兼容：通过 arxiv_id 查找 paper_id
                    paper_info = self.get_paper_info(arxiv_id=arxiv_id)
                    if paper_info:
                        paper_id = paper_info["paper_id"]
                    else:
                        continue
                else:
                    continue
            
            # 准备 abstract 数据：格式 (abstract, paper_id)
            abstract = item.get("abstract")
            if abstract is not None:
                abstract_data.append((abstract, paper_id))
            
            # 准备 alias 数据：格式 (alias, paper_id)
            alias = item.get("alias")
            if alias is not None:
                alias_data.append((alias, paper_id))
            
            # 准备 full_name 数据：格式 (full_name, paper_id)
            full_name = item.get("full_name")
            if full_name is not None:
                full_name_data.append((full_name, paper_id))
            
            # 准备 summary 数据：格式 (summary, paper_id)
            summary = item.get("summary")
            if summary is not None:
                summary_data.append((summary, paper_id))
            
            # 准备 date 数据：格式 (date, paper_id)
            date = item.get("date")
            if date is not None:
                date_data.append((date, paper_id))
            
            # 准备 company_names 数据
            company_names = item.get("company_names")
            if company_names is not None:
                company_data.append({
                    "paper_id": paper_id,
                    "company_names": company_names
                })
            
            # 准备 university_names 数据
            university_names = item.get("university_names")
            if university_names is not None:
                university_data.append({
                    "paper_id": paper_id,
                    "university_names": university_names
                })
            
            # 准备 author_names 数据
            author_names = item.get("author_names")
            if author_names is not None:
                author_data.append({
                    "paper_id": paper_id,
                    "author_names": author_names
                })

            # 显式带键才更新（含 None → 写入 NULL），避免与 is_comment_used 分条更新时漏写 comment
            if "arxiv_comments" in item:
                arxiv_comments_data.append((item["arxiv_comments"], paper_id))

            icu = item.get("is_comment_used")
            if icu is not None:
                is_comment_used_data.append((1 if icu else 0, paper_id))
        
        # 调用辅助方法更新数据
        if abstract_data:
            self._update_paper_abstract(abstract_data)
        if alias_data:
            self._update_paper_alias(alias_data)
        if full_name_data:
            self._update_paper_full_name(full_name_data)
        if summary_data:
            self._update_paper_summary(summary_data)
        if date_data:
            self._update_paper_date(date_data)
        if company_data:
            self._update_paper_company_names(company_data)
        if university_data:
            self._update_paper_university_names(university_data)
        if author_data:
            self._update_paper_author_names(author_data)
        if arxiv_comments_data:
            self._update_paper_arxiv_comments(arxiv_comments_data)
        if is_comment_used_data:
            self._update_paper_is_comment_used(is_comment_used_data)

    def _update_paper_abstract(self, data):
        """
        data: [(abstract, paper_id), ...]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                UPDATE paper SET abstract = ? WHERE paper_id = ?
            """, data)
            conn.commit()

    def _update_paper_alias(self, data):
        """
        data: [(alias, paper_id), ...]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                UPDATE paper SET alias = ? WHERE paper_id = ?
            """, data)
            conn.commit()
    
    def _update_paper_full_name(self, data):   
        """
        data: [(full_name, paper_id), ...]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                UPDATE paper SET full_name = ? WHERE paper_id = ?
            """, data)
            conn.commit()
    
    def _update_paper_summary(self, data):
        """
        data: [(summary, paper_id), ...]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                UPDATE paper SET summary = ? WHERE paper_id = ?
            """, data)
            conn.commit()
    
    def _update_paper_date(self, data):
        """
        data: [(date, paper_id), ...]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                UPDATE paper SET date = ? WHERE paper_id = ?
            """, data)
            conn.commit()

    def _update_paper_arxiv_comments(self, data):
        """
        data: [(arxiv_comments, paper_id), ...]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                UPDATE paper SET arxiv_comments = ? WHERE paper_id = ?
            """, data)
            conn.commit()

    def _update_paper_is_comment_used(self, data):
        """
        data: [(0|1, paper_id), ...]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                UPDATE paper SET is_comment_used = ? WHERE paper_id = ?
            """, data)
            conn.commit()
    
    def _update_paper_company_names(self, data):
        """
        更新论文的公司名称
        先删除旧的关联，再插入新的
        
        data: [
            {
                "paper_id": "xx",
                "company_names": ["xx", "xx"]
            },
            ...
        ]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            
            for item in data:
                paper_id = item["paper_id"]
                company_names = item.get("company_names", [])
                
                # 删除旧的关联
                cursor.execute("DELETE FROM paper_company WHERE paper_id = ?", (paper_id,))
                
                # 插入新的公司名称
                company_data = [(paper_id, name) for name in company_names if name]
                if company_data:
                    cursor.executemany("""
                        INSERT INTO paper_company (paper_id, company_name) VALUES (?, ?)
                    """, company_data)
            
            conn.commit()
    
    def _update_paper_university_names(self, data):
        """
        更新论文的大学名称
        先删除旧的关联，再插入新的
        
        data: [
            {
                "paper_id": "xx",
                "university_names": ["xx", "xx"]
            },
            ...
        ]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            
            for item in data:
                paper_id = item["paper_id"]
                university_names = item.get("university_names", [])
                
                # 删除旧的关联
                cursor.execute("DELETE FROM paper_university WHERE paper_id = ?", (paper_id,))
                
                # 插入新的大学名称
                university_data = [(paper_id, name) for name in university_names if name]
                if university_data:
                    cursor.executemany("""
                        INSERT INTO paper_university (paper_id, university_name) VALUES (?, ?)
                    """, university_data)
            
            conn.commit()
    
    def _update_paper_author_names(self, data):
        """
        更新论文的作者名称（按顺序保存：一作、二作等）
        先删除旧的关联，再插入新的
        
        data: [
            {
                "paper_id": "xx",
                "author_names": ["xx", "xx"]  # 列表顺序即作者顺序（一作、二作等）
            },
            ...
        ]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            
            for item in data:
                paper_id = item["paper_id"]
                author_names = item.get("author_names", [])
                
                # 删除旧的关联
                cursor.execute("DELETE FROM paper_author WHERE paper_id = ?", (paper_id,))
                
                # 插入新的作者名称（保持顺序，索引+1作为author_order）
                # 使用 dict.fromkeys 去重，保持顺序（Python 3.7+ dict 保持插入顺序）
                unique_author_names = list(dict.fromkeys([name for name in author_names if name]))
                # author_order: 1=一作, 2=二作, 3=三作, ...
                author_data = [(paper_id, name, idx + 1) for idx, name in enumerate(unique_author_names)]
                if author_data:
                    cursor.executemany("""
                        INSERT OR IGNORE INTO paper_author (paper_id, author_name, author_order) VALUES (?, ?, ?)
                    """, author_data)
            
            conn.commit()
    
    def insert_paper_company_university_names(self, data):
        """
        data: 
        [
           {
              "paper_id": "xx",        # 优先使用
              "arxiv_id": "xx",        # 如果没有 paper_id，可以使用 arxiv_id（向后兼容）
              "company_names": ["xx", "xx"],
              "university_names": ["xx", "xx"],
           } 
        ]
        """
        # 转换数据格式为辅助方法需要的格式
        company_data = []
        university_data = []
        
        for item in data:
            # 优先使用 paper_id，如果没有则使用 arxiv_id（向后兼容）
            paper_id = item.get("paper_id")
            if not paper_id:
                arxiv_id = item.get("arxiv_id")
                if arxiv_id:
                    # 通过 arxiv_id 查找 paper_id
                    paper_info = self.get_paper_info(arxiv_id=arxiv_id)
                    if paper_info:
                        paper_id = paper_info["paper_id"]
                    else:
                        continue
                else:
                    continue
            
            # 处理公司名称
            company_names = item.get("company_names", [])
            for company_name in company_names:
                if company_name:  # 确保不为空
                    company_data.append((paper_id, company_name))
            
            # 处理大学名称
            university_names = item.get("university_names", [])
            for university_name in university_names:
                if university_name:  # 确保不为空
                    university_data.append((paper_id, university_name))
        
        # 调用辅助方法插入数据
        if company_data:
            self._insert_paper_company_names(company_data)
        if university_data:
            self._insert_paper_university_names(university_data)

    def _insert_paper_company_names(self, data):
        """
        data: [(paper_id, company_name), ...]
        """
        conn = sqlite3.connect(self._path)
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO paper_company (paper_id, company_name) VALUES (?, ?)
        """, data)
        conn.commit()
        conn.close()

    def _insert_paper_university_names(self, data):
        """
        data: [(paper_id, university_name), ...]
        """
        conn = sqlite3.connect(self._path)
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO paper_university (paper_id, university_name) VALUES (?, ?)
        """, data)
        conn.commit()
        conn.close()

    def get_all_papers_with_details(self):
        """
        获取所有论文及其关联的公司和大学信息
        返回格式: [
            {
                "paper_id": "...",
                "arxiv_id": "..." (可能为 None),
                "paper_url": "...",
                "alias": "...",
                "full_name": "...",
                "abstract": "...",
                "summary": "...",
                "company_names": ["...", "..."],
                "university_names": ["...", "..."],
                "author_names": ["...", "..."],
                "arxiv_comments": "...",
                "is_comment_used": bool,
                "tags": ["...", "..."]
            },
            ...
        ]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, summary,
                       company_names, university_names, author_names, arxiv_comments, is_comment_used, tag_names, github_url
                FROM paper_based_view
                ORDER BY
                    (CASE WHEN arxiv_id IS NOT NULL AND TRIM(arxiv_id) != '' THEN 1 ELSE 0 END) DESC,
                    arxiv_id DESC,
                    date DESC,
                    paper_id DESC
            """)
            return [_paper_dict_from_view_row(row) for row in cursor.fetchall()]

    def query_papers(
        self,
        company: str = None,
        university: str = None,
        author: str = None,
        tag: str = None,
        start_date: str = None,
        end_date: str = None,
    ):
        """
        按条件查询论文，支持公司、高校、作者、标签、时间范围过滤。
        返回格式同 get_all_papers_with_details。

        参数:
            company: 公司名（模糊匹配，如 'Tesla'、'Waymo'）
            university: 高校名（模糊匹配）
            author: 作者名（模糊匹配）
            tag: 标签名或前缀（模糊匹配，支持层级如 '自动驾驶.感知'）
            start_date: 开始日期 yyyyMM，如 '202401'
            end_date: 结束日期 yyyyMM，如 '202412'
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()

            conditions = []
            params = []

            if company:
                conditions.append("company_names LIKE ?")
                params.append(f"%{company}%")
            if university:
                conditions.append("university_names LIKE ?")
                params.append(f"%{university}%")
            if author:
                conditions.append("author_names LIKE ?")
                params.append(f"%{author}%")
            if start_date:
                conditions.append("(date >= ? OR date IS NULL)")
                params.append(start_date)
            if end_date:
                conditions.append("(date <= ? OR date IS NULL)")
                params.append(end_date)

            where_sql = " AND ".join(conditions) if conditions else "1=1"

            if tag:
                # 需要按 tag 过滤，先查 paper_based_view 再过滤 tag
                cursor.execute(
                    f"""
                    SELECT paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, summary,
                           company_names, university_names, author_names, arxiv_comments, is_comment_used, tag_names, github_url
                    FROM paper_based_view
                    WHERE {where_sql}
                    ORDER BY
                        (CASE WHEN arxiv_id IS NOT NULL AND TRIM(arxiv_id) != '' THEN 1 ELSE 0 END) DESC,
                        arxiv_id DESC,
                        date DESC,
                        paper_id
                    """,
                    params,
                )
                rows = cursor.fetchall()
                result = []
                needle = tag.lower()
                for row in rows:
                    d = _paper_dict_from_view_row(row)
                    if any(needle in t.lower() for t in d["tags"]):
                        result.append(d)
                return result

            cursor.execute(
                f"""
                SELECT paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, summary,
                       company_names, university_names, author_names, arxiv_comments, is_comment_used, tag_names, github_url
                FROM paper_based_view
                WHERE {where_sql}
                ORDER BY
                    (CASE WHEN arxiv_id IS NOT NULL AND TRIM(arxiv_id) != '' THEN 1 ELSE 0 END) DESC,
                    arxiv_id DESC,
                    date DESC,
                    paper_id
                """,
                params,
            )
            return [_paper_dict_from_view_row(row) for row in cursor.fetchall()]

    def query_papers(
        self,
        company=None,
        university=None,
        author=None,
        tag=None,
        start_date=None,
        end_date=None,
    ):
        """
        按条件筛选论文，返回格式同 get_all_papers_with_details。
        参数均支持模糊匹配（LIKE %value%），日期格式为 yyyyMM。

        :param company: 公司名（支持部分匹配）
        :param university: 高校名
        :param author: 作者名
        :param tag: 标签名（支持层级前缀，如 自动驾驶.感知）
        :param start_date: 起始日期 yyyyMM
        :param end_date: 结束日期 yyyyMM
        """
        conditions = []
        params = []

        if company:
            conditions.append("(company_names LIKE ?)")
            params.append(f"%{company}%")
        if university:
            conditions.append("(university_names LIKE ?)")
            params.append(f"%{university}%")
        if author:
            conditions.append("(author_names LIKE ?)")
            params.append(f"%{author}%")
        if start_date:
            conditions.append("(date >= ?)")
            params.append(start_date)
        if end_date:
            conditions.append("(date <= ?)")
            params.append(end_date)

        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            where_sql = " AND ".join(conditions) if conditions else "1=1"

            # 先用 paper_based_view 筛选
            cursor.execute(
                f"""
                SELECT paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, summary,
                       company_names, university_names, author_names, arxiv_comments, is_comment_used, tag_names, github_url
                FROM paper_based_view
                WHERE {where_sql}
                ORDER BY
                    (CASE WHEN arxiv_id IS NOT NULL AND TRIM(arxiv_id) != '' THEN 1 ELSE 0 END) DESC,
                    arxiv_id DESC,
                    date DESC,
                    paper_id
                """,
                params,
            )
            rows = cursor.fetchall()

            # tag 筛选需关联 paper_tag
            if tag and rows:
                paper_ids = [r[0] for r in rows]
                placeholders = ",".join(["?"] * len(paper_ids))
                cursor.execute(
                    f"""
                    SELECT DISTINCT pt.paper_id
                    FROM paper_tag pt
                    JOIN tag t ON pt.tag_id = t.tag_id
                    WHERE pt.paper_id IN ({placeholders})
                      AND t.tag_name LIKE ?
                    """,
                    paper_ids + [f"%{tag}%"],
                )
                valid_ids = {r[0] for r in cursor.fetchall()}
                rows = [r for r in rows if r[0] in valid_ids]

            return [_paper_dict_from_view_row(row) for row in rows]

    def get_company_paper_matrix(self):
        """
        获取公司-论文矩阵数据
        返回格式: [
            {
                "paper_id": "...",
                "arxiv_id": "..." (可能为 None),
                "paper_url": "...",
                "alias": "...",
                "company_name": "..."
            },
            ...
        ]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.paper_id, p.arxiv_id, p.paper_url, p.alias, pc.company_name
                FROM paper p
                INNER JOIN paper_company pc ON p.paper_id = pc.paper_id
                ORDER BY pc.company_name, p.paper_id
            """)
            results = []
            for paper_id, arxiv_id, paper_url, alias, company_name in cursor.fetchall():
                results.append({
                    "paper_id": paper_id,
                    "arxiv_id": arxiv_id,
                    "paper_url": paper_url,
                    "alias": alias or "",
                    "company_name": company_name
                })
            return results
    
    def get_watched_author_paper_matrix(self):
        """
        获取关注作者-论文矩阵数据
        从数据库读取关注作者配置，使用匹配规则查询，返回时使用配置名称
        返回格式: [
            {
                "paper_id": "...",
                "arxiv_id": "..." (可能为 None),
                "paper_url": "...",
                "alias": "...",
                "summary": "...",
                "full_name": "...",
                "date": "...",
                "author_name": "..."  # 配置名称
            },
            ...
        ]
        """
        # 从数据库加载关注作者配置
        watched_authors = self.get_all_watched_authors()
        
        # 按名称分组，构建匹配规则映射
        author_mapping = {}
        for item in watched_authors:
            name = item["name"]
            match_rule = item["match_rule"]
            if name not in author_mapping:
                author_mapping[name] = []
            author_mapping[name].append(match_rule)
        
        # 分离精确匹配和通配符模式
        exact_names = []
        wildcard_patterns = []  # [(pattern, config_name), ...]
        author_to_config = {}
        
        for config_name, match_rules in author_mapping.items():
            for match_rule in match_rules:
                # 检查是否包含通配符（* 或 ?）
                if '*' in match_rule or '?' in match_rule:
                    # 转换为 SQL LIKE 模式：* -> %, ? -> _
                    sql_pattern = match_rule.replace('*', '%').replace('?', '_')
                    wildcard_patterns.append((sql_pattern, config_name))
                else:
                    exact_names.append(match_rule)
                    author_to_config[match_rule] = config_name
        
        # 使用匹配规则查询数据库
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            results = []
            
            # 1. 精确匹配查询
            if exact_names:
                placeholders = ','.join(['?'] * len(exact_names))
                cursor.execute(f"""
                    SELECT p.paper_id, p.arxiv_id, p.paper_url, p.alias, p.summary, p.full_name, p.date, pa.author_name
                    FROM paper p
                    INNER JOIN paper_author pa ON p.paper_id = pa.paper_id
                    WHERE pa.author_name IN ({placeholders})
                    ORDER BY pa.author_name, p.paper_id
                """, exact_names)
                
                for paper_id, arxiv_id, paper_url, alias, summary, full_name, date, author_name in cursor.fetchall():
                    config_name = author_to_config.get(author_name, author_name)
                    results.append({
                        "paper_id": paper_id,
                        "arxiv_id": arxiv_id,
                        "paper_url": paper_url,
                        "alias": alias or "",
                        "summary": summary or "",
                        "full_name": full_name or "",
                        "date": date or "",
                        "author_name": config_name
                    })
            
            # 2. 通配符匹配查询
            for sql_pattern, config_name in wildcard_patterns:
                cursor.execute("""
                    SELECT p.paper_id, p.arxiv_id, p.paper_url, p.alias, p.summary, p.full_name, p.date, pa.author_name
                    FROM paper p
                    INNER JOIN paper_author pa ON p.paper_id = pa.paper_id
                    WHERE pa.author_name LIKE ?
                    ORDER BY pa.author_name, p.paper_id
                """, (sql_pattern,))
                
                for paper_id, arxiv_id, paper_url, alias, summary, full_name, date, author_name in cursor.fetchall():
                    # 检查是否已经添加过（避免重复）
                    if not any(r["paper_id"] == paper_id and r["author_name"] == config_name for r in results):
                        results.append({
                            "paper_id": paper_id,
                            "arxiv_id": arxiv_id,
                            "paper_url": paper_url,
                            "alias": alias or "",
                            "summary": summary or "",
                            "full_name": full_name or "",
                            "date": date or "",
                            "author_name": config_name
                        })
            
            return results
    
    def get_arxiv_ids_having_no_summary(self):
        """获取没有总结的 arXiv ID（向后兼容方法）"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT arxiv_id FROM paper 
                WHERE arxiv_id IS NOT NULL AND summary IS NULL
            """)
            return [row[0] for row in cursor.fetchall()]
    
    def get_car_company_paper_matrix(self):
        """
        获取关注公司-论文矩阵数据
        从数据库读取关注公司配置，将中文名称映射到英文名称进行查询，返回时使用中文名称
        返回格式: [
            {
                "paper_id": "...",
                "arxiv_id": "..." (可能为 None),
                "paper_url": "...",
                "alias": "...",
                "summary": "...",
                "full_name": "...",
                "company_name": "..."  # 中文名称
            },
            ...
        ]
        """
        # 从数据库加载关注公司配置
        watched_companies = self.get_all_watched_companies()
        
        # 按名称分组，构建匹配规则映射
        company_mapping = {}
        for item in watched_companies:
            name = item["name"]
            match_rule = item["match_rule"]
            if name not in company_mapping:
                company_mapping[name] = []
            company_mapping[name].append(match_rule)
        
        # 分离精确匹配和通配符模式
        exact_names = []
        wildcard_patterns = []  # [(pattern, chinese_name), ...]
        english_to_chinese = {}
        
        for chinese_name, match_rules in company_mapping.items():
            for match_rule in match_rules:
                # 检查是否包含通配符（* 或 ?）
                if '*' in match_rule or '?' in match_rule:
                    # 转换为 SQL LIKE 模式：* -> %, ? -> _
                    sql_pattern = match_rule.replace('*', '%').replace('?', '_')
                    wildcard_patterns.append((sql_pattern, chinese_name))
                else:
                    exact_names.append(match_rule)
                    english_to_chinese[match_rule] = chinese_name
        
        # 使用英文名称查询数据库
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            results = []
            
            # 1. 精确匹配查询
            if exact_names:
                placeholders = ','.join(['?'] * len(exact_names))
                cursor.execute(f"""
                    SELECT p.paper_id, p.arxiv_id, p.paper_url, p.alias, p.summary, p.full_name, p.date, pc.company_name
                    FROM paper p
                    INNER JOIN paper_company pc ON p.paper_id = pc.paper_id
                    WHERE pc.company_name IN ({placeholders})
                    ORDER BY pc.company_name, p.paper_id
                """, exact_names)
                
                for paper_id, arxiv_id, paper_url, alias, summary, full_name, date, company_name_en in cursor.fetchall():
                    company_name_cn = english_to_chinese.get(company_name_en, company_name_en)
                    results.append({
                        "paper_id": paper_id,
                        "arxiv_id": arxiv_id,
                        "paper_url": paper_url,
                        "alias": alias or "",
                        "summary": summary or "",
                        "full_name": full_name or "",
                        "date": date or "",
                        "company_name": company_name_cn
                    })
            
            # 2. 通配符匹配查询
            for sql_pattern, chinese_name in wildcard_patterns:
                cursor.execute("""
                    SELECT p.paper_id, p.arxiv_id, p.paper_url, p.alias, p.summary, p.full_name, p.date, pc.company_name
                    FROM paper p
                    INNER JOIN paper_company pc ON p.paper_id = pc.paper_id
                    WHERE pc.company_name LIKE ?
                    ORDER BY pc.company_name, p.paper_id
                """, (sql_pattern,))
                
                for paper_id, arxiv_id, paper_url, alias, summary, full_name, date, company_name_en in cursor.fetchall():
                    # 检查是否已经添加过（避免重复）
                    if not any(r["paper_id"] == paper_id and r["company_name"] == chinese_name for r in results):
                        results.append({
                            "paper_id": paper_id,
                            "arxiv_id": arxiv_id,
                            "paper_url": paper_url,
                            "alias": alias or "",
                            "summary": summary or "",
                            "full_name": full_name or "",
                            "date": date or "",
                            "company_name": chinese_name
                        })
            
            return results
    
    def get_university_paper_matrix(self):
        """
        获取关注高校-论文矩阵数据
        从数据库读取关注高校配置，将中文名称映射到英文名称进行查询，返回时使用中文名称
        返回格式: [
            {
                "paper_id": "...",
                "arxiv_id": "..." (可能为 None),
                "paper_url": "...",
                "alias": "...",
                "summary": "...",
                "full_name": "...",
                "university_name": "..."  # 中文名称
            },
            ...
        ]
        """
        # 从数据库加载关注高校配置
        watched_universities = self.get_all_watched_universities()
        
        # 按名称分组，构建匹配规则映射
        university_mapping = {}
        for item in watched_universities:
            name = item["name"]
            match_rule = item["match_rule"]
            if name not in university_mapping:
                university_mapping[name] = []
            university_mapping[name].append(match_rule)
        
        # 分离精确匹配和通配符模式
        exact_names = []
        wildcard_patterns = []  # [(pattern, chinese_name), ...]
        english_to_chinese = {}
        
        for chinese_name, match_rules in university_mapping.items():
            for match_rule in match_rules:
                # 检查是否包含通配符（* 或 ?）
                if '*' in match_rule or '?' in match_rule:
                    # 转换为 SQL LIKE 模式：* -> %, ? -> _
                    sql_pattern = match_rule.replace('*', '%').replace('?', '_')
                    wildcard_patterns.append((sql_pattern, chinese_name))
                else:
                    exact_names.append(match_rule)
                    english_to_chinese[match_rule] = chinese_name
        
        # 使用英文名称查询数据库
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            results = []
            
            # 1. 精确匹配查询
            if exact_names:
                placeholders = ','.join(['?'] * len(exact_names))
                cursor.execute(f"""
                    SELECT p.paper_id, p.arxiv_id, p.paper_url, p.alias, p.summary, p.full_name, p.date, pu.university_name
                    FROM paper p
                    INNER JOIN paper_university pu ON p.paper_id = pu.paper_id
                    WHERE pu.university_name IN ({placeholders})
                    ORDER BY pu.university_name, p.paper_id
                """, exact_names)
                
                for paper_id, arxiv_id, paper_url, alias, summary, full_name, date, university_name_en in cursor.fetchall():
                    university_name_cn = english_to_chinese.get(university_name_en, university_name_en)
                    results.append({
                        "paper_id": paper_id,
                        "arxiv_id": arxiv_id,
                        "paper_url": paper_url,
                        "alias": alias or "",
                        "summary": summary or "",
                        "full_name": full_name or "",
                        "date": date or "",
                        "university_name": university_name_cn
                    })
            
            # 2. 通配符匹配查询
            for sql_pattern, chinese_name in wildcard_patterns:
                cursor.execute("""
                    SELECT p.paper_id, p.arxiv_id, p.paper_url, p.alias, p.summary, p.full_name, p.date, pu.university_name
                    FROM paper p
                    INNER JOIN paper_university pu ON p.paper_id = pu.paper_id
                    WHERE pu.university_name LIKE ?
                    ORDER BY pu.university_name, p.paper_id
                """, (sql_pattern,))
                
                for paper_id, arxiv_id, paper_url, alias, summary, full_name, date, university_name_en in cursor.fetchall():
                    # 检查是否已经添加过（避免重复）
                    if not any(r["paper_id"] == paper_id and r["university_name"] == chinese_name for r in results):
                        results.append({
                            "paper_id": paper_id,
                            "arxiv_id": arxiv_id,
                            "paper_url": paper_url,
                            "alias": alias or "",
                            "summary": summary or "",
                            "full_name": full_name or "",
                            "date": date or "",
                            "university_name": chinese_name
                        })
            
            return results


            



    def get_all_tags(self):
        """
        获取所有标签
        返回格式: [
            {
                "tag_id": 1,
                "tag_name": "a.b.c"
            },
            ...
        ]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tag_id, tag_name FROM tag ORDER BY tag_name
            """)
            results = []
            for tag_id, tag_name in cursor.fetchall():
                results.append({
                    "tag_id": tag_id,
                    "tag_name": tag_name
                })
            return results

    def get_paper_ids_matching_tag_glob(self, glob_pattern: str) -> set:
        """
        至少带有一个标签名匹配 glob 的论文 ID 集合（与关注 match_rule 相同：* -> %, ? -> _）。
        例如 venue.* 匹配 venue.NeurIPS、venue.ICLR 等。
        """
        p = (glob_pattern or "").strip()
        if not p:
            return set()
        sql_like = p.replace("*", "%").replace("?", "_")
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT pt.paper_id
                FROM paper_tag pt
                INNER JOIN tag t ON pt.tag_id = t.tag_id
                WHERE t.tag_name LIKE ?
                """,
                (sql_like,),
            )
            return {row[0] for row in cursor.fetchall()}
    
    def get_papers_by_tag(self, tag_id):
        """
        根据标签 ID 获取关联的论文
        返回格式: [
            {
                "paper_id": "...",
                "arxiv_id": "..." (可能为 None),
                "paper_url": "...",
                "alias": "...",
                "full_name": "...",
                "summary": "..."
            },
            ...
        ]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.paper_id, p.arxiv_id, p.paper_url, p.alias, p.full_name, p.summary
                FROM paper p
                INNER JOIN paper_tag pt ON p.paper_id = pt.paper_id
                WHERE pt.tag_id = ?
                ORDER BY
                    (CASE WHEN p.arxiv_id IS NOT NULL AND TRIM(p.arxiv_id) != '' THEN 1 ELSE 0 END) DESC,
                    p.arxiv_id DESC,
                    p.date DESC,
                    p.paper_id
            """, (tag_id,))
            results = []
            for paper_id, arxiv_id, paper_url, alias, full_name, summary in cursor.fetchall():
                results.append({
                    "paper_id": paper_id,
                    "arxiv_id": arxiv_id,
                    "paper_url": paper_url,
                    "alias": alias or "",
                    "full_name": full_name or "",
                    "summary": summary or ""
                })
            return results
    
    def get_top_level_tags(self):
        """
        获取所有一级标签（标签名称中第一个点号之前的部分）
        返回格式: [
            {
                "tag_name": "feedforward",
                "tag_id": 1 (如果一级标签本身存在) 或 None
            },
            ...
        ]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tag_id, tag_name FROM tag ORDER BY tag_name")
            top_level_tags = {}
            for tag_id, tag_name in cursor.fetchall():
                # 提取一级标签名称
                first_part = tag_name.split('.')[0]
                if first_part not in top_level_tags:
                    top_level_tags[first_part] = None
                # 如果整个标签名就是一级标签（没有点号），记录 tag_id
                if '.' not in tag_name:
                    top_level_tags[first_part] = tag_id
            
            results = []
            for tag_name, tag_id in top_level_tags.items():
                results.append({
                    "tag_name": tag_name,
                    "tag_id": tag_id
                })
            return sorted(results, key=lambda x: x["tag_name"])
    
    def get_tags_by_prefix(self, prefix):
        """
        获取所有以指定前缀开头的标签（包括前缀本身）
        prefix: 标签前缀，例如 "feedforward"
        返回格式: [
            {
                "tag_id": 1,
                "tag_name": "feedforward"
            },
            {
                "tag_id": 2,
                "tag_name": "feedforward.pose_aware"
            },
            ...
        ]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            # 匹配前缀本身或以 prefix. 开头的标签
            cursor.execute("""
                SELECT tag_id, tag_name FROM tag 
                WHERE tag_name = ? OR tag_name LIKE ?
                ORDER BY tag_name
            """, (prefix, f"{prefix}.%"))
            results = []
            for tag_id, tag_name in cursor.fetchall():
                results.append({
                    "tag_id": tag_id,
                    "tag_name": tag_name
                })
            return results
    
    def get_tag_paper_matrix(self, tag_ids):
        """
        获取标签-论文矩阵数据
        tag_ids: 标签 ID 列表
        返回格式: [
            {
                "paper_id": "...",
                "date": "202401",
                "tag_id": 1,
                "tag_name": "feedforward",
                "alias": "...",
                "full_name": "...",
                "summary": "...",
                "arxiv_id": "...",
                "paper_url": "..."
            },
            ...
        ]
        """
        if not tag_ids:
            return []
        
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            # 使用 IN 子句查询多个标签
            placeholders = ','.join(['?'] * len(tag_ids))
            cursor.execute(f"""
                SELECT p.paper_id, p.date, pt.tag_id, t.tag_name, p.alias, p.full_name, p.summary, p.arxiv_id, p.paper_url
                FROM paper p
                INNER JOIN paper_tag pt ON p.paper_id = pt.paper_id
                INNER JOIN tag t ON pt.tag_id = t.tag_id
                WHERE pt.tag_id IN ({placeholders})
                ORDER BY
                    (CASE WHEN p.arxiv_id IS NOT NULL AND TRIM(p.arxiv_id) != '' THEN 1 ELSE 0 END) DESC,
                    p.arxiv_id DESC,
                    p.date DESC,
                    p.paper_id
            """, tag_ids)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "paper_id": row[0],
                    "date": row[1] or "",
                    "tag_id": row[2],
                    "tag_name": row[3],
                    "alias": row[4] or "",
                    "full_name": row[5] or "",
                    "summary": row[6] or "",
                    "arxiv_id": row[7],
                    "paper_url": row[8]
                })
            return results
    
    def get_paper_tags(self, paper_id):
        """
        获取论文的所有标签
        返回格式: [
            {
                "tag_id": 1,
                "tag_name": "a.b.c"
            },
            ...
        ]
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.tag_id, t.tag_name
                FROM tag t
                INNER JOIN paper_tag pt ON t.tag_id = pt.tag_id
                WHERE pt.paper_id = ?
                ORDER BY t.tag_name
            """, (paper_id,))
            results = []
            for tag_id, tag_name in cursor.fetchall():
                results.append({
                    "tag_id": tag_id,
                    "tag_name": tag_name
                })
            return results
    
    def get_papers_by_tag_name(self, tag_name: str) -> list:
        """Return list of paper_ids that have the given tag."""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pt.paper_id
                FROM paper_tag pt
                INNER JOIN tag t ON pt.tag_id = t.tag_id
                WHERE t.tag_name = ?
            """, (tag_name,))
            return [row[0] for row in cursor.fetchall()]

    def update_github_url(self, paper_id: str, github_url: str) -> bool:
        """Update github_url for a paper (only if currently NULL or empty).

        Returns True if the update changed a row, False if paper not found or github_url already set.
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE paper SET github_url = ?
                WHERE paper_id = ? AND (github_url IS NULL OR github_url = '')
            """, (github_url, paper_id))
            return cursor.rowcount > 0

    def add_tag_to_paper(self, paper_id, tag_name):
        """
        为论文添加标签
        如果标签不存在，会自动创建
        paper_id: 论文 ID
        tag_name: 标签名称（例如 "a.b.c"）
        返回: (tag_id, created) - tag_id 是标签 ID，created 表示标签是否是新创建的
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            
            # 检查标签是否存在
            cursor.execute("SELECT tag_id FROM tag WHERE tag_name = ?", (tag_name,))
            result = cursor.fetchone()
            
            if result:
                tag_id = result[0]
                created = False
            else:
                # 创建新标签
                cursor.execute("INSERT INTO tag (tag_name) VALUES (?)", (tag_name,))
                tag_id = cursor.lastrowid
                created = True
            
            # 检查论文和标签的关联是否已存在
            cursor.execute("""
                SELECT 1 FROM paper_tag 
                WHERE paper_id = ? AND tag_id = ?
            """, (paper_id, tag_id))
            
            if not cursor.fetchone():
                # 添加关联
                cursor.execute("""
                    INSERT INTO paper_tag (paper_id, tag_id) 
                    VALUES (?, ?)
                """, (paper_id, tag_id))
            
            conn.commit()
            return tag_id, created
    
    def remove_tag_from_paper(self, paper_id, tag_id):
        """
        从论文中移除标签
        paper_id: 论文 ID
        tag_id: 标签 ID
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM paper_tag 
                WHERE paper_id = ? AND tag_id = ?
            """, (paper_id, tag_id))
            conn.commit()
    
    def delete_tag(self, tag_id):
        """
        删除标签（会自动删除所有 paper_tag 关联记录，因为外键约束 ON DELETE CASCADE）
        tag_id: 标签 ID
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            # 删除标签（paper_tag 中的记录会自动删除）
            cursor.execute("""
                DELETE FROM tag 
                WHERE tag_id = ?
            """, (tag_id,))
            conn.commit()
    
    def update_tag_name(self, tag_id, new_tag_name):
        """
        更新标签名称
        如果新标签名已存在，则合并标签（将当前标签的论文关联到已存在的标签，然后删除当前标签）
        tag_id: 标签 ID
        new_tag_name: 新的标签名称
        """
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            
            # 检查新标签名是否已存在（且不是当前标签）
            cursor.execute("SELECT tag_id FROM tag WHERE tag_name = ?", (new_tag_name,))
            existing_tag = cursor.fetchone()
            
            if existing_tag and existing_tag[0] != tag_id:
                # 新标签名已存在，需要合并
                existing_tag_id = existing_tag[0]
                
                # 获取当前标签关联的所有论文ID
                cursor.execute("""
                    SELECT paper_id FROM paper_tag WHERE tag_id = ?
                """, (tag_id,))
                paper_ids = [row[0] for row in cursor.fetchall()]
                
                # 将这些论文关联到已存在的标签（如果还没有关联的话）
                for paper_id in paper_ids:
                    # 检查是否已经有关联
                    cursor.execute("""
                        SELECT 1 FROM paper_tag 
                        WHERE paper_id = ? AND tag_id = ?
                    """, (paper_id, existing_tag_id))
                    if not cursor.fetchone():
                        # 添加关联
                        cursor.execute("""
                            INSERT INTO paper_tag (paper_id, tag_id) 
                            VALUES (?, ?)
                        """, (paper_id, existing_tag_id))
                
                # 删除当前标签（会自动删除所有 paper_tag 关联记录）
                cursor.execute("""
                    DELETE FROM tag 
                    WHERE tag_id = ?
                """, (tag_id,))
            else:
                # 新标签名不存在或就是当前标签，直接更新
                cursor.execute("""
                    UPDATE tag 
                    SET tag_name = ? 
                    WHERE tag_id = ?
                """, (new_tag_name, tag_id))
            
            conn.commit()

    @staticmethod
    def _venue_tag_without_trailing_year(tag_name: str) -> Optional[str]:
        """
        venue.NeurIPS2024 -> venue.NeurIPS；已是 venue.ICLR 或无法识别则返回 None。
        与 ai_api 去掉年份的规则一致（末尾 4 位为 1990–2100 的年份）。
        """
        from config import TAG_SEPARATOR, VENUE_TAG_PREFIX

        prefix = f"{VENUE_TAG_PREFIX}{TAG_SEPARATOR}"
        if not tag_name.startswith(prefix):
            return None
        rest = tag_name[len(prefix) :]
        m = re.match(r"^(.+)(\d{4})$", rest)
        if not m:
            return None
        y = int(m.group(2))
        if not (1990 <= y <= 2100):
            return None
        base = m.group(1)
        if not base:
            return None
        return prefix + base

    def migrate_venue_tags_strip_year(self, dry_run: bool = False) -> dict:
        """
        将库中 venue.* 标签去掉末尾年份（venue.NeurIPS2024 -> venue.NeurIPS）。
        依赖已有 update_tag_name 的合并逻辑处理同名冲突。

        :param dry_run: 为 True 时不写库，仅统计与列出将变更项
        :return: {"examined", "changed", "unchanged", "moves": [(old, new, tag_id), ...]}
        """
        from config import TAG_SEPARATOR, VENUE_TAG_PREFIX

        prefix = f"{VENUE_TAG_PREFIX}{TAG_SEPARATOR}"
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT tag_id, tag_name FROM tag WHERE tag_name LIKE ? ORDER BY tag_id",
                (prefix + "%",),
            )
            rows: List[Tuple[int, str]] = cursor.fetchall()

        moves = []
        examined = 0
        unchanged = 0
        for tag_id, tag_name in rows:
            examined += 1
            new_name = self._venue_tag_without_trailing_year(tag_name)
            if new_name is None or new_name == tag_name:
                unchanged += 1
                continue
            moves.append((tag_name, new_name, tag_id))
            if not dry_run:
                self.update_tag_name(tag_id, new_name)

        return {
            "examined": examined,
            "changed": len(moves),
            "unchanged": unchanged,
            "moves": moves,
            "dry_run": dry_run,
        }
    
    # ========== 关注公司管理方法 ==========
    def get_all_watched_companies(self):
        """获取所有关注公司配置，按名称分组"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, match_rule 
                FROM watched_company 
                ORDER BY name, id
            """)
            results = []
            for id_val, name, match_rule in cursor.fetchall():
                results.append({
                    "id": id_val,
                    "name": name,
                    "match_rule": match_rule
                })
            return results
    
    def add_watched_company(self, name, match_rule):
        """添加关注公司配置"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO watched_company (name, match_rule) 
                VALUES (?, ?)
            """, (name, match_rule))
            conn.commit()
            return cursor.lastrowid
    
    def update_watched_company(self, id_val, name=None, match_rule=None):
        """更新关注公司配置"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if match_rule is not None:
                updates.append("match_rule = ?")
                params.append(match_rule)
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(id_val)
                cursor.execute(f"""
                    UPDATE watched_company 
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, params)
                conn.commit()
    
    def delete_watched_company(self, id_val):
        """删除关注公司配置"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM watched_company 
                WHERE id = ?
            """, (id_val,))
            conn.commit()
    
    # ========== 关注高校管理方法 ==========
    def get_all_watched_universities(self):
        """获取所有关注高校配置，按名称分组"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, match_rule 
                FROM watched_university 
                ORDER BY name, id
            """)
            results = []
            for id_val, name, match_rule in cursor.fetchall():
                results.append({
                    "id": id_val,
                    "name": name,
                    "match_rule": match_rule
                })
            return results
    
    def add_watched_university(self, name, match_rule):
        """添加关注高校配置"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO watched_university (name, match_rule) 
                VALUES (?, ?)
            """, (name, match_rule))
            conn.commit()
            return cursor.lastrowid
    
    def update_watched_university(self, id_val, name=None, match_rule=None):
        """更新关注高校配置"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if match_rule is not None:
                updates.append("match_rule = ?")
                params.append(match_rule)
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(id_val)
                cursor.execute(f"""
                    UPDATE watched_university 
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, params)
                conn.commit()
    
    def delete_watched_university(self, id_val):
        """删除关注高校配置"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM watched_university 
                WHERE id = ?
            """, (id_val,))
            conn.commit()
    
    # ========== 关注作者管理方法 ==========
    def get_all_watched_authors(self):
        """获取所有关注作者配置，按名称分组"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, match_rule 
                FROM watched_author 
                ORDER BY name, id
            """)
            results = []
            for id_val, name, match_rule in cursor.fetchall():
                results.append({
                    "id": id_val,
                    "name": name,
                    "match_rule": match_rule
                })
            return results
    
    def add_watched_author(self, name, match_rule):
        """添加关注作者配置"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO watched_author (name, match_rule) 
                VALUES (?, ?)
            """, (name, match_rule))
            conn.commit()
            return cursor.lastrowid
    
    def update_watched_author(self, id_val, name=None, match_rule=None):
        """更新关注作者配置"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if match_rule is not None:
                updates.append("match_rule = ?")
                params.append(match_rule)
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(id_val)
                cursor.execute(f"""
                    UPDATE watched_author 
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, params)
                conn.commit()
    
    def delete_watched_author(self, id_val):
        """删除关注作者配置"""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM watched_author 
                WHERE id = ?
            """, (id_val,))
            conn.commit()
    
    def clean_duplicate_arxiv_versions(self, dry_run=True):
        """
        清理数据库中 arxiv_id 的重复版本，只保留最新版本
        
        例如：如果存在 2401.12345 和 2401.12345v1，只保留 v1 版本
        
        Args:
            dry_run: 如果为 True，只报告将要删除的记录，不实际删除
        
        Returns:
            {
                'total_groups': 找到的重复组数,
                'total_to_delete': 将要删除的记录数,
                'details': [(base_id, kept_version, deleted_versions), ...]
            }
        """
        import re
        
        def get_base_arxiv_id(arxiv_id):
            """获取基础 arxiv_id（移除版本号）"""
            if not arxiv_id:
                return None
            # 移除版本号部分（v1, v2等）
            return re.sub(r'v\d+$', '', arxiv_id)
        
        def get_version_number(arxiv_id):
            """获取版本号，如果没有版本号返回 0"""
            if not arxiv_id:
                return 0
            match = re.search(r'v(\d+)$', arxiv_id)
            if match:
                return int(match.group(1))
            return 0
        
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            
            # 获取所有有 arxiv_id 的记录
            cursor.execute("""
                SELECT paper_id, arxiv_id FROM paper 
                WHERE arxiv_id IS NOT NULL
            """)
            all_papers = cursor.fetchall()
            
            # 按基础 arxiv_id 分组
            groups = {}
            for paper_id, arxiv_id in all_papers:
                base_id = get_base_arxiv_id(arxiv_id)
                if base_id not in groups:
                    groups[base_id] = []
                groups[base_id].append((paper_id, arxiv_id))
            
            # 找出有重复的组
            duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
            
            if not duplicate_groups:
                return {
                    'total_groups': 0,
                    'total_to_delete': 0,
                    'details': []
                }
            
            # 对于每个重复组，找出要保留的版本（版本号最高的）
            to_delete = []
            details = []
            
            for base_id, papers in duplicate_groups.items():
                # 按版本号排序（降序），版本号最高的在前
                sorted_papers = sorted(papers, key=lambda x: get_version_number(x[1]), reverse=True)
                
                # 保留版本号最高的
                kept = sorted_papers[0]
                deleted = sorted_papers[1:]
                
                # 记录要删除的 paper_id
                for paper_id, arxiv_id in deleted:
                    to_delete.append(paper_id)
                
                details.append({
                    'base_id': base_id,
                    'kept': kept[1],
                    'kept_paper_id': kept[0],
                    'deleted': [arxiv_id for _, arxiv_id in deleted],
                    'deleted_paper_ids': [paper_id for paper_id, _ in deleted]
                })
            
            if not dry_run and to_delete:
                # 实际删除记录
                # 注意：需要先删除关联表中的记录（外键约束）
                placeholders = ','.join(['?'] * len(to_delete))
                
                # 删除关联表记录
                cursor.execute(f"""
                    DELETE FROM paper_tag WHERE paper_id IN ({placeholders})
                """, to_delete)
                cursor.execute(f"""
                    DELETE FROM paper_company WHERE paper_id IN ({placeholders})
                """, to_delete)
                cursor.execute(f"""
                    DELETE FROM paper_university WHERE paper_id IN ({placeholders})
                """, to_delete)
                cursor.execute(f"""
                    DELETE FROM paper_author WHERE paper_id IN ({placeholders})
                """, to_delete)
                
                # 删除主表记录
                cursor.execute(f"""
                    DELETE FROM paper WHERE paper_id IN ({placeholders})
                """, to_delete)
                
                conn.commit()
            
            return {
                'total_groups': len(duplicate_groups),
                'total_to_delete': len(to_delete),
                'details': details
            }



if __name__ == "__main__":
    db_path = "./data/database.db"
    database = Database(db_path)
    database.construct()
    #data = [("2505.23716", "test")]
    #database.update_papaer_abstract(data)
