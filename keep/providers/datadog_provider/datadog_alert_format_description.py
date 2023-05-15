from typing import Literal

from pydantic import BaseModel, Field


class Thresholds(BaseModel):
    critical: float
    critical_recovery: float
    ok: float
    warning: float
    warning_recovery: float
    unknown: float


class EvaluationWindow(BaseModel):
    day_starts: str
    hour_starts: int
    month_starts: int


class SchedulingOptions(BaseModel):
    evaluation_window: EvaluationWindow


class ThresholdWindows(BaseModel):
    recovery_window: str
    trigger_window: str


class DatadogOptions(BaseModel):
    enable_logs_sample: bool
    enable_samples: bool
    escalation_message: str
    evaluation_delay: int
    group_retention_duration: str
    grouby_simple_monitor: bool
    include_tags: bool
    locked: bool
    min_failure_duration: int
    min_location_failed: int
    new_group_delay: int
    new_host_delay: int
    no_data_timeframe: int
    notification_preset_name: Literal[
        "show_all", "hide_query", "hide_handles", "hide_all"
    ]
    notify_audit: bool
    notify_by: list[str]
    notify_no_data: bool
    on_missing_data: Literal[
        "default", "show_no_data", "show_and_notify_no_data", "resolve"
    ]
    renotify_interval: int
    renotify_occurrences: int
    renotify_statuses: list[str]
    require_full_window: bool
    cheduling_options: SchedulingOptions
    silenced: dict
    threshold_windows: ThresholdWindows
    # thresholds: Thresholds
    timeout_h: int


class DatadogAlertFormatDescription(BaseModel):
    message: str = Field(
        ..., description="A message to include with notifications for this monitor."
    )
    name: str = Field(..., description="The name of the monitor.")
    options: DatadogOptions
    priority: int = Field(..., description="The priority of the monitor.", min=1, max=5)
    query: str = Field(..., description="The query to monitor.", required=True)
    tags: list[str]
    type: Literal[
        "composite",
        "event alert",
        "log alert",
        "metric alert",
        "process alert",
        "query alert",
        "rum alert",
        "service check",
        "synthetics alert",
        "trace-analytics alert",
        "slo alert",
        "event-v2 alert",
        "audit alert",
        "ci-pipelines alert",
        "ci-tests alert",
        "error-tracking alert",
    ]

    class Config:
        schema_extra = {
            "example": {
                "name": "Example-Monitor",
                "type": "rum alert",
                "query": 'formula("query2 / query1 * 100").last("15m") >= 0.8',
                "message": "some message Notify: @hipchat-channel",
                "tags": ["test:examplemonitor", "env:ci"],
                "priority": 3,
                "options": {
                    "thresholds": {"critical": 0.8},
                    "variables": [
                        {
                            "data_source": "rum",
                            "name": "query2",
                            "search": {"query": ""},
                            "indexes": ["*"],
                            "compute": {"aggregation": "count"},
                            "group_by": [],
                        },
                        {
                            "data_source": "rum",
                            "name": "query1",
                            "search": {"query": "status:error"},
                            "indexes": ["*"],
                            "compute": {"aggregation": "count"},
                            "group_by": [],
                        },
                    ],
                },
            }
        }
