from typing import Optional

from pydantic import BaseModel, SecretStr, validator


class SMTPSettings(BaseModel):
    host: str
    port: int
    from_email: str
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    secure: bool = True
    # Only for testing
    to_email: Optional[str] = "keep@example.com"

    @validator("from_email", "to_email")
    def email_validator(cls, v):
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address")
        return v

    class Config:
        schema_extra = {
            "example": {
                "host": "smtp.example.com",
                "port": 587,
                "username": "user@example.com",
                "password": "password",
                "secure": True,
                "from_email": "noreply@example.com",
                "to_email": "",
            }
        }
