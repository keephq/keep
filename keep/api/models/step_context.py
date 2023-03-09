from pydantic import BaseModel


class StepContext(BaseModel):
    step_id: str
    step_context: dict
