import json
from datetime import datetime

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field


class TimeStampFilter(BaseModel):
    lower_timestamp: datetime | None = Field(None, alias="start")
    upper_timestamp: datetime | None = Field(None, alias="end")

    class Config:
        allow_population_by_field_name = True


# Function to handle the time_stamp query parameter and parse it
def _get_time_stamp_filter(time_stamp: str | None = Query(None)) -> TimeStampFilter:
    if time_stamp:
        try:
            # Parse the JSON string
            time_stamp_dict = json.loads(time_stamp)
            # Return the TimeStampFilter object, Pydantic will map 'from' -> lower_timestamp and 'to' -> upper_timestamp
            return TimeStampFilter(**time_stamp_dict)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid time_stamp format")
    return TimeStampFilter()
