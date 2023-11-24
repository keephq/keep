from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from keep.providers.models.provider_config import ProviderScope
from keep.providers.models.provider_method import ProviderMethod


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
    scopes: list[ProviderScope] = []
    validatedScopes: dict[str, bool | str] | None = {}
    methods: list[ProviderMethod] = []
    installed_by: str | None = None
    installation_time: datetime | None = None
    docs: str | None = None
    tags: list[Literal["alert", "ticketing", "messaging", "data", "queue"]] = []
