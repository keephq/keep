from pydantic import BaseModel


class SortOptionsDto(BaseModel):
    sort_by: str | None
    sort_dir: str | None


class QueryDto(BaseModel):
    cel: str | None
    limit: int | None = 1000
    offset: int | None = 0
    sort_by: str | None  # must be deprecated because we have sort_options
    sort_dir: str | None  # must be deprecated because we have sort_options
    sort_options: list[SortOptionsDto] | None
