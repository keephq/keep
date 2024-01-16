from typing import Optional

from pydantic import BaseModel, Extra

class APIKeyDTO(BaseModel, extra=Extra.ignore):
    key_name: str
    description: str
    created_at: str