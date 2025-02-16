from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from keep.providers.models.provider_config import ProviderScope
from keep.providers.models.provider_method import ProviderMethodDTO


class ProviderAlertsCountResponseDTO(BaseModel):
    count: int


class Provider(BaseModel):
    id: str | None = None
    display_name: str
    type: str
    config: dict[str, dict] = Field(default_factory=dict)
    details: dict[str, dict] | None = None
    can_notify: bool
    # TODO: consider making it strongly typed for UI validations
    notify_params: list[str] | None = None
    can_query: bool
    query_params: list[str] | None = None
    installed: bool = False
    # whether we got alert from this provider without installaltion
    linked: bool = False
    last_alert_received: str | None = None
    # Whether we support webhooks without install
    supports_webhook: bool = False
    # Whether we also support auto install for webhooks
    can_setup_webhook: bool = False
    # If the setup webhook checkbox in the UI is checked and disabled.
    webhook_required: bool = False
    provider_description: str | None = None
    oauth2_url: str | None = None
    scopes: list[ProviderScope] = Field(default_factory=list)
    validatedScopes: dict[str, bool | str] | None = Field(default_factory=dict)
    methods: list[ProviderMethodDTO] = Field(default_factory=list)
    installed_by: str | None = None
    installation_time: datetime | None = None
    pulling_available: bool = False
    pulling_enabled: bool = True
    last_pull_time: datetime | None = None
    docs: str | None = None
    tags: list[
        Literal[
            "alert", "ticketing", "messaging", "data", "queue", "topology", "incident"
        ]
    ] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=lambda: ["Others"])
    coming_soon: bool = False
    alertsDistribution: dict[str, int] | None = None
    alertExample: dict | None = None
    default_fingerprint_fields: list[str] | None = None
    provisioned: bool = False
    health: bool = False
