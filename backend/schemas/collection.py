from pydantic import BaseModel, StringConstraints, ConfigDict, field_validator, Field
from typing import Optional, Annotated, Literal
from datetime import datetime

# Request
class CollectionCreate(BaseModel):
    '''
    Payload to create a new collection for a user.
    '''
    collection_name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    description: Optional[Annotated[str, StringConstraints(max_length=255)]] = None

    # enforce that a collection_name cant be whitespace.
    @field_validator("collection_name")
    def collection_name_not_whitespace(v: str) -> str:
        if v.strip() == "":
            raise ValueError("collection_name cannot be empty/whitespace")
        
        return v
    
# Request
class CollectionUpdate(BaseModel):
    '''
    Payload to update a user-owned collection.
    '''
    collection_name: Optional[Annotated[str, StringConstraints(min_length=1, max_length=255)]] = None
    description: Optional[Annotated[str, StringConstraints(max_length=255)]] = None

    # enforce that a collection_name cant be whitespace.
    @field_validator("collection_name")
    def collection_name_not_whitespace_if_present(cls, v: str | None) -> str | None:
        if v is not None and v.strip() == "":
            raise ValueError("collection_name cannot be empty/whitespace")
        return v

# Response
class CollectionRead(BaseModel):
    '''
    Update for a collection, all fields optional.
    '''
    collection_id: int
    collection_name: str
    description: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MangaInCollectionRequest(BaseModel):
    '''
    API representation of a collection returned from the server.
    '''
    manga_id: int

class BulkMangaInCollectionRequest(BaseModel):
    manga_ids: list[int] = Field(min_length=1, max_length=100)


class BulkMangaAddFailure(BaseModel):
    manga_id: int
    reason: Literal["ALREADY_EXISTS", "COLLECTION_NOT_FOUND", "UNKNOWN"]


class BulkMangaInCollectionResponse(BaseModel):
    collection_id: int
    added_count: int
    failed_count: int
    added_ids: list[int]
    failed: list[BulkMangaAddFailure]