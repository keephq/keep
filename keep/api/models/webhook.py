from pydantic import BaseModel


class WebhookSettings(BaseModel):
    webhookDescription: str | None = None
    webhookTemplate: str
