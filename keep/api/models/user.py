from typing import List, Optional

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


class PermissionEntity(BaseModel):
    id: str
    type: str  # 'user' or 'group'


class ResourcePermission(BaseModel):
    resource_id: str
    resource_name: str
    resource_type: str
    permissions: List[PermissionEntity]
