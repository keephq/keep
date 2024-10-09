from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TimeStampFilter(BaseModel):
    lower_timestamp: Optional[datetime] = Field(None, alias="start")
    upper_timestamp: Optional[datetime] = Field(None, alias="end")

    class Config:
        allow_population_by_field_name = True
