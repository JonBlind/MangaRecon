from pydantic import BaseModel, Field, ConfigDict
from typing import Annotated
from decimal import Decimal
from datetime import datetime

# Request
class RatingCreate(BaseModel):
    '''
    Create or update the caller’s personal rating for a manga.
    The rating value is bounded (e.g., 0.0–10.0 in 0.5 increments).
    '''
    manga_id: int
    personal_rating: Annotated[Decimal, Field(ge=0.0, le=10.0, multiple_of=0.5, description="Rating from 0.0 to 10.0 in increments of 0.5")]

# Response
class RatingRead(BaseModel):
    '''
    API representation of a stored personal rating, with the timestamp of creation.
    '''
    manga_id: int
    personal_rating: float
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)