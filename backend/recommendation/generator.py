import uuid
from backend.recommendation import core
from typing import List, Dict, Any
from backend.db.client_db import ClientReadDatabase

async def generate_recommendations(
    user_id: uuid.UUID,
    collection_id: int,
    db: ClientReadDatabase
) -> List[Dict[str, Any]]:
    '''
    Generate recommendations for the given user's collection by composing core steps.

    Args:
        user_id (uuid.UUID): Identifier of the current user.
        collection_id (int): Target collection identifier.
        session (AsyncSession): SQLAlchemy async session bound to the manga domain.

    Returns:
        list: Ranked recommendations as a list of dictionaries (title, ids, scores, and additional attributes).
    '''
    # Get all manga in collection
    manga_ids = await core.get_manga_ids_in_user_collection(user_id, collection_id, db)
    if not manga_ids:
        raise ValueError("Need at least 1 manga in the collection to generate recommendations")

    metadata_profile = await core.get_metadata_profile_for_collection(manga_ids, db)

    candidates = await core.get_candidate_manga(
        excluded_ids=manga_ids,
        genre_ids=list(metadata_profile["genres"].keys()),
        tag_ids=list(metadata_profile["tags"].keys()),
        demo_ids=list(metadata_profile["demographics"].keys()),
        db=db
    )

    scored = await core.get_scored_recommendations(candidates, metadata_profile, db)
    return scored