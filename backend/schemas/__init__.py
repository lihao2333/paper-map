from .paper import (
    Paper,
    PaperCreate,
    PaperUpdate,
    PaperListResponse,
    PaperMatrixItem,
    CompanyMatrixResponse,
    UniversityMatrixResponse,
    AuthorMatrixResponse,
)
from .tag import (
    Tag,
    TagCreate,
    TagUpdate,
    TagTreeNode,
    TagMatrixResponse,
    PaperTagRequest,
)
from .watched import (
    WatchedItem,
    WatchedItemCreate,
    WatchedItemUpdate,
    WatchedCompany,
    WatchedUniversity,
    WatchedAuthor,
)
