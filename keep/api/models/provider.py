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
    can_setup_webhook: bool = False
