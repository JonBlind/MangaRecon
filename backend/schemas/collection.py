from pydantic import BaseModel, StringConstraints, ConfigDict
from typing import Optional, Annotated
from datetime import datetime

# Request
class CollectionCreate(BaseModel):
    collection_name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    description: Optional[Annotated[str, StringConstraints(min_length=1, max_length=255)]] = None
    
# Request
class CollectionUpdate(BaseModel):
    collection_name: Optional[Annotated[str, StringConstraints(min_length=1, max_length=255)]] = None
    description: Optional[Annotated[str, StringConstraints(min_length=1, max_length=255)]] = None

# Response
class CollectionRead(BaseModel):
    collection_id: int
    user_id: str # UUIDs are strings
    collection_name: str
    description: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MangaInCollectionRequest(BaseModel):
    manga_id: int