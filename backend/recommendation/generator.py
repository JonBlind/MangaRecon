import uuid
from backend.recommendation import core
from typing import List, Dict, Any
from backend.db.client_db import ClientReadDatabase
from backend.config.limits import MAX_RECOMMENDATION_SEEDS

async def generate_recommendations_for_collection(
    user_id: uuid.UUID,
    collection_id: int,
    db: ClientReadDatabase
) -> List[Dict[str, Any]]:
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
    # Get all manga in collection
    manga_ids = await core.get_manga_ids_in_user_collection(user_id, collection_id, db)
    if not manga_ids:
        raise ValueError("Need at least 1 manga in the collection to generate recommendations")
    
    seed_truncated = False
    seed_total = len(manga_ids)

    if seed_total > MAX_RECOMMENDATION_SEEDS:
        manga_ids = manga_ids[:MAX_RECOMMENDATION_SEEDS]
        seed_truncated = True

    metadata_profile = await core.get_metadata_profile_for_collection(manga_ids, db)

    candidates = await core.get_candidate_manga(
        excluded_ids=manga_ids,
        genre_ids=list(metadata_profile["genres"].keys()),
        tag_ids=list(metadata_profile["tags"].keys()),
        demo_ids=list(metadata_profile["demographics"].keys()),
        db=db
    )

    scored = await core.get_scored_recommendations(candidates, metadata_profile, db)
    return {
    "items": scored,
    "seed_total": seed_total,
    "seed_used": len(manga_ids),
    "seed_truncated": seed_truncated,
    }



async def generate_recommendations_for_list(
    manga_ids: List[int],
    db: ClientReadDatabase,
) -> List[Dict[str, Any]]:
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
        raise ValueError("Need at least 1 manga to generate recommendations")
    
    seed_total = len(manga_ids)
    seed_truncated = seed_total > MAX_RECOMMENDATION_SEEDS
    if seed_truncated:
        manga_ids = manga_ids[:MAX_RECOMMENDATION_SEEDS]

    metadata_profile = await core.get_metadata_profile_for_collection(manga_ids, db)

    candidates = await core.get_candidate_manga(
        excluded_ids=manga_ids,
        genre_ids=list(metadata_profile["genres"].keys()),
        tag_ids=list(metadata_profile["tags"].keys()),
        demo_ids=list(metadata_profile["demographics"].keys()),
        db=db,
    )

    scored = await core.get_scored_recommendations(candidates, metadata_profile, db)
    return {
    "items": scored,
    "seed_total": seed_total,
    "seed_used": len(manga_ids),
    "seed_truncated": seed_truncated,
    }
