from pydantic import BaseModel


class Provider(BaseModel):
    id: str | None = None
    type: str
    config: dict[str, dict] = {}
    details: dict[str, dict] | None = None
    can_notify: bool
    can_query: bool
    installed: bool = False
