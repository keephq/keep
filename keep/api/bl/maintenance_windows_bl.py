import datetime
import json
import logging

import celpy
from sqlmodel import Session

from keep.api.core.db import get_session_sync
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.alert import ActionType, AlertAudit
from keep.api.models.db.maintenance_window import MaintenanceWindowRule
from keep.api.utils.cel_utils import preprocess_cel_expression


class MaintenanceWindowsBl:

    ALERT_STATUSES_TO_IGNORE = [
        AlertStatus.RESOLVED.value,
        AlertStatus.ACKNOWLEDGED.value,
    ]

    def __init__(self, tenant_id: str, session: Session | None) -> None:
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        self.session = session if session else get_session_sync()
        self.maintenance_rules: list[MaintenanceWindowRule] = (
            self.session.query(MaintenanceWindowRule)
            .filter(MaintenanceWindowRule.tenant_id == tenant_id)
            .filter(MaintenanceWindowRule.enabled == True)
            .filter(MaintenanceWindowRule.end_time >= datetime.datetime.now())
            .all()
        )

    def check_if_alert_in_maintenance_windows(self, alert: AlertDto) -> bool:
        extra = {"tenant_id": self.tenant_id, "fingerprint": alert.fingerprint}

        if not self.maintenance_rules:
            self.logger.debug(
                "No maintenance window rules for this tenant",
                extra={"tenant_id": self.tenant_id},
            )
            return False

        if alert.status in self.ALERT_STATUSES_TO_IGNORE:
            self.logger.debug(
                "Alert status is set to be ignored, ignoring maintenance windows",
                extra={"tenant_id": self.tenant_id},
            )
            return False

        self.logger.info("Checking maintenance window for alert", extra=extra)
        env = celpy.Environment()

        for maintenance_rule in self.maintenance_rules:
            if maintenance_rule.end_time <= datetime.datetime.now():
                # this is wtf error, should not happen because of query in init
                self.logger.error(
                    "Fetched maintenance window which already ended by mistake, should not happen!"
                )
                continue

            cel = preprocess_cel_expression(maintenance_rule.cel_query)
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
                    "Alert is in maintenance window",
                    extra={**extra, "maintenance_rule_id": maintenance_rule.id},
                )

                try:
                    audit = AlertAudit(
                        tenant_id=self.tenant_id,
                        fingerprint=alert.fingerprint,
                        user_id="Keep",
                        action=ActionType.MAINTENANCE.value,
                        description=(
                            f"Alert in maintenance due to rule `{maintenance_rule.name}`"
                            if not maintenance_rule.suppress
                            else f"Alert suppressed due to maintenance rule `{maintenance_rule.name}`"
                        ),
                    )
                    self.session.add(audit)
                    self.session.commit()
                except Exception:
                    self.logger.exception(
                        "Failed to write audit for alert maintenance window",
                        extra={
                            "tenant_id": self.tenant_id,
                            "fingerprint": alert.fingerprint,
                        },
                    )

                if maintenance_rule.suppress:
                    # If user chose to suppress the alert, let it in but override the status.
                    alert.status = AlertStatus.SUPPRESSED.value
                    return False

                return True
        self.logger.info("Alert is not in maintenance window", extra=extra)
        return False
