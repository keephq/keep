from __future__ import annotations

from typing import List

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
    condition: str
    data: List[Datum]
    execErrState: str
    folderUID: str
    for_: str = Field(..., alias="for", description="For example: 5m/1h/1d")
    isPaused: bool
    labels: list[str]
    noDataState: str
    orgID: int
    ruleGroup: str
    title: str
