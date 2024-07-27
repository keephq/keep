from typing import Optional

from pydantic import BaseModel, Extra


class User(BaseModel, extra=Extra.ignore):
    email: str
    name: str
    role: str
    picture: Optional[str]
    created_at: str
    last_login: Optional[str]


class Group(BaseModel, extra=Extra.ignore):
    id: str
    name: str
    roles: list[str]
    members: list[str] = []
    memberCount: int
