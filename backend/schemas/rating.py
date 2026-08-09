from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

# Request
class RatingCreate(BaseModel):
    '''
    Create or update the caller's personal rating for a manga.
    Integer scores from 1-10 map to half-star choices from 0.5-5 stars.
    An unrated manga has no rating row rather than a score of zero.
    '''
    manga_id: int
    personal_rating: int = Field(
        ge=1,
        le=10,
        description="Integer score from 1 to 10, representing 0.5 to 5 stars",
    )

# Response
class RatingRead(BaseModel):
    '''
    API representation of a stored personal rating, with the timestamp of creation.
    '''
    manga_id: int
    personal_rating: float
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
