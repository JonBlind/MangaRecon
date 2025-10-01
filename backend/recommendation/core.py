'''
Core recommendation utilities.
Builds a collection metadata profile, retrieves candidate manga, and
scores candidates against the profile to produce ranked results.
'''

import uuid
from sqlalchemy import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from backend.db.models.collection import Collection
from backend.db.models.manga_collection import MangaCollection
from backend.db.models.join_tables import manga_genre, manga_tag, manga_demographic, manga_author
from backend.db.models.manga import Manga
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)

async def get_manga_ids_in_user_collection(user_id: uuid.UUID, collection_id: int, session: AsyncSession) -> List[int]:
    '''
    Return all manga IDs contained in a user's collection after verifying ownership.

    Args:
        user_id (uuid.UUID): Identifier of the current user.
        collection_id (int): Target collection identifier.
        session (AsyncSession): SQLAlchemy async session bound to the user/manga domain.

    Returns:
        list: A list of unique manga IDs in the collection. If the collection is not found or not owned, returns an empty list.
    '''
    try:
        # Confirm ownership
        ownership_stmt = select(Collection).where(
            Collection.collection_id == collection_id,
            Collection.user_id == user_id
        )
        ownership_result = await session.execute(ownership_stmt)
        if ownership_result.scalar_one_or_none() is None:
            logger.warning(f"User {user_id} tried to access unauthorized or non-existent collection {collection_id}")
            return []

        # Get manga in that collection
        stmt = select(MangaCollection.manga_id).where(MangaCollection.collection_id == collection_id)
        result = await session.execute(stmt)
        return list({row[0] for row in result.fetchall()})  # deduplicated
    except SQLAlchemyError as e:
        logger.error(f"Error fetching manga from collection {collection_id}: {e}", exc_info=True)
        return []
    
async def get_metadata_profile_for_collection(
    manga_ids: List[int], session: AsyncSession
) -> Dict[str, any]:
    '''
    Build a metadata profile for the provided collection (frequency counts, authors, ratings, years).

    Args:
        manga_ids (List[int]): IDs of manga used to build the collection.
        session (AsyncSession): SQLAlchemy async session bound to the manga domain.

    Returns:
        dict: A dictionary with genre/tag/demographic frequency maps, an author set, and aggregates like external ratings and years.
    '''
    try:
        profile = {
            "genres": Counter(),
            "tags": Counter(),
            "demographics": Counter(),
            "authors": set(),
            "external_ratings": [],
            "years": []
        }

        # Genres
        genre_stmt = select(manga_genre.c.genre_id).where(manga_genre.c.manga_id.in_(manga_ids))
        genre_result = await session.execute(genre_stmt)
        profile["genres"].update([row[0] for row in genre_result.fetchall()])

        # Tags
        tag_stmt = select(manga_tag.c.tag_id).where(manga_tag.c.manga_id.in_(manga_ids))
        tag_result = await session.execute(tag_stmt)
        profile["tags"].update([row[0] for row in tag_result.fetchall()])

        # Demographics
        demo_stmt = select(manga_demographic.c.demographic_id).where(manga_demographic.c.manga_id.in_(manga_ids))
        demo_result = await session.execute(demo_stmt)
        profile["demographics"].update([row[0] for row in demo_result.fetchall()])

        # Authors
        author_stmt = select(manga_author.c.author_id).where(manga_author.c.manga_id.in_(manga_ids))
        author_result = await session.execute(author_stmt)
        profile["authors"].update([row[0] for row in author_result.fetchall()])

        # External ratings
        rating_stmt = select(Manga.external_average_rating).where(Manga.manga_id.in_(manga_ids))
        rating_result = await session.execute(rating_stmt)
        profile["external_ratings"].extend([row[0] for row in rating_result.fetchall() if row[0] is not None])

        # Years
        year_stmt = select(Manga.published_date).where(Manga.manga_id.in_(manga_ids))
        years_result = await session.execute(year_stmt)
        profile["years"].extend([row[0].year for row in years_result.fetchall() if row[0] is not None])

        return profile

    except SQLAlchemyError as e:
        logger.error("Failed to build metadata profile for collection", exc_info=True)
        return {
            "genres": Counter(),
            "tags": Counter(),
            "demographics": Counter(),
            "authors": set(),
            "external_ratings": []
        }
    

async def get_candidate_manga(
    excluded_ids: List[int],
    genre_ids: List[int],
    tag_ids: List[int],
    demo_ids: List[int],
    session: AsyncSession,
    max_candidates: int = 2000  # soft cap for candidates
) -> List[Manga]:
    '''
    Fetch candidate manga not in the seed set and return them with lightweight metadata needed for scoring.

    Args:
        excluded_ids (List[int]): Seed manga IDs to exclude from candidates.
        session (AsyncSession): SQLAlchemy async session bound to the manga domain.
        max_candidates (int): Soft cap on number of candidates fetched for scoring.

    Returns:
        list: A list of candidate manga rows/objects for scoring.
    '''
    try:
        stmt = (
            select(distinct(Manga))
            .join(manga_genre, Manga.manga_id == manga_genre.c.manga_id, isouter=True)
            .join(manga_tag, Manga.manga_id == manga_tag.c.manga_id, isouter=True)
            .join(manga_demographic, Manga.manga_id == manga_demographic.c.manga_id, isouter=True)
            .where(
                Manga.manga_id.notin_(excluded_ids),
                (
                    (manga_genre.c.genre_id.in_(genre_ids)) |
                    (manga_tag.c.tag_id.in_(tag_ids)) |
                    (manga_demographic.c.demographic_id.in_(demo_ids))
                ),
                Manga.external_average_rating.is_not(None)
            )
            .limit(max_candidates)
        )

        result = await session.execute(stmt)
        candidates = result.scalars().all()
        logger.info(f"Generated {len(candidates)} candidate manga to score")
        return candidates

    except Exception as e:
        logger.error(f"Error generating candidate manga: {e}", exc_info=True)
        return []
    
async def get_scored_recommendations(
    candidates: List[Manga],
    metadata_profile: Dict[str, Any],
    session: AsyncSession
) -> List[Dict[str, Any]]:
    '''
    Score candidate manga against the collection's metadata profile and return a ranked list.

    Args:
        candidates (List[Manga]): Candidate manga rows/objects to score.
        metadata_profile (dict): Profile including frequency maps and aggregates used as scoring features.

    Returns:
        list: Ranked recommendations with a final score and a breakdown of contributing feature scores.
    '''
    if not candidates:
        return []

    # Extract all the manga_ids for candidates
    candidate_ids = [manga.manga_id for manga in candidates]

    meta = {
        "genres": defaultdict(set),
        "tags": defaultdict(set),
        "demographics": defaultdict(set),
        "authors": defaultdict(set)
    }

    genre_stmt = select(manga_genre.c.manga_id, manga_genre.c.genre_id).where(manga_genre.c.manga_id.in_(candidate_ids))
    tag_stmt = select(manga_tag.c.manga_id, manga_tag.c.tag_id).where(manga_tag.c.manga_id.in_(candidate_ids))
    demo_stmt = select(manga_demographic.c.manga_id, manga_demographic.c.demographic_id).where(manga_demographic.c.manga_id.in_(candidate_ids))
    author_stmt = select(manga_author.c.manga_id, manga_author.c.author_id).where(manga_author.c.manga_id.in_(candidate_ids))

    for stmt, key in [(genre_stmt, "genres"), (tag_stmt, "tags"), (demo_stmt, "demographics"), (author_stmt, "authors")]:
        result = await session.execute(stmt)
        for manga_id, item_id in result.fetchall():
            meta[key][manga_id].add(item_id)

    # Get avg rating of all works.
    if metadata_profile["external_ratings"]:
        avg_rating = sum(metadata_profile["external_ratings"]) / len(metadata_profile["external_ratings"])
    else:
        avg_rating = None

    # Get avg year of release for all works
    if metadata_profile["years"]:
        avg_year = round(sum(metadata_profile["years"]) / len(metadata_profile["years"]))
    else:
        avg_year = None
    
    scored = []
    for manga in candidates:
        manga_id = manga.manga_id
        score = 0.0

        # For each match:
        # + (# genres * 2)
        # + (# tags * 3)
        # + (# demographics * 1.25)
        # + 3 author match
        # - 0.5 per year off average year of release
        genre_score = sum(metadata_profile["genres"].get(g, 0) for g in meta["genres"].get(manga_id, [])) * 2
        tag_score = sum(metadata_profile["tags"].get(t, 0) for t in meta["tags"].get(manga_id, [])) * 3
        demo_score = sum(metadata_profile["demographics"].get(d, 0) for d in meta["demographics"].get(manga_id, [])) * 1.25
        author_score = 3 if metadata_profile["authors"] & meta["authors"].get(manga_id, set()) else 0
        rating_score = max(0, 5 - abs(manga.external_average_rating - avg_rating)) if manga.external_average_rating and avg_rating else 0

        year_score = 0
        if manga.published_date and avg_year:
            year_score = max(0, 5 - (abs(manga.published_date.year - avg_year) * 0.5))

        score = genre_score + tag_score + demo_score + author_score + rating_score + year_score

        scored.append({
            "manga_id": manga.manga_id,
            "title": manga.title,
            "external_average_rating": manga.external_average_rating,
            "cover_image_url": manga.cover_image_url,
            "score": round(score, 2),
            "details": {
                "genre_score": genre_score,
                "tag_score": tag_score,
                "demo_score": demo_score,
                "author_score":author_score,
                "rating_score": rating_score,
                "year_score": year_score
            }
        })

    # sorted by score from largest --> smallest
    return sorted(scored, key=lambda x: x["score"], reverse=True)