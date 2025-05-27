from pydantic import BaseModel, Field


class EventPostBody(BaseModel):
    name: str = Field(examples=["CPU is High"])
    description: str | None = Field(examples=["CPU is high on lab server"])
    severity: str | None = Field(examples=["high"])
    environment: str | None = Field(examples=["lab"])
    product_name: str | None = Field(examples=["MetrologyX"])
    service: str | None = Field(examples=["InstrumentController"])
    operator: str | None = Field(examples=["olivia"])
    run_id: str | None = Field(examples=["TM005"])


class EventBulkPostBody(BaseModel):
    events: list[EventPostBody] = Field(
        examples=[
            [
                {
                    "name": "CPU is High",
                    "description": "CPU is high on lab server",
                    "severity": "high",
                    "environment": "lab",
                    "product_name": "MetrologyX",
                    "service": "InstrumentController",
                    "operator": "olivia",
                    "run_id": "TM005",
                }
            ]
        ]
    )
