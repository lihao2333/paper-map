from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database import Database
from backend.schemas import Paper, PaperCreate, PaperUpdate, PaperListResponse

router = APIRouter(prefix="/papers", tags=["papers"])


def get_db():
    db_path = Path(__file__).parent.parent.parent / "data" / "database.db"
    return Database(str(db_path))


# ==================== 补全接口（必须在 /{paper_id} 之前定义） ====================

@router.post("/complete-authors")
async def complete_authors(db: Database = Depends(get_db)):
    """为缺少作者信息的 arXiv 论文从 arXiv API 拉取作者并写入数据库"""
    try:
        from arxiv_api import ArxivApi
    except ImportError:
        raise HTTPException(status_code=501, detail="arxiv_api not available")
    
    arxiv_ids = db.get_arxiv_ids_having_no_authors()
    if not arxiv_ids:
        return {"message": "No papers need author completion", "completed": 0}
    
    api = ArxivApi()
    updated = 0
    errors = []
    for arxiv_id in arxiv_ids:
        try:
            author_names = api.get_author_names(arxiv_id)
            if author_names:
                paper_id = arxiv_id  # arXiv 论文 paper_id = arxiv_id
                db.update_paper_info([{"paper_id": paper_id, "author_names": author_names}])
                updated += 1
        except Exception as e:
            errors.append({"arxiv_id": arxiv_id, "error": str(e)})
    
    return {"message": f"Completed authors for {updated} papers", "completed": updated, "total": len(arxiv_ids), "errors": errors[:10]}


@router.post("/complete-summaries")
async def complete_summaries(db: Database = Depends(get_db)):
    """为有摘要但缺 AI 总结的论文生成 AI 总结"""
    try:
        from ai_api import AiApi
    except ImportError:
        raise HTTPException(status_code=501, detail="ai_api not available")
    
    all_papers = db.get_all_papers_with_details()
    need_summary = [p for p in all_papers if (p.get("abstract")) and not (p.get("summary") or "").strip()]
    if not need_summary:
        return {"message": "No papers need summary completion", "completed": 0}
    
    api = AiApi()
    updated = 0
    errors = []
    for p in need_summary:
        try:
            summary = api.summary(p["abstract"])
            if summary:
                db.update_paper_info([{"paper_id": p["paper_id"], "summary": summary.strip()}])
                updated += 1
        except Exception as e:
            errors.append({"paper_id": p["paper_id"], "error": str(e)})
    
    return {"message": f"Completed summaries for {updated} papers", "completed": updated, "total": len(need_summary), "errors": errors[:10]}


def get_db():
    db_path = Path(__file__).parent.parent.parent / "data" / "database.db"
    return Database(str(db_path))


@router.get("", response_model=PaperListResponse)
async def list_papers(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    tag: Optional[str] = None,
    company: Optional[str] = None,
    university: Optional[str] = None,
    author: Optional[str] = None,
    db: Database = Depends(get_db),
):
    """获取论文列表，支持分页、搜索和筛选（DB 侧筛选 + 当前页批量加载 debug 视图字段）"""
    total, page_papers = db.list_papers_paginated(
        page,
        page_size,
        search=search,
        tag=tag,
        company=company,
        university=university,
        author=author,
    )
    return PaperListResponse(
        items=[Paper(**p) for p in page_papers],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{paper_id}", response_model=Paper)
async def get_paper(paper_id: str, db: Database = Depends(get_db)):
    """获取单个论文详情"""
    paper = db.get_paper_info(paper_id=paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    paper_tags = db.get_paper_tags(paper_id)
    paper["tags"] = [t["tag_name"] for t in paper_tags]
    
    return Paper(**paper)


@router.post("", response_model=Paper)
async def create_paper(paper: PaperCreate, db: Database = Depends(get_db)):
    """创建新论文"""
    paper_data = paper.model_dump()
    
    if not paper_data.get("paper_id"):
        if paper_data.get("arxiv_id"):
            paper_data["paper_id"] = paper_data["arxiv_id"]
        else:
            import uuid
            paper_data["paper_id"] = str(uuid.uuid4())[:8]
    
    db.insert_paper([paper_data])
    
    created = db.get_paper_info(paper_id=paper_data["paper_id"])
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create paper")
    
    created["tags"] = []
    return Paper(**created)


@router.put("/{paper_id}", response_model=Paper)
async def update_paper(paper_id: str, paper: PaperUpdate, db: Database = Depends(get_db)):
    """更新论文信息"""
    existing = db.get_paper_info(paper_id=paper_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    update_data = paper.model_dump(exclude_unset=True)
    update_data["paper_id"] = paper_id
    
    db.update_paper_info([update_data])
    
    updated = db.get_paper_info(paper_id=paper_id)
    paper_tags = db.get_paper_tags(paper_id)
    updated["tags"] = [t["tag_name"] for t in paper_tags]
    
    return Paper(**updated)


@router.delete("/{paper_id}")
async def delete_paper(paper_id: str, db: Database = Depends(get_db)):
    """删除论文"""
    existing = db.get_paper_info(paper_id=paper_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # 由于 database.py 没有 delete_paper 方法，我们需要直接执行 SQL
    import sqlite3
    db_path = Path(__file__).parent.parent.parent / "data" / "database.db"
    
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM paper_tag WHERE paper_id = ?", (paper_id,))
        cursor.execute("DELETE FROM paper_company WHERE paper_id = ?", (paper_id,))
        cursor.execute("DELETE FROM paper_university WHERE paper_id = ?", (paper_id,))
        cursor.execute("DELETE FROM paper_author WHERE paper_id = ?", (paper_id,))
        cursor.execute("DELETE FROM paper WHERE paper_id = ?", (paper_id,))
        conn.commit()
    
    return {"message": "Paper deleted successfully"}


@router.get("/search/autocomplete")
async def search_autocomplete(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: Database = Depends(get_db),
):
    """搜索自动补全"""
    results = db.search_paper(q)
    return results[:limit]
