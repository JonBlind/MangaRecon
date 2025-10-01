from pydantic import BaseModel, StringConstraints, ConfigDict
from typing import Optional, Annotated
from datetime import datetime

# Request
class CollectionCreate(BaseModel):
    '''
    Payload to create a new collection for a user.
    '''
    collection_name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    description: Optional[Annotated[str, StringConstraints(min_length=1, max_length=255)]] = None
    
# Request
class CollectionUpdate(BaseModel):
    '''
    Payload to update a user-owned collection.
    '''
    collection_name: Optional[Annotated[str, StringConstraints(min_length=1, max_length=255)]] = None
    description: Optional[Annotated[str, StringConstraints(min_length=1, max_length=255)]] = None

# Response
class CollectionRead(BaseModel):
    '''
    Update for a collection, all fields optional.
    '''
    collection_id: int
    user_id: str # UUIDs are strings
    collection_name: str
    description: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MangaInCollectionRequest(BaseModel):
    '''
    API representation of a collection returned from the server.
    '''
    manga_id: int