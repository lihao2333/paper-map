from pydantic import BaseModel, Field
from typing import Optional, List


class PaperBase(BaseModel):
    paper_url: str
    arxiv_id: Optional[str] = None
    date: Optional[str] = None
    alias: Optional[str] = None
    full_name: Optional[str] = None
    abstract: Optional[str] = None
    summary: Optional[str] = None
    github_url: Optional[str] = None
    arxiv_comments: Optional[str] = None
    is_comment_used: bool = False


class PaperCreate(PaperBase):
    paper_id: Optional[str] = None


class PaperUpdate(BaseModel):
    paper_id: str
    arxiv_id: Optional[str] = None
    date: Optional[str] = None
    alias: Optional[str] = None
    full_name: Optional[str] = None
    abstract: Optional[str] = None
    summary: Optional[str] = None
    arxiv_comments: Optional[str] = None
    is_comment_used: Optional[bool] = None
    company_names: Optional[List[str]] = None
    university_names: Optional[List[str]] = None
    author_names: Optional[List[str]] = None
    github_url: Optional[str] = None


class Paper(PaperBase):
    paper_id: str
    company_names: List[str] = []
    university_names: List[str] = []
    author_names: List[str] = []
    tags: List[str] = []

    class Config:
        from_attributes = True


class PaperListResponse(BaseModel):
    items: List[Paper]
    total: int
    page: int
    page_size: int


class PaperMatrixItem(BaseModel):
    paper_id: str
    arxiv_id: Optional[str] = None
    paper_url: str
    alias: str
    full_name: str
    summary: str
    date: str


class CompanyMatrixResponse(BaseModel):
    companies: List[str]
    papers: List[dict]


class UniversityMatrixResponse(BaseModel):
    universities: List[str]
    papers: List[dict]


class AuthorMatrixResponse(BaseModel):
    authors: List[str]
    papers: List[dict]
