from pydantic import BaseModel
from typing import Optional, List


class TagBase(BaseModel):
    tag_name: str


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    tag_name: str


class Tag(TagBase):
    tag_id: int
    paper_count: Optional[int] = 0

    class Config:
        from_attributes = True


class TagTreeNode(BaseModel):
    tag_id: Optional[int] = None
    tag_name: str
    full_path: str
    children: List["TagTreeNode"] = []
    paper_count: int = 0


class TagMatrixResponse(BaseModel):
    tags: List[str]
    papers: List[dict]


class PaperTagRequest(BaseModel):
    paper_id: str
    tag_name: str
