from typing import Optional

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass


@dataclass(config=ConfigDict(extra="allow"))
class AuthenticatedEntity:
    tenant_id: str
    email: str
    api_key_name: Optional[str] = None
    role: Optional[str] = None
