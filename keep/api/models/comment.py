from typing import List
from pydantic import BaseModel
from keep.api.models.db.incident import IncidentStatus

class IncidentCommentDto(BaseModel):
    status: IncidentStatus
    comment: str
    mentioned_users: List[str] = []