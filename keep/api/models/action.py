from typing import Optional, Union, Any
from pydantic import BaseModel


class ActionDTO(BaseModel):
  id: Optional[str]
  use: str
  name: str
  details: Union[dict[str, Any], None] = None

class PartialActionDTO(BaseModel):
    use: Optional[str] = None
    name: Optional[str] = None
    details: Union[dict, None] = None
