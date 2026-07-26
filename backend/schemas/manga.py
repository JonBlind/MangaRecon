from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal
from datetime import date

CreatorRole = Literal["author", "artist"]

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

class CreatorCreditRead(BaseModel):
    """
    A creator's role on a particular manga.
    """

    creator_id: int
    creator_name: str
    role: CreatorRole

    model_config = ConfigDict(from_attributes=True)
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

    creator_credits: list[CreatorCreditRead] = Field(default_factory=list)
    genres: list[GenreRead] = Field(default_factory=list)
    tags: list[TagRead] = Field(default_factory=list)
    demographics: list[DemographicRead] = Field(default_factory=list)
    cover_image_url: Optional[str] = None

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
    genres: list[GenreRead] = Field(default_factory=list)
    average_rating: Optional[float] = None
    cover_image_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)