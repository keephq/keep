from collections import OrderedDict
from datetime import datetime
from typing import List, Literal, Optional

import yaml
from pydantic import BaseModel, validator


def represent_ordered_dict(dumper, data):
    filtered_data = {k: v for k, v in data.items() if v is not None}
    return dumper.represent_mapping("tag:yaml.org,2002:map", filtered_data.items())


yaml.add_representer(OrderedDict, represent_ordered_dict)


class ProviderDTO(BaseModel):
    type: str
    id: str | None  # if not installed - no id
    name: str
    installed: bool


class WorkflowDTO(BaseModel):
    id: str
    name: str
    description: Optional[str] = "Workflow file doesn't contain description"
    created_by: str
    creation_time: datetime
    triggers: List[dict] = None
    interval: int
    last_execution_time: datetime = None
    last_execution_status: str = None
    providers: List[ProviderDTO]
    workflow_raw: str
    revision: int = 1
    last_updated: datetime = None

    @property
    def workflow_raw_id(self):
        id = yaml.safe_load(self.workflow_raw).get("id")
        return id

    @validator("workflow_raw", pre=False, always=True)
    def manipulate_raw(cls, raw, values):
        """We want to control the "sort" of a workflow when it gets to the front:
            1. id
            2. desc
            3. triggers
            4 --- all the rest ---
            5. steps
            6. actions

        Args:
            raw (_type_): _description_

        Returns:
            _type_: _description_
        """
        ordered_raw = OrderedDict()
        d = yaml.safe_load(raw)
        # id desc and triggers
        ordered_raw["id"] = d.get("id")
        values["workflow_raw_id"] = d.get("id")
        ordered_raw["description"] = d.get("description")
        ordered_raw["triggers"] = d.get("triggers")
        for key, val in d.items():
            if key not in ["id", "description", "triggers", "steps", "actions"]:
                ordered_raw[key] = val
        # than steps and actions
        ordered_raw["steps"] = d.get("steps")
        # last, actions
        ordered_raw["actions"] = d.get("actions")
        return yaml.dump(ordered_raw)


class WorkflowExecutionLogsDTO(BaseModel):
    id: int
    timestamp: datetime
    message: str
    context: Optional[dict]


class WorkflowExecutionDTO(BaseModel):
    id: str
    workflow_id: str
    started: datetime
    triggered_by: str
    status: str
    logs: Optional[List[WorkflowExecutionLogsDTO]]
    error: Optional[str]
    execution_time: Optional[int]
    results: Optional[dict]


class WorkflowCreateOrUpdateDTO(BaseModel):
    workflow_id: str
    status: Literal["created", "updated"]
    revision: int = 1
