# tests/db/factories.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.db.models.user import User
from backend.db.models.author import Author
from backend.db.models.manga import Manga
from backend.db.models.rating import Rating
from backend.db.models.collection import Collection
from backend.db.models.genre import Genre
from backend.db.models.tag import Tag
from backend.db.models.demographics import Demographic


def _utcnow():
    return datetime.now(timezone.utc)


DEFAULT_USER_HASHED_PASSWORD = "some-bs-hash"
DEFAULT_AUTHOR_NAME = "Test Author"
DEFAULT_MANGA_TITLE = "Test Manga"
DEFAULT_COLLECTION_NAME = "Test Collection"
DEFAULT_COLLECTION_DESCRIPTION = "A test collection"
DEFAULT_GENRE_NAME = "Test Genre"
DEFAULT_TAG_NAME = "Test Tag"
DEFAULT_DEMOGRAPHIC_NAME = "Test Demographic"


async def make_user(
    session,
    *,
    id=None,
    email=None,
    username=None,
    displayname=None,
    hashed_password=None,
    is_active=True,
    is_superuser=False,
    is_verified=True,
    last_login=None,
    **extra_fields,
) -> User:
    suffix = uuid4().hex[:8]
    user = User(
        id=id or uuid4(),
        email=email or f"test_{suffix}@fakemail.com",
        hashed_password=hashed_password or DEFAULT_USER_HASHED_PASSWORD,
        username=username or f"testuser_{suffix}",
        displayname=displayname or "Test User",
        is_active=is_active,
        is_superuser=is_superuser,
        is_verified=is_verified,
        last_login=last_login,
        **extra_fields,
    )
    session.add(user)
    await session.flush()
    return user


async def make_author(session, *, name=None, **extra_fields) -> Author:
    author = Author(
        author_name=name or DEFAULT_AUTHOR_NAME,
        **extra_fields,
    )
    session.add(author)
    await session.flush()
    return author


async def make_manga(
    session,
    *,
    author: Author | None = None,
    author_id: int | None = None,
    title=None,
    description=None,
    published_date=None,
    external_average_rating=None,
    average_rating=None,
    cover_image_url=None,
    **extra_fields,
) -> Manga:
    if author is None and author_id is None:
        author = await make_author(session)

    if title is None:
        title = f"{DEFAULT_MANGA_TITLE} {uuid4().hex[:8]}"


    manga = Manga(
        title=title,
        author_id=author_id if author_id is not None else author.author_id,
        description=description,
        published_date=published_date,
        external_average_rating=external_average_rating,
        average_rating=average_rating,
        cover_image_url=cover_image_url,
        **extra_fields,
    )
    session.add(manga)
    await session.flush()
    return manga


async def make_rating(
    session,
    *,
    user: User | None = None,
    manga: Manga | None = None,
    personal_rating: float = 7.5,
    **extra_fields,
) -> Rating:
    if user is None:
        user = await make_user(session)
    if manga is None:
        manga = await make_manga(session)

    rating = Rating(
        user_id=user.id,
        manga_id=manga.manga_id,
        personal_rating=personal_rating,
        **extra_fields,
    )
    session.add(rating)
    await session.flush()
    return rating


async def make_collection(
    session,
    *,
    user: User | None = None,
    user_id=None,
    name=None,
    description=None,
    is_public=False,
    **extra_fields,
) -> Collection:
    if user is None and user_id is None:
        user = await make_user(session)

    collection = Collection(
        collection_id=uuid4(),
        user_id=user_id if user_id is not None else user.id,
        name=name or DEFAULT_COLLECTION_NAME,
        description=description or DEFAULT_COLLECTION_DESCRIPTION,
        is_public=is_public,
        **extra_fields,
    )
    session.add(collection)
    await session.flush()
    return collection


async def make_genre(session, *, name=None, **extra_fields) -> Genre:
    genre = Genre(
        name=name or DEFAULT_GENRE_NAME,
        **extra_fields,
    )
    session.add(genre)
    await session.flush()
    return genre


async def make_tag(session, *, name=None, **extra_fields) -> Tag:
    tag = Tag(
        genre_name=name or DEFAULT_TAG_NAME,
        **extra_fields,
    )
    session.add(tag)
    await session.flush()
    return tag


async def make_demographic(session, *, name=None, **extra_fields) -> Demographic:
    demographic = Demographic(
        demographic_name=name or DEFAULT_DEMOGRAPHIC_NAME,
        **extra_fields,
    )
    session.add(demographic)
    await session.flush()
    return demographic
