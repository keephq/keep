from pydantic import BaseModel


class WorkflowStatsDalModel(BaseModel):
    pass_count: int
    fail_count: int
    avg_duration: float
