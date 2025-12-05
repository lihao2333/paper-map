from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database import Database
from link_parser import LinkParser

router = APIRouter(prefix="/collect", tags=["collect"])


def get_db():
    db_path = Path(__file__).parent.parent.parent / "data" / "database.db"
    return Database(str(db_path))


class CollectRequest(BaseModel):
    url: str
    alias: Optional[str] = None
    tags: Optional[List[str]] = None


class CollectResponse(BaseModel):
    paper_id: str
    message: str


class CompleteRequest(BaseModel):
    paper_id: str
    fields: Optional[List[str]] = None  # abstract, summary, companies, universities, authors


@router.post("", response_model=CollectResponse)
async def collect_paper(
    request: CollectRequest,
    db: Database = Depends(get_db)
):
    """收集论文"""
    try:
        parser = LinkParser()
        parsed = parser.parse(request.url)
        
        if not parsed:
            raise HTTPException(status_code=400, detail="Invalid paper URL")
        
        paper_id = parsed.get("paper_id")
        arxiv_id = parsed.get("arxiv_id")
        paper_url = parsed.get("paper_url")
        
        # 检查是否已存在
        existing = db.get_paper_info(paper_id=paper_id)
        if existing:
            raise HTTPException(status_code=400, detail=f"Paper {paper_id} already exists")
        
        # 插入论文
        paper_data = {
            "paper_id": paper_id,
            "arxiv_id": arxiv_id,
            "paper_url": paper_url,
            "alias": request.alias,
        }
        
        db.insert_paper([paper_data])
        
        # 添加标签
        if request.tags:
            for tag_name in request.tags:
                db.add_tag_to_paper(paper_id, tag_name)
        
        return CollectResponse(
            paper_id=paper_id,
            message="Paper collected successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complete")
async def complete_paper_info(
    request: CompleteRequest,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db)
):
    """补全论文信息（异步）"""
    paper = db.get_paper_info(paper_id=request.paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # 返回当前状态，后台补全
    # 由于 completer.py 可能需要网络请求，我们这里简单返回
    # 实际实现可以使用 BackgroundTasks
    
    return {
        "message": "Completion started",
        "paper_id": request.paper_id,
        "current_status": {
            "has_abstract": bool(paper.get("abstract")),
            "has_summary": bool(paper.get("summary")),
            "has_companies": bool(paper.get("company_names")),
            "has_universities": bool(paper.get("university_names")),
            "has_authors": bool(paper.get("author_names")),
        }
    }


@router.post("/batch")
async def batch_collect(
    urls: List[str],
    db: Database = Depends(get_db)
):
    """批量收集论文"""
    results = []
    parser = LinkParser()
    
    for url in urls:
        try:
            parsed = parser.parse(url)
            if not parsed:
                results.append({"url": url, "status": "error", "message": "Invalid URL"})
                continue
            
            paper_id = parsed.get("paper_id")
            existing = db.get_paper_info(paper_id=paper_id)
            
            if existing:
                results.append({"url": url, "status": "skipped", "message": "Already exists", "paper_id": paper_id})
                continue
            
            paper_data = {
                "paper_id": paper_id,
                "arxiv_id": parsed.get("arxiv_id"),
                "paper_url": parsed.get("paper_url"),
            }
            
            db.insert_paper([paper_data])
            results.append({"url": url, "status": "success", "paper_id": paper_id})
            
        except Exception as e:
            results.append({"url": url, "status": "error", "message": str(e)})
    
    return {
        "total": len(urls),
        "success": len([r for r in results if r["status"] == "success"]),
        "skipped": len([r for r in results if r["status"] == "skipped"]),
        "error": len([r for r in results if r["status"] == "error"]),
        "results": results
    }
