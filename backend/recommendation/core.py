'''
Core recommendation utilities.
Builds a collection metadata profile, retrieves candidate manga, and
scores candidates against the profile to produce ranked results.
'''

import uuid
from sqlalchemy import or_, select
from backend.db.client_db import ClientReadDatabase
from sqlalchemy.exc import SQLAlchemyError
from backend.db.models.collection import Collection
from backend.db.models.manga_collection import MangaCollection
from backend.db.models.join_tables import manga_genre, manga_tag, manga_demographic
from backend.db.models.manga_creator import MangaCreator
from backend.db.models.manga import Manga
from collections import Counter, defaultdict
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

async def get_manga_ids_in_user_collection(user_id: uuid.UUID, collection_id: int, db: ClientReadDatabase) -> List[int]:
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
        ownership_result = await db.execute(ownership_stmt)
        if ownership_result.scalar_one_or_none() is None:
            logger.warning(f"User {user_id} tried to access unauthorized or non-existent collection {collection_id}")
            return []

        # Get manga in that collection
        stmt = select(MangaCollection.manga_id).where(MangaCollection.collection_id == collection_id)
        result = await db.execute(stmt)
        return list({row[0] for row in result.fetchall()})  # deduplicated
    except SQLAlchemyError as e:
        logger.error(f"Error fetching manga from collection {collection_id}: {e}", exc_info=True)
        return []


async def get_manga_ids_in_user_collections(
    user_id: uuid.UUID,
    db: ClientReadDatabase,
) -> List[int]:
    """Return every distinct manga ID saved in any collection owned by a user."""
    try:
        stmt = (
            select(MangaCollection.manga_id)
            .join(
                Collection,
                Collection.collection_id == MangaCollection.collection_id,
            )
            .where(Collection.user_id == user_id)
            .distinct()
        )
        result = await db.execute(stmt)
        return list(dict.fromkeys(row[0] for row in result.fetchall()))
    except SQLAlchemyError as exc:
        logger.error(
            "Error fetching manga across collections for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return []
    
async def get_metadata_profile_for_collection(manga_ids: List[int], db: ClientReadDatabase) -> Dict[str, any]:
    '''
    Build a metadata profile for the provided collection (frequency counts, creators, ratings, years).

    Args:
        manga_ids (List[int]): IDs of manga used to build the collection.
        session (AsyncSession): SQLAlchemy async session bound to the manga domain.

    Returns:
        dict: A dictionary with genre/tag/demographic frequency maps, a creator set, and aggregates like external ratings and years.
    '''
    try:
        profile = {
            "genres": Counter(),
            "tags": Counter(),
            "demographics": Counter(),
            "creators": set(),
            "external_ratings": [],
            "years": []
        }

        # Genres
        genre_stmt = select(manga_genre.c.genre_id).where(manga_genre.c.manga_id.in_(manga_ids))
        genre_result = await db.execute(genre_stmt)
        profile["genres"].update([row[0] for row in genre_result.fetchall()])

        # Tags
        tag_stmt = select(manga_tag.c.tag_id).where(manga_tag.c.manga_id.in_(manga_ids))
        tag_result = await db.execute(tag_stmt)
        profile["tags"].update([row[0] for row in tag_result.fetchall()])

        # Demographics
        demo_stmt = select(manga_demographic.c.demographic_id).where(manga_demographic.c.manga_id.in_(manga_ids))
        demo_result = await db.execute(demo_stmt)
        profile["demographics"].update([row[0] for row in demo_result.fetchall()])

        # Creators
        creator_stmt = select(MangaCreator.creator_id).where(MangaCreator.manga_id.in_(manga_ids))
        creator_result = await db.execute(creator_stmt)
        profile["creators"].update(row[0] for row in creator_result.fetchall())

        # External ratings
        rating_stmt = select(Manga.external_average_rating).where(Manga.manga_id.in_(manga_ids))
        rating_result = await db.execute(rating_stmt)
        profile["external_ratings"].extend([row[0] for row in rating_result.fetchall() if row[0] is not None])

        # Years
        year_stmt = select(Manga.publication_year).where(Manga.manga_id.in_(manga_ids))
        years_result = await db.execute(year_stmt)
        profile["years"].extend(row[0]for row in years_result.fetchall() if row[0] is not None)

        return profile

    except SQLAlchemyError as e:
        logger.error("Failed to build metadata profile for collection", exc_info=True)
        return {
            "genres": Counter(),
            "tags": Counter(),
            "demographics": Counter(),
            "creators": set(),
            "external_ratings": [],
            "years": []
        }
    

async def get_candidate_manga(
    excluded_ids: List[int],
    genre_ids: List[int],
    tag_ids: List[int],
    demo_ids: List[int],
    creator_ids: List[int],
    db: ClientReadDatabase,
    max_candidates: int = 2000,
) -> List[Dict[str, Any]]:
    """
    Fetch candidate manga that share at least one relevant metadata value with
    the seed manga.

    Creator identity participates in candidate discovery regardless of the
    creator's role on either manga.
    """
    try:
        similarity_conditions = []

        if genre_ids:
            similarity_conditions.append(
                Manga.manga_id.in_(
                    select(manga_genre.c.manga_id).where(
                        manga_genre.c.genre_id.in_(genre_ids)
                    )
                )
            )

        if tag_ids:
            similarity_conditions.append(
                Manga.manga_id.in_(
                    select(manga_tag.c.manga_id).where(
                        manga_tag.c.tag_id.in_(tag_ids)
                    )
                )
            )

        if demo_ids:
            similarity_conditions.append(
                Manga.manga_id.in_(
                    select(manga_demographic.c.manga_id).where(
                        manga_demographic.c.demographic_id.in_(demo_ids)
                    )
                )
            )

        if creator_ids:
            similarity_conditions.append(
                Manga.manga_id.in_(
                    select(MangaCreator.manga_id).where(
                        MangaCreator.creator_id.in_(creator_ids)
                    )
                )
            )

        if not similarity_conditions:
            return []

        stmt = (
            select(
                Manga.manga_id,
                Manga.title,
                Manga.description,
                Manga.publication_year,
                Manga.external_average_rating,
                Manga.average_rating,
                Manga.cover_image_url,
            )
            .where(
                Manga.manga_id.notin_(excluded_ids),
                or_(*similarity_conditions),
                Manga.external_average_rating.is_not(None),
            )
            .distinct()
            .limit(max_candidates)
        )

        result = await db.execute(stmt)
        candidates = [
            dict(row)
            for row in result.mappings().all()
        ]

        logger.info(
            "Generated %s candidate manga to score",
            len(candidates),
        )
        return candidates

    except Exception as exc:
        logger.error(
            "Error generating candidate manga: %s",
            exc,
            exc_info=True,
        )
        return []
    
async def get_scored_recommendations(
    candidates: List[Dict[str, Any]],
    metadata_profile: Dict[str, Any],
    db: ClientReadDatabase
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
    candidate_ids = [manga["manga_id"] for manga in candidates]

    meta = {
        "genres": defaultdict(set),
        "tags": defaultdict(set),
        "demographics": defaultdict(set),
        "creators": defaultdict(set)
    }

    genre_stmt = select(manga_genre.c.manga_id, manga_genre.c.genre_id).where(manga_genre.c.manga_id.in_(candidate_ids))
    tag_stmt = select(manga_tag.c.manga_id, manga_tag.c.tag_id).where(manga_tag.c.manga_id.in_(candidate_ids))
    demo_stmt = select(manga_demographic.c.manga_id, manga_demographic.c.demographic_id).where(manga_demographic.c.manga_id.in_(candidate_ids))
    creator_stmt = select(MangaCreator.manga_id, MangaCreator.creator_id,).where(MangaCreator.manga_id.in_(candidate_ids))

    metadata_queries = [
        (genre_stmt, "genres"),
        (tag_stmt, "tags"),
        (demo_stmt, "demographics"),
        (creator_stmt, "creators"),
    ]

    for stmt, key in metadata_queries:
        result = await db.execute(stmt)

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
        manga_id = manga["manga_id"]
        score = 0.0

        # For each match:
        # + (# genres * 2)
        # + (# tags * 3)
        # + (# demographics * 1.25)
        # + 3 creator match
        # - 0.5 per year off average year of release
        genre_score = sum(metadata_profile["genres"].get(g, 0) for g in meta["genres"].get(manga_id, [])) * 2
        tag_score = sum(metadata_profile["tags"].get(t, 0) for t in meta["tags"].get(manga_id, [])) * 3
        demo_score = sum(metadata_profile["demographics"].get(d, 0) for d in meta["demographics"].get(manga_id, [])) * 1.25
        creator_score = (3 if metadata_profile["creators"] & meta["creators"].get(manga_id, set())else 0)
        rating_score = max(0, 5 - abs(float(manga["external_average_rating"] - avg_rating)) if manga["external_average_rating"] and avg_rating else 0)

        year_score = 0
        if manga["publication_year"] is not None and avg_year is not None:
            year_score = max(0, 5 - (abs(manga["publication_year"] - avg_year) * 0.5))

        score = genre_score + tag_score + demo_score + creator_score + rating_score + year_score

        scored.append({
            "manga_id": manga["manga_id"],
            "title": manga["title"],
            "external_average_rating": manga["external_average_rating"],
            "cover_image_url": manga["cover_image_url"],
            "score": round(score, 2),
            "details": {
                "genre_score": genre_score,
                "tag_score": tag_score,
                "demo_score": demo_score,
                "creator_score":creator_score,
                "rating_score": rating_score,
                "year_score": year_score
            }
        })

    # sorted by score from largest --> smallest
    return sorted(scored, key=lambda x: x["score"], reverse=True)
