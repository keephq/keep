from pydantic import BaseModel, Extra


class Group(BaseModel, extra=Extra.ignore):
    id: str
    name: str
    roles: list[str] = []
    members: list[str] = []
    memberCount: int = 0


class User(BaseModel, extra=Extra.ignore):
    email: str
    name: str
    role: str | None = None
    picture: str | None
    created_at: str
    last_login: str | None
    ldap: bool | None = False
    groups: list[Group] | None = []


class Role(BaseModel):
    id: str
    name: str
    description: str
    scopes: set[str]
    predefined: bool = True


class CreateOrUpdateRole(BaseModel):
    name: str | None
    description: str | None
    scopes: set[str] | None


class PermissionEntity(BaseModel):
    id: str  # permission id
    type: str  # 'user' or 'group'
    name: str | None  # permission name


class ResourcePermission(BaseModel):
    resource_id: str
    resource_name: str
    resource_type: str
    permissions: list[PermissionEntity]
