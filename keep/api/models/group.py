from typing import Optional

from pydantic import BaseModel


class AlertSummaryDto(BaseModel):
    alert_summary: Optional[str]
    alert_fingerprint: str


class GroupDto(BaseModel):
    group_description: Optional[str]
    start_time: str
    last_update_time: str
    alerts: list[AlertSummaryDto]

    @staticmethod
    def get_group_attributes(alerts):
        return {
            "start_time": str(min([alert.timestamp for alert in alerts])),
            "last_update_time": str(
                max([alert.event.get("lastReceived") for alert in alerts])
            ),
            "num_of_alerts": len(alerts),
        }
