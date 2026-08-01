from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


CreatorRole = Literal["author", "artist"]


class GenreRead(BaseModel):
    """
    Genre master record used for categorizing manga (e.g., Action, Romance).
    """

    genre_id: int
    genre_name: str

    model_config = ConfigDict(from_attributes=True)


class TagRead(BaseModel):
    """
    Tag master record for more specific classification
    (e.g., Time Travel, Tournament).
    """

    tag_id: int
    tag_name: str

    model_config = ConfigDict(from_attributes=True)


class DemographicRead(BaseModel):
    """
    Demographic label for the intended audience
    (e.g., Shonen, Seinen, Josei).
    """

    demographic_id: int
    demographic_name: str

    model_config = ConfigDict(from_attributes=True)


class CreatorCreditRead(BaseModel):
    """
    A creator's role on a particular manga.
    """

    creator_id: int
    creator_name: str
    role: CreatorRole

    model_config = ConfigDict(from_attributes=True)


class MangaRead(BaseModel):
    """
    Full API representation of a manga, including core fields, creator
    credits, classifications, and internal and external rating metadata.
    """

    manga_id: int
    title: str
    description: Optional[str] = None
    publication_year: Optional[int] = None
    media_type: Optional[str] = None

    external_average_rating: Optional[float] = None
    external_rating_votes: Optional[int] = None
    average_rating: Optional[float] = None

    creator_credits: list[CreatorCreditRead] = Field(default_factory=list)
    genres: list[GenreRead] = Field(default_factory=list)
    tags: list[TagRead] = Field(default_factory=list)
    demographics: list[DemographicRead] = Field(default_factory=list)

    cover_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MangaListItem(BaseModel):
    """
    Lightweight manga representation used for listing and search results.
    """

    manga_id: int
    title: str
    description: Optional[str] = None
    publication_year: Optional[int] = None
    media_type: Optional[str] = None

    genres: list[GenreRead] = Field(default_factory=list)

    average_rating: Optional[float] = None
    external_average_rating: Optional[float] = None
    external_rating_votes: Optional[int] = None

    cover_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
