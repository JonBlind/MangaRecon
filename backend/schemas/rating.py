from pydantic import BaseModel, Field, condecimal
from typing import Annotated
from decimal import Decimal
import datetime

# Request
class RatingCreate(BaseModel):
    manga_id: int
    personal_rating: Annotated[Decimal, Field(ge=0.0, le=10.0, multiple_of=0.5, description="Rating from 0.0 to 10.0 in increments of 0.5")]

# Response
class RatingRead(BaseModel):
    manga_id: int
    personal_rating: float
    created_at: datetime

    class Config:
        orm_mode = True
        