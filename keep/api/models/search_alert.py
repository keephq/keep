from pydantic import BaseModel, Extra, Field, validator

from keep.searchengine.searchengine import SearchQuery


class SearchAlertsRequest(BaseModel):
    query: SearchQuery = Field(..., alias="query")
    timeframe: int = Field(..., alias="timeframe")

    @validator("query")
    def validate_search_query(cls, value):
        if value.timestamp < 0:
            raise ValueError("Timestamp must be greater than or equal to 0.")
        return value

    class Config:
        extra = Extra.allow
