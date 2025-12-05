from fastapi import APIRouter, HTTPException, Depends
from typing import List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database import Database
from backend.schemas import WatchedItem, WatchedItemCreate, WatchedItemUpdate

router = APIRouter(tags=["watched"])


def get_db():
    db_path = Path(__file__).parent.parent.parent / "data" / "database.db"
    return Database(str(db_path))


# ==================== 关注公司 ====================

@router.get("/watched/companies", response_model=List[WatchedItem])
async def list_watched_companies(db: Database = Depends(get_db)):
    """获取所有关注公司"""
    return db.get_all_watched_companies()


@router.post("/watched/companies", response_model=WatchedItem)
async def create_watched_company(item: WatchedItemCreate, db: Database = Depends(get_db)):
    """添加关注公司"""
    item_id = db.add_watched_company(item.name, item.match_rule)
    return WatchedItem(id=item_id, name=item.name, match_rule=item.match_rule)


@router.put("/watched/companies/{item_id}")
async def update_watched_company(
    item_id: int,
    item: WatchedItemUpdate,
    db: Database = Depends(get_db)
):
    """更新关注公司"""
    db.update_watched_company(item_id, name=item.name, match_rule=item.match_rule)
    return {"message": "Updated successfully"}


@router.delete("/watched/companies/{item_id}")
async def delete_watched_company(item_id: int, db: Database = Depends(get_db)):
    """删除关注公司"""
    db.delete_watched_company(item_id)
    return {"message": "Deleted successfully"}


# ==================== 关注高校 ====================

@router.get("/watched/universities", response_model=List[WatchedItem])
async def list_watched_universities(db: Database = Depends(get_db)):
    """获取所有关注高校"""
    return db.get_all_watched_universities()


@router.post("/watched/universities", response_model=WatchedItem)
async def create_watched_university(item: WatchedItemCreate, db: Database = Depends(get_db)):
    """添加关注高校"""
    item_id = db.add_watched_university(item.name, item.match_rule)
    return WatchedItem(id=item_id, name=item.name, match_rule=item.match_rule)


@router.put("/watched/universities/{item_id}")
async def update_watched_university(
    item_id: int,
    item: WatchedItemUpdate,
    db: Database = Depends(get_db)
):
    """更新关注高校"""
    db.update_watched_university(item_id, name=item.name, match_rule=item.match_rule)
    return {"message": "Updated successfully"}


@router.delete("/watched/universities/{item_id}")
async def delete_watched_university(item_id: int, db: Database = Depends(get_db)):
    """删除关注高校"""
    db.delete_watched_university(item_id)
    return {"message": "Deleted successfully"}


# ==================== 关注作者 ====================

@router.get("/watched/authors", response_model=List[WatchedItem])
async def list_watched_authors(db: Database = Depends(get_db)):
    """获取所有关注作者"""
    return db.get_all_watched_authors()


@router.post("/watched/authors", response_model=WatchedItem)
async def create_watched_author(item: WatchedItemCreate, db: Database = Depends(get_db)):
    """添加关注作者"""
    item_id = db.add_watched_author(item.name, item.match_rule)
    return WatchedItem(id=item_id, name=item.name, match_rule=item.match_rule)


@router.put("/watched/authors/{item_id}")
async def update_watched_author(
    item_id: int,
    item: WatchedItemUpdate,
    db: Database = Depends(get_db)
):
    """更新关注作者"""
    db.update_watched_author(item_id, name=item.name, match_rule=item.match_rule)
    return {"message": "Updated successfully"}


@router.delete("/watched/authors/{item_id}")
async def delete_watched_author(item_id: int, db: Database = Depends(get_db)):
    """删除关注作者"""
    db.delete_watched_author(item_id)
    return {"message": "Deleted successfully"}
