from pydantic import BaseModel, Extra


class StepProviderParameter(BaseModel):
    class Config:
        extra = Extra.forbid
    key: str  # the key to render
    safe: bool = False  # whether to validate this key or fail silently ("safe")
    default: str | int | bool = None  # default value if this key doesn't exist
