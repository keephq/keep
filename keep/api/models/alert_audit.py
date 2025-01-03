from datetime import datetime

from pydantic import BaseModel

from keep.api.models.db.alert import ActionType, AlertAudit


class AlertAuditDto(BaseModel):
    id: str
    timestamp: datetime
    fingerprint: str
    action: ActionType
    user_id: str
    description: str

    @classmethod
    def from_orm(cls, alert_audit: AlertAudit) -> "AlertAuditDto":
        return cls(
            id=str(alert_audit.id),
            timestamp=alert_audit.timestamp,
            fingerprint=alert_audit.fingerprint,
            action=alert_audit.action,
            user_id=alert_audit.user_id,
            description=alert_audit.description,
        )

    @classmethod
    def from_orm_list(cls, alert_audits: list[AlertAudit]) -> list["AlertAuditDto"]:
        grouped_events = []
        previous_event = None
        count = 1

        for event in alert_audits:
            # Check if the current event is similar to the previous event
            if previous_event and (
                event.user_id == previous_event.user_id
                and event.action == previous_event.action
                and event.description == previous_event.description
            ):
                # Increment the count if the events are similar
                count += 1
            else:
                # If the events are not similar, append the previous event to the grouped events
                if previous_event:
                    if count > 1:
                        previous_event.description += f" x{count}"
                    grouped_events.append(AlertAuditDto.from_orm(previous_event))
                # Update the previous event to the current event and reset the count
                previous_event = event
                count = 1

        # Add the last event to the grouped events
        if previous_event:
            if count > 1:
                previous_event.description += f" x{count}"
            grouped_events.append(AlertAuditDto.from_orm(previous_event))
        return grouped_events
