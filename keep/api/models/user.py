from typing import Optional

from pydantic import BaseModel, Extra


class User(BaseModel, extra=Extra.ignore):
    email: str
    name: str
    picture: Optional[str]
    created_at: str
    last_login: Optional[str]
