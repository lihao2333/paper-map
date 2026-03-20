from fastapi import APIRouter, Depends, Query
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database import Database, paper_list_sort_key
from backend.schemas import CompanyMatrixResponse, UniversityMatrixResponse, AuthorMatrixResponse

router = APIRouter(prefix="/matrix", tags=["matrix"])


def get_db():
    db_path = Path(__file__).parent.parent.parent / "data" / "database.db"
    return Database(str(db_path))


def build_hover_info_from_dict(
    info: Optional[Dict],
    tags: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """从批量查询结果组装 hover 信息（纯函数，无 DB 调用），与标签矩阵 _build_hover_info 格式一致"""
    if not info:
        return {}
    summary = info.get("summary") or ""
    summary_trunc = summary[:300] + ("..." if len(summary) > 300 else "")
    abstract = info.get("abstract") or ""
    ac = (info.get("arxiv_comments") or "").strip()
    arxiv_comments_trunc = ac[:500] + ("..." if len(ac) > 500 else "") if ac else ""
    tag_names = [t["tag_name"] for t in tags] if tags else []
    return {
        "full_name": info.get("full_name", ""),
        "abstract": abstract,
        "summary": summary_trunc,
        "arxiv_comments": arxiv_comments_trunc,
        "company_names": info.get("company_names", []),
        "university_names": info.get("university_names", []),
        "author_names": info.get("author_names", []),
        "tag_names": tag_names,
        "tags": tags,
        "date": info.get("date", ""),
        "paper_id": info.get("paper_id", ""),
        "arxiv_id": info.get("arxiv_id"),
        "paper_url": info.get("paper_url", ""),
        "github_url": info.get("github_url"),
    }


def pivot_matrix(data: List[Dict], group_key: str, db: Optional[Database] = None) -> Dict[str, Any]:
    """将矩阵数据转换为透视表格式，可选添加 hover_info（批量查询，避免 N+1）"""
    if not data:
        return {"headers": [], "rows": []}
    
    # 获取所有唯一的分组名称
    groups = sorted(set(item[group_key] for item in data))
    
    # 第一遍：按 paper_id 分组，仅构建 papers_map 和 cells，不调用 build_hover_info
    papers_map: Dict[str, Dict] = {}
    for item in data:
        paper_id = item["paper_id"]
        if paper_id not in papers_map:
            papers_map[paper_id] = {
                "paper_id": paper_id,
                "date": item.get("date", ""),
                "arxiv_id": item.get("arxiv_id"),
                "paper_url": item.get("paper_url", ""),
                "cells": {},
            }
        papers_map[paper_id]["cells"][item[group_key]] = {
            "alias": item.get("alias", ""),
            "full_name": item.get("full_name", ""),
            "summary": item.get("summary", ""),
        }
    
    # 批量加载 hover_info：2 次查询替代 2N 次
    if db:
        paper_ids = list(papers_map.keys())
        info_map = db.get_papers_info_batch(paper_ids)
        tags_map = db.get_papers_tags_batch(paper_ids)
        for paper_id, row in papers_map.items():
            info = info_map.get(paper_id)
            tags = tags_map.get(paper_id, [])
            row["hover_info"] = build_hover_info_from_dict(info, tags)
    
    # 转换为列表并按日期排序
    rows = list(papers_map.values())
    rows.sort(key=paper_list_sort_key, reverse=True)
    
    return {
        "headers": groups,
        "rows": rows,
    }


def resolve_matrix_tag_patterns(
    tag_rules: Optional[str],
    tag_rule: Optional[str],
) -> Optional[List[str]]:
    """
    解析矩阵标签筛选：多条 glob 为 OR（命中任一即保留）。
    - tag_rules 优先：逗号分隔多个模式；空字符串表示不按标签筛选。
    - 仅 tag_rule（旧参数）：单个模式；空字符串表示不按标签筛选。
    - 二者皆未传：不按标签筛选（与空 tag_rules 一致）。
    """
    if tag_rules is not None:
        s = tag_rules.strip()
        if s == "":
            return None
        parts = [p.strip() for p in s.split(",") if p.strip()]
        return parts if parts else None
    if tag_rule is not None:
        s = tag_rule.strip()
        if s == "":
            return None
        return [s]
    return None


def filter_matrix_by_tag_patterns(
    data: List[Dict],
    patterns: Optional[List[str]],
    db: Database,
) -> List[Dict]:
    if not patterns:
        return data
    allowed: set = set()
    for p in patterns:
        allowed |= db.get_paper_ids_matching_tag_glob(p)
    return [row for row in data if row["paper_id"] in allowed]


@router.get("/companies")
async def get_company_matrix(
    tag_rules: Optional[str] = Query(
        None,
        description="逗号分隔的多个标签 glob（OR）；未传或空字符串表示不按标签筛选",
    ),
    tag_rule: Optional[str] = Query(
        None,
        description="兼容旧版单个 glob；与 tag_rules 同时出现时以 tag_rules 为准",
    ),
    db: Database = Depends(get_db),
):
    """获取公司-论文矩阵"""
    data = db.get_car_company_paper_matrix()
    patterns = resolve_matrix_tag_patterns(tag_rules, tag_rule)
    data = filter_matrix_by_tag_patterns(data, patterns, db)
    result = pivot_matrix(data, "company_name", db)
    return {
        "companies": result["headers"],
        "papers": result["rows"]
    }


@router.get("/universities")
async def get_university_matrix(
    tag_rules: Optional[str] = Query(
        None,
        description="逗号分隔的多个标签 glob（OR）；未传或空字符串表示不按标签筛选",
    ),
    tag_rule: Optional[str] = Query(
        None,
        description="兼容旧版单个 glob；与 tag_rules 同时出现时以 tag_rules 为准",
    ),
    db: Database = Depends(get_db),
):
    """获取高校-论文矩阵"""
    data = db.get_university_paper_matrix()
    patterns = resolve_matrix_tag_patterns(tag_rules, tag_rule)
    data = filter_matrix_by_tag_patterns(data, patterns, db)
    result = pivot_matrix(data, "university_name", db)
    return {
        "universities": result["headers"],
        "papers": result["rows"]
    }


@router.get("/authors")
async def get_author_matrix(
    tag_rules: Optional[str] = Query(
        None,
        description="逗号分隔的多个标签 glob（OR）；未传或空字符串表示不按标签筛选",
    ),
    tag_rule: Optional[str] = Query(
        None,
        description="兼容旧版单个 glob；与 tag_rules 同时出现时以 tag_rules 为准",
    ),
    db: Database = Depends(get_db),
):
    """获取作者-论文矩阵"""
    data = db.get_watched_author_paper_matrix()
    patterns = resolve_matrix_tag_patterns(tag_rules, tag_rule)
    data = filter_matrix_by_tag_patterns(data, patterns, db)
    result = pivot_matrix(data, "author_name", db)
    return {
        "authors": result["headers"],
        "papers": result["rows"]
    }
