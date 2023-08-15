from pydantic import BaseModel, Extra


class AlertDto(BaseModel, extra=Extra.allow):
    id: str
    name: str
    status: str
    lastReceived: str
    environment: str = "undefined"
    isDuplicate: bool | None = None
    duplicateReason: str | None = None
    service: str | None = None
    source: list[str] | None = []
    message: str | None = None
    description: str | None = None
    severity: str | None = None
    fatigueMeter: int | None = None
    pushed: bool = False  # Whether the alert was pushed or pulled from the provider
