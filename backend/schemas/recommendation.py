from pydantic import BaseModel, Field
from typing import List

class RecommendationQueryListRequest(BaseModel):
    '''
    Request payload for generating recommendations from a client-provided list of manga IDs.
    This list is NOT persisted server-side.
    '''
    manga_ids: List[int] = Field(min_length=1)