from backend.recommendation import core
from typing import List, Dict, Any
from backend.db.models.manga import Manga
from sqlalchemy.ext.asyncio import AsyncSession

async def generate_recommendations(
    user_id: int,
    collection_id: int,
    session: AsyncSession
) -> List[Dict[str, Any]]:
    """
    Top-level function to generate recommendations based on a user's selected collection.
    Calls internal steps for fetching manga, generating metadata profile, candidates, and scoring.
    """
    # Get all manga in collection
    manga_ids = await core.get_manga_ids_in_user_collection(user_id, collection_id, session)
    if not manga_ids:
        raise ValueError("Need at least 1 manga in the collection to generate recommendations")

    # Create metadata profile
    metadata_profile = await core.get_metadata_profile_for_collection(manga_ids, session)

    # Get candidates
    candidates = await core.get_candidate_manga(
        excluded_ids=manga_ids,
        genre_ids=list(metadata_profile["genres"].keys()),
        tag_ids=list(metadata_profile["tags"].keys()),
        demo_ids=list(metadata_profile["demographics"].keys()),
        session=session
    )

    scored = await core.get_scored_recommendations(candidates, metadata_profile, session)

    return scored