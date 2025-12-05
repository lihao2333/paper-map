"""认证相关：修改操作需验证口令"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])


class VerifyRequest(BaseModel):
    password: str


class VerifyResponse(BaseModel):
    valid: bool


@router.post("/verify", response_model=VerifyResponse)
async def verify_password(req: VerifyRequest):
    """验证修改操作口令，正确后前端可携带该口令发起修改请求"""
    import os
    expected = os.environ.get("PAPER_MAP_PASSWORD", "").strip()
    if not expected:
        return VerifyResponse(valid=True)  # 未配置口令时不校验
    return VerifyResponse(valid=(req.password.strip() == expected))
