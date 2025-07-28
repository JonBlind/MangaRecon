from pydantic import BaseModel, constr
from typing import Optional, Annotated
from datetime import datetime

# Request
class CollectionCreate(BaseModel):
    collection_name: Annotated[str, constr(min_length=1, max_length=255)]
    description: Optional[Annotated[str, constr(min_length=1, max_length=255)]] = None
    
# Request
class CollectionUpdate(BaseModel):
    collection_name: Optional[Annotated[str, constr(min_length=1, max_length=255)]] = None
    description: Optional[Annotated[str, constr(min_length=1, max_length=255)]] = None

# Response
class CollectionRead(BaseModel):
    collection_id: int
    user_id: str # UUIDs are strings
    collection_name: str
    description: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class MangaInCollectionRequest(BaseModel):
    manga_id: int