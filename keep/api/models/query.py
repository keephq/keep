from typing import Optional
from pydantic import BaseModel


class QueryDto(BaseModel):
    cel: Optional[str]
    limit: Optional[int]
    offset: Optional[int]
    sort_by: Optional[str]
    sort_dir: Optional[str]
