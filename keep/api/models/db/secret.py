from datetime import datetime

from sqlmodel import Field, SQLModel

class Secret(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
    
    lastmodification_time: datetime = Field(
        default_factory=datetime.utcnow, 
    )

    class Config:
        orm_mode = True