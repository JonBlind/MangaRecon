from pydantic import BaseModel, Field, condecimal
from typing import Annotated
from decimal import Decimal

class RateMangaRequest(BaseModel):
    user_id: int
    manga_id: int
    score: Annotated[Decimal, Field(ge=0.0, le=10.0, multiple_of=0.5, description="Rating from 0.0 to 10.0 in increments of 0.5")]