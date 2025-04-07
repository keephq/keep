from typing import Optional
from pydantic import BaseModel


class SortOptionsDto(BaseModel):
    sort_by: Optional[str]
    sort_dir: Optional[str]


class QueryDto(BaseModel):
    cel: Optional[str]
    limit: Optional[int]
    offset: Optional[int]
    sort_by: Optional[str]  # must be deprecated because we have sort_options
    sort_dir: Optional[str]  # must be deprecated because we have sort_options
    sort_options: Optional[list[SortOptionsDto]]
