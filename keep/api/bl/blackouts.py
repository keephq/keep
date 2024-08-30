from sqlmodel import Session

from keep.api.core.db import get_session_sync
from keep.api.models.alert import AlertDto
from keep.api.models.db.blackout import BlackoutRule


class BlackoutsBl:
    def __init__(self, tenant_id: str, session: Session | None) -> None:
        self.tenant_id = tenant_id
        session = session if session else get_session_sync()
        self.blackouts = (
            session.query(BlackoutRule)
            .filter(BlackoutRule.tenant_id == tenant_id)
            .filter(BlackoutRule.enabled == True)
            .all()
        )

    def check_if_alert_in_blackout(alert: AlertDto) -> bool:
        return False
