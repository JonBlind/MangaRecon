from __future__ import annotations

import uuid
from typing import List

from backend.config.limits import MAX_RECOMMENDATION_SEEDS
from backend.db.client_db import ClientReadDatabase
from backend.recommendation import core
from backend.repositories.manga_repo import filter_visible_manga_ids
from backend.utils.domain_exceptions import BadRequestError


async def generate_recommendations_for_collection(
    user_id: uuid.UUID,
    collection_id: int,
    user_db: ClientReadDatabase,
    manga_db: ClientReadDatabase,
    include_adult: bool = False,
) -> dict:
    '''
    Generate recommendations for the given user's collection by composing core steps.

    Args:
        user_id (uuid.UUID): Identifier of the current user.
        collection_id (int): Target collection identifier.
        db (ClientReadDatabase): Read-only session of the ClientDatabase.

    Returns:
        dict:
            - items: list of recommendation dicts
            - seed_total: int
            - seed_used: int
            - seed_truncated: bool
    '''
    stored_collection_manga_ids = await core.get_manga_ids_in_user_collection(
        user_id,
        collection_id,
        user_db,
    )
    collection_manga_ids = await filter_visible_manga_ids(
        manga_db,
        manga_ids=stored_collection_manga_ids,
        include_adult=include_adult,
    )
    if not collection_manga_ids:
        raise BadRequestError(code="RECOMMENDATION_SEED_EMPTY", message="Need at least 1 manga in the collection to generate recommendations.", 
                          detail={"collection_id": collection_id})

    all_user_manga_ids = await core.get_manga_ids_in_user_collections(
        user_id,
        user_db,
    )
    excluded_ids = list(
        dict.fromkeys([*collection_manga_ids, *all_user_manga_ids])
    )

    seed_total = len(collection_manga_ids)
    seed_truncated = seed_total > MAX_RECOMMENDATION_SEEDS
    scoring_manga_ids = collection_manga_ids[:MAX_RECOMMENDATION_SEEDS]

    metadata_profile = await core.get_metadata_profile_for_collection(
        scoring_manga_ids,
        manga_db,
    )

    candidates = await core.get_candidate_manga(
        excluded_ids=excluded_ids,
        genre_ids=list(metadata_profile["genres"].keys()),
        tag_ids=list(metadata_profile["tags"].keys()),
        demo_ids=list(metadata_profile["demographics"].keys()),
        creator_ids=list(metadata_profile["creators"]),
        db=manga_db,
        include_adult=include_adult,
    )

    scored = await core.get_scored_recommendations(candidates, metadata_profile, manga_db)

    return {
        "items": scored,
        "seed_total": seed_total,
        "seed_used": len(scoring_manga_ids),
        "seed_truncated": seed_truncated,
    }


async def generate_recommendations_for_list(
    manga_ids: List[int],
    db: ClientReadDatabase,
    include_adult: bool = False,
) -> dict:
    '''
    Generate recommendations from a raw list of manga IDs (not persisted).

    Args:
        manga_ids(List[int]): List of manga_ids to generate recommendations for.
        db (ClientReadDatabase): Read-only session of the ClientDatabase.

    Returns:
        dict:
            - items: list of recommendation dicts
            - seed_total: int
            - seed_used: int
            - seed_truncated: bool
    '''
    if not manga_ids:
        raise BadRequestError(code="RECOMMENDATION_SEED_EMPTY", message="Please provide at least one manga to generate recommendations.")

    excluded_ids = list(manga_ids)
    visible_manga_ids = await filter_visible_manga_ids(
        db,
        manga_ids=excluded_ids,
        include_adult=include_adult,
    )

    if not visible_manga_ids:
        raise BadRequestError(
            code="RECOMMENDATION_SEED_EMPTY",
            message=(
                "Please provide at least one visible manga "
                "to generate recommendations."
            ),
        )

    seed_total = len(visible_manga_ids)
    seed_truncated = seed_total > MAX_RECOMMENDATION_SEEDS
    scoring_manga_ids = visible_manga_ids[:MAX_RECOMMENDATION_SEEDS]

    metadata_profile = await core.get_metadata_profile_for_collection(
        scoring_manga_ids,
        db,
    )

    candidates = await core.get_candidate_manga(
        excluded_ids=excluded_ids,
        genre_ids=list(metadata_profile["genres"].keys()),
        tag_ids=list(metadata_profile["tags"].keys()),
        demo_ids=list(metadata_profile["demographics"].keys()),
        creator_ids=list(metadata_profile["creators"]),
        db=db,
        include_adult=include_adult,
    )

    scored = await core.get_scored_recommendations(candidates, metadata_profile, db)

    return {
        "items": scored,
        "seed_total": seed_total,
        "seed_used": len(scoring_manga_ids),
        "seed_truncated": seed_truncated,
    }
