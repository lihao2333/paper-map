from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List, Dict, Any
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database import Database, paper_list_sort_key
from backend.schemas import Tag, TagCreate, TagUpdate, TagTreeNode, PaperTagRequest

router = APIRouter(prefix="/tags", tags=["tags"])


def get_db():
    db_path = Path(__file__).parent.parent.parent / "data" / "database.db"
    return Database(str(db_path))


def build_tag_tree(tags: List[Dict], db: Database) -> List[TagTreeNode]:
    """构建标签树"""
    tree: Dict[str, Any] = {}
    
    for tag in tags:
        tag_name = tag["tag_name"]
        tag_id = tag["tag_id"]
        
        # 获取该标签的论文数量
        papers = db.get_papers_by_tag(tag_id)
        paper_count = len(papers)
        
        parts = tag_name.split(".")
        current = tree
        
        for i, part in enumerate(parts):
            if part not in current:
                current[part] = {
                    "_children": {},
                    "_tag_id": None,
                    "_full_path": ".".join(parts[:i+1]),
                    "_paper_count": 0
                }
            
            if i == len(parts) - 1:
                current[part]["_tag_id"] = tag_id
                current[part]["_paper_count"] = paper_count
            
            current = current[part]["_children"]
    
    def convert_to_nodes(subtree: Dict, prefix: str = "") -> List[TagTreeNode]:
        nodes = []
        for name, data in subtree.items():
            if name.startswith("_"):
                continue
            
            full_path = data.get("_full_path", name)
            children = convert_to_nodes(data.get("_children", {}), full_path)
            
            total_count = data.get("_paper_count", 0)
            for child in children:
                total_count += child.paper_count
            
            nodes.append(TagTreeNode(
                tag_id=data.get("_tag_id"),
                tag_name=name,
                full_path=full_path,
                children=children,
                paper_count=total_count
            ))
        
        return sorted(nodes, key=lambda x: x.tag_name)
    
    return convert_to_nodes(tree)


@router.get("", response_model=List[Tag])
async def list_tags(db: Database = Depends(get_db)):
    """获取所有标签列表"""
    tags = db.get_all_tags()
    result = []
    for tag in tags:
        papers = db.get_papers_by_tag(tag["tag_id"])
        result.append(Tag(
            tag_id=tag["tag_id"],
            tag_name=tag["tag_name"],
            paper_count=len(papers)
        ))
    return result


@router.get("/tree", response_model=List[TagTreeNode])
async def get_tag_tree(db: Database = Depends(get_db)):
    """获取标签树"""
    tags = db.get_all_tags()
    return build_tag_tree(tags, db)


@router.get("/top-level")
async def get_top_level_tags(db: Database = Depends(get_db)):
    """获取所有一级标签"""
    return db.get_top_level_tags()


@router.get("/{tag_id}", response_model=Tag)
async def get_tag(tag_id: int, db: Database = Depends(get_db)):
    """获取单个标签详情"""
    tags = db.get_all_tags()
    tag = next((t for t in tags if t["tag_id"] == tag_id), None)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    papers = db.get_papers_by_tag(tag_id)
    return Tag(
        tag_id=tag["tag_id"],
        tag_name=tag["tag_name"],
        paper_count=len(papers)
    )


@router.get("/{tag_id}/papers")
async def get_tag_papers(tag_id: int, db: Database = Depends(get_db)):
    """获取标签关联的论文"""
    papers = db.get_papers_by_tag(tag_id)
    return papers


def _build_hover_info(db: Database, paper_id: str) -> Dict:
    """构建论文 hover 信息，与 matrix.build_hover_info_from_dict 格式一致"""
    info = db.get_paper_info(paper_id=paper_id)
    if not info:
        return {}
    tags = db.get_paper_tags(paper_id)
    tag_names = [t["tag_name"] for t in tags] if tags else []
    tags_with_id = [{"tag_id": t["tag_id"], "tag_name": t["tag_name"]} for t in tags] if tags else []
    summary = info.get("summary") or ""
    summary_trunc = summary[:300] + ("..." if len(summary) > 300 else "")
    return {
        "full_name": info.get("full_name", ""),
        "abstract": info.get("abstract", ""),
        "summary": summary_trunc,
        "company_names": info.get("company_names", []),
        "university_names": info.get("university_names", []),
        "author_names": info.get("author_names", []),
        "tag_names": tag_names,
        "tags": tags_with_id,
        "date": info.get("date", ""),
        "paper_id": info.get("paper_id", ""),
        "arxiv_id": info.get("arxiv_id"),
        "paper_url": info.get("paper_url", ""),
    }


@router.get("/prefix/{prefix}/matrix")
async def get_tag_matrix(prefix: str, db: Database = Depends(get_db)):
    """获取指定前缀的标签矩阵"""
    tags = db.get_tags_by_prefix(prefix)
    if not tags:
        return {"tags": [], "papers": []}
    
    tag_ids = [t["tag_id"] for t in tags]
    matrix_data = db.get_tag_paper_matrix(tag_ids)
    
    # 透视数据
    tag_names = sorted(set(item["tag_name"] for item in matrix_data))
    papers_map: Dict[str, Dict] = {}
    
    for item in matrix_data:
        paper_id = item["paper_id"]
        if paper_id not in papers_map:
            papers_map[paper_id] = {
                "paper_id": paper_id,
                "date": item.get("date", ""),
                "arxiv_id": item.get("arxiv_id"),
                "paper_url": item.get("paper_url", ""),
                "cells": {},
                "hover_info": _build_hover_info(db, paper_id),
            }
        papers_map[paper_id]["cells"][item["tag_name"]] = {
            "alias": item.get("alias", ""),
            "full_name": item.get("full_name", ""),
            "summary": item.get("summary", "")
        }
    
    rows = list(papers_map.values())
    rows.sort(key=paper_list_sort_key, reverse=True)
    
    return {
        "tags": tag_names,
        "papers": rows
    }


@router.post("")
async def create_tag(tag: TagCreate, db: Database = Depends(get_db)):
    """创建新标签"""
    tags = db.get_all_tags()
    existing = next((t for t in tags if t["tag_name"] == tag.tag_name), None)
    if existing:
        raise HTTPException(status_code=400, detail="Tag already exists")
    
    # 使用 add_tag_to_paper 创建标签（传入一个虚拟 paper_id 然后删除关联）
    # 或者直接执行 SQL
    import sqlite3
    db_path = Path(__file__).parent.parent.parent / "data" / "database.db"
    
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tag (tag_name) VALUES (?)", (tag.tag_name,))
        tag_id = cursor.lastrowid
        conn.commit()
    
    return {"tag_id": tag_id, "tag_name": tag.tag_name}


@router.put("/{tag_id}")
async def update_tag(tag_id: int, tag: TagUpdate, db: Database = Depends(get_db)):
    """更新标签名称"""
    db.update_tag_name(tag_id, tag.tag_name)
    return {"message": "Tag updated successfully"}


@router.delete("/{tag_id}")
async def delete_tag(tag_id: int, db: Database = Depends(get_db)):
    """删除标签"""
    db.delete_tag(tag_id)
    return {"message": "Tag deleted successfully"}


@router.post("/paper")
async def add_tag_to_paper(request: PaperTagRequest, db: Database = Depends(get_db)):
    """为论文添加标签"""
    tag_id, created = db.add_tag_to_paper(request.paper_id, request.tag_name)
    return {"tag_id": tag_id, "created": created}


@router.delete("/paper/{paper_id}/{tag_id}")
async def remove_tag_from_paper(paper_id: str, tag_id: int, db: Database = Depends(get_db)):
    """从论文移除标签"""
    db.remove_tag_from_paper(paper_id, tag_id)
    return {"message": "Tag removed from paper"}
