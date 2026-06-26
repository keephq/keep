from datetime import datetime

from sqlalchemy import TEXT, Column
from sqlmodel import Field, SQLModel

class Secret(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = Field(sa_column=Column(TEXT, nullable=False))
    
    last_updated: datetime = Field(
        default_factory=datetime.utcnow, 
    )

    class Config:
        orm_mode = True