import dataclasses
from typing import Optional


@dataclasses.dataclass
class AuthenticatedEntity:
    tenant_id: str
    email: str
    api_key_name: Optional[str] = None
    role: Optional[str] = None
