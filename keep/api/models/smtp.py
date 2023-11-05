from pydantic import BaseModel, SecretStr, validator


class SMTPSettings(BaseModel):
    host: str
    port: int
    user: str
    password: SecretStr
    use_tls: bool
    use_ssl: bool
    sender_email: str

    @validator("user", "sender_email")
    def email_validator(cls, v):
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address")
        return v

    class Config:
        schema_extra = {
            "example": {
                "host": "smtp.example.com",
                "port": 587,
                "user": "user@example.com",
                "password": "password",
                "use_tls": True,
                "use_ssl": False,
                "email": "noreply@example.com",
            }
        }
