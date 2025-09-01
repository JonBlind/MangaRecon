from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Annotated
from datetime import date
import uuid

# Get the genre
# Response
class GenreRead(BaseModel):
    genre_id: int
    genre_name: str
    model_config = ConfigDict(from_attributes=True)

# Get the tag
# Response
class TagRead(BaseModel):
    tag_id: int
    tag_name: str
    model_config = ConfigDict(from_attributes=True)

# Get the demographic label
class DemographicRead(BaseModel):
    demographic_id: int
    demographic_name: str
    model_config = ConfigDict(from_attributes=True)

# Get all the info on a manga
# Response
class MangaRead(BaseModel):
    manga_id: int
    title: str
    description: Optional[str] = None
    published_date: Optional[date] = None
    external_average_rating: Optional[float] = None
    average_rating: Optional[float] = None

    author_id: int
    genres: List[GenreRead] = []
    tags: List[TagRead] = []
    demographics: List[DemographicRead] = []
    model_config = ConfigDict(from_attributes=True)

# Get very minimal info for listing manga
# Response
class MangaListItem(BaseModel):
    manga_id: int
    title: str
    average_rating: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)