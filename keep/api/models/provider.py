from datetime import datetime

from pydantic import BaseModel


class Provider(BaseModel):
    id: str | None = None
    type: str
    config: dict[str, dict] = {}
    details: dict[str, dict] | None = None
    can_notify: bool
    # TODO: consider making it strongly typed for UI validations
    notify_params: list[str] | None = None
    can_query: bool
    query_params: list[str] | None = None
    installed: bool = False
    # Whether we support webhooks without install
    supports_webhook: bool = False
    # Whether we also support auto install for webhooks
    can_setup_webhook: bool = False
    provider_description: str | None = None
    oauth2_url: str | None = None
    installed_by: str | None = None
    installation_time: datetime | None = None
