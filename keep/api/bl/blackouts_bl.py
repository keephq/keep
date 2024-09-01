import json
import logging

import celpy
from sqlmodel import Session

from keep.api.core.db import get_session_sync
from keep.api.models.alert import AlertDto
from keep.api.models.db.blackout import BlackoutRule
from keep.api.utils.cel_utils import preprocess_cel_expression


class BlackoutsBl:
    def __init__(self, tenant_id: str, session: Session | None) -> None:
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        session = session if session else get_session_sync()
        self.blackouts: list[BlackoutRule] = (
            session.query(BlackoutRule)
            .filter(BlackoutRule.tenant_id == tenant_id)
            .filter(BlackoutRule.enabled == True)
            .all()
        )

    def check_if_alert_in_blackout(self, alert: AlertDto) -> bool:
        extra = {"tenant_id": self.tenant_id, "fingerprint": alert.fingerprint}
        self.logger.info("Checking blackout for alert", extra=extra)
        env = celpy.Environment()

        for blackout in self.blackouts:
            cel = preprocess_cel_expression(blackout.cel_query)
            ast = env.compile(cel)
            prgm = env.program(ast)

            payload = alert.dict()
            # todo: fix this in the future
            payload["source"] = payload["source"][0]

            activation = celpy.json_to_cel(json.loads(json.dumps(payload, default=str)))

            try:
                cel_result = prgm.evaluate(activation)
            except celpy.evaluation.CELEvalError as e:
                if "no such member" in str(e):
                    continue
                # wtf
                raise
            if cel_result:
                self.logger.info(
                    "Alert is blacked out", extra={**extra, "blackout_id": blackout.id}
                )
                return True
        self.logger.info("Alert is not blacked out", extra=extra)
        return False
