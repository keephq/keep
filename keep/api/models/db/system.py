
from sqlmodel import Field, SQLModel


class System(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    value: str
