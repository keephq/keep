from pydantic import AnyHttpUrl, BaseModel, Extra, validator


class AlertDto(BaseModel):
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
    event_id: str | None = None  # Database alert id
    url: AnyHttpUrl | None = None
    labels: dict | None = {}
    fingerprint: str | None = (
        None  # The fingerprint of the alert (used for alert de-duplication)
    )
    deleted: bool = False  # Whether the alert is deleted or not

    @validator("fingerprint", pre=True, always=True)
    def assign_fingerprint_if_none(cls, fingerprint, values):
        if fingerprint is None:
            return values.get("name", "")
        return fingerprint

    class Config:
        extra = Extra.allow
        schema_extra = {
            "examples": [
                {
                    "id": "1234",
                    "name": "Alert name",
                    "status": "firing",
                    "lastReceived": "2021-01-01T00:00:00.000Z",
                    "environment": "production",
                    "isDuplicate": False,
                    "duplicateReason": None,
                    "service": "backend",
                    "source": ["keep"],
                    "message": "Alert message",
                    "description": "Alert description",
                    "severity": "critical",
                    "fatigueMeter": 0,
                    "pushed": True,
                    "event_id": "1234",
                    "url": "https://www.google.com/search?q=open+source+alert+management",
                    "fingerprint": "Alert name",
                }
            ]
        }


class DeleteRequestBody(BaseModel):
    fingerprint: str | None = None
    restore: bool = False


class EnrichAlertRequestBody(BaseModel):
    enrichments: dict[str, str]
    fingerprint: str
