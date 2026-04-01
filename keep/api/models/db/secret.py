from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class Secret(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = Field(sa_column=sa.Column(sa.Text, nullable=False))

    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
    )

    class Config:
        orm_mode = True
