#!/usr/bin/env python3
"""
PaperMap FastAPI 后端
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.routers import (
    auth_router,
    papers_router,
    matrix_router,
    tags_router,
    watched_router,
    collect_router,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from database import Database
    db_path = Path(__file__).parent.parent / "data" / "database.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    Database(str(db_path)).construct()
    yield


app = FastAPI(
    title="PaperMap API",
    description="论文管理系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 修改操作口令保护（口令存于环境变量 PAPER_MAP_PASSWORD，不泄露于代码）
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_REQUIRED_PASSWORD = os.environ.get("PAPER_MAP_PASSWORD", "").strip()

class RequirePasswordMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _REQUIRED_PASSWORD:
            return await call_next(request)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        path = request.url.path
        if path == "/api/auth/verify" or path.rstrip("/") == "/api/auth/verify":
            return await call_next(request)
        if path.startswith("/api/"):
            pwd = request.headers.get("X-Paper-Map-Password", "")
            if pwd != _REQUIRED_PASSWORD:
                return JSONResponse(status_code=403, content={"detail": "需要正确的修改口令"})
        return await call_next(request)

app.add_middleware(RequirePasswordMiddleware)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router, prefix="/api")
app.include_router(papers_router, prefix="/api")
app.include_router(matrix_router, prefix="/api")
app.include_router(tags_router, prefix="/api")
app.include_router(watched_router, prefix="/api")
app.include_router(collect_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "PaperMap API", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    from database import Database
    
    db_path = Path(__file__).parent.parent / "data" / "database.db"
    db = Database(str(db_path))
    
    papers = db.get_all_papers_with_details()
    tags = db.get_all_tags()
    watched_companies = db.get_all_watched_companies()
    watched_universities = db.get_all_watched_universities()
    watched_authors = db.get_all_watched_authors()
    
    return {
        "total_papers": len(papers),
        "total_tags": len(tags),
        "watched_companies": len(set(c["name"] for c in watched_companies)),
        "watched_universities": len(set(u["name"] for u in watched_universities)),
        "watched_authors": len(set(a["name"] for a in watched_authors)),
    }


if __name__ == "__main__":
    import uvicorn
    # 使用导入字符串才能启用 reload 热重载
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
