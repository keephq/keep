from pydantic import BaseModel, Field


class IncidentPostBody(BaseModel):
    id: str = Field(
        examples=["incident_123"],
    )
    user_generated_name: str = Field(examples=["CPU is High"])
    user_summary: str | None = Field(examples=["CPU is high on lab server"])


class IncidentBulkPostBody(BaseModel):
    incidents: list[IncidentPostBody] = Field(
        examples=[
            [
                {
                    "id": "incident_123",
                    "user_generated_name": "CPU is High",
                    "user_summary": "CPU is high on lab server",
                }
            ]
        ]
    )


class IncidentDto(BaseModel):
    id: str = Field(examples=["incident_123"])
    user_generated_name: str = Field(examples=["CPU is High"])
    user_summary: str | None = Field(examples=["CPU is high on lab server"])
