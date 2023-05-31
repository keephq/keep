from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class Evaluator(BaseModel):
    params: List[int]
    type: str


class Operator(BaseModel):
    type: str


class Query(BaseModel):
    params: List


class Reducer(BaseModel):
    params: List
    type: str


class Condition(BaseModel):
    evaluator: Evaluator
    operator: Operator
    query: Query
    reducer: Reducer
    type: str


class Datasource(BaseModel):
    type: str
    uid: str


class Model1(BaseModel):
    conditions: List[Condition]
    datasource: Datasource
    expression: str
    hide: bool
    intervalMs: int
    maxDataPoints: int
    refId: str
    type: str


class RelativeTimeRange(BaseModel):
    from_: int = Field(..., alias="from")
    to: int


class Datum(BaseModel):
    datasourceUid: str
    model: Model1
    queryType: str
    refId: str
    relativeTimeRange: RelativeTimeRange


class GrafanaAlertFormatDescription(BaseModel):
    condition: str = Field(
        ..., max_length=1, description="Must be one of the refId in data"
    )
    data: List[Datum]
    execErrState: Literal["OK", "Alerting", "Error"]
    folderUID: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Folder UID, cannot be empty",
        required=True,
    )
    for_: str = Field(..., alias="for", description="For example: 5m/1h/1d")
    isPaused: bool
    labels: dict = Field(..., description="Key-value pairs, cannot be empty")
    noDataState: Literal["NoData", "OK", "Alerting"]
    orgID: int
    ruleGroup: str = Field(
        ..., max_length=190, min_length=1, description="Rule group name"
    )
    title: str = Field(
        ..., max_length=190, min_length=1, description="Alert title", required=True
    )

    class Config:
        schema_extra = {
            "example": {
                "condition": "A",
                "folderUID": "keep_alerts",
                "labels": {"team": "sre-team-1"},
                "ruleGroup": "keep_group_1",
            },
        }
