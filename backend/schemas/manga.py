from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Annotated
from datetime import date
import uuid

# Get the genre
# Response
class GenreRead(BaseModel):
    '''
    Genre master record used for categorizing manga (e.g., Action, Romance).
    '''
    genre_id: int
    genre_name: str
    model_config = ConfigDict(from_attributes=True)

# Get the tag
# Response
class TagRead(BaseModel):
    '''
    Tag master record for more specific classification (e.g., Time Travel, Found Family).
    '''
    tag_id: int
    tag_name: str
    model_config = ConfigDict(from_attributes=True)

# Get the demographic label
class DemographicRead(BaseModel):
    '''
    Demographic label for the intended audience (e.g., Shonen, Seinen, Josei).
    '''
    demographic_id: int
    demographic_name: str
    model_config = ConfigDict(from_attributes=True)

# Get all the info on a manga
# Response
class MangaRead(BaseModel):
    '''
    Full API representation of a manga, including core fields and attached metadata
    (author, genres, tags, demographics). Ratings may include external and aggregate values.
    '''
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
    '''
    Lightweight representation for listing/search results and recommendations.
    Includes identifier, title, and optional average rating.
    '''
    manga_id: int
    title: str
    average_rating: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)