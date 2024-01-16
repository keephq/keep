from datetime import datetime

from sqlmodel import Field, SQLModel

# THIS IS ONLY FOR SINGLE TENANT (self-hosted) USAGES
from keep.api.core.dependencies import SINGLE_TENANT_UUID

class APIKey(SQLModel, table=True):
    # Unique ID for each API key
    id: int = Field(primary_key=True)

    tenant_id: str = Field(default=SINGLE_TENANT_UUID)

    # API Key name for identification
    key_name: str = Field(index=True, unique=True)

    # Description for the API Key
    description: str

    # Timestamp for API Key creation
    created_at: datetime = Field(default_factory=datetime.utcnow)