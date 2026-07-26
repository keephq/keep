from typing import Any

from pydantic import BaseModel


class ActionDTO(BaseModel):
    id: str | None
    use: str
    name: str
    details: dict[str, Any] | None = None


class PartialActionDTO(BaseModel):
    use: str | None = None
    name: str | None = None
    details: dict | None = None
