from pydantic import BaseModel, Field
from typing import List

from backend.config.limits import MAX_QUERY_LIST_SEEDS

class RecommendationQueryListRequest(BaseModel):
    '''
    Request payload for generating recommendations from a client-provided list of manga IDs.
    This list is NOT persisted server-side.
    '''
    manga_ids: List[int] = Field(
        min_length=1,
        max_length=MAX_QUERY_LIST_SEEDS,
    )
