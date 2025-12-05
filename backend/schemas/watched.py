from pydantic import BaseModel
from typing import Optional, List


class WatchedItemBase(BaseModel):
    name: str
    match_rule: str


class WatchedItemCreate(WatchedItemBase):
    pass


class WatchedItemUpdate(BaseModel):
    name: Optional[str] = None
    match_rule: Optional[str] = None


class WatchedItem(WatchedItemBase):
    id: int

    class Config:
        from_attributes = True


class WatchedCompany(WatchedItem):
    pass


class WatchedUniversity(WatchedItem):
    pass


class WatchedAuthor(WatchedItem):
    pass
