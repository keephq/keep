import datetime
import json
import logging

import celpy
from sqlmodel import Session

from keep.api.consts import KEEP_CORRELATION_ENABLED, MAINTENANCE_WINDOW_ALERT_STRATEGY
from opentelemetry import trace
from keep.api.core.db import (
    add_audit,
    get_alerts_by_status,
    get_all_presets_dtos,
    get_maintenance_windows_started,
    get_session_sync,
    recover_prev_alert_status,
)
from keep.api.core.dependencies import get_pusher_client
from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.alert import Alert, AlertAudit
from keep.api.models.db.maintenance_window import MaintenanceWindowRule
from keep.api.tasks.notification_cache import get_notification_cache
from keep.api.utils.cel_utils import preprocess_cel_expression
from keep.rulesengine.rulesengine import RulesEngine
from keep.workflowmanager.workflowmanager import WorkflowManager

tracer = trace.get_tracer(__name__)

class MaintenanceWindowsBl:

    def __init__(self, tenant_id: str, session: Session | None) -> None:
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        self.session = session if session else get_session_sync()
        self.maintenance_rules: list[MaintenanceWindowRule] = (
            self.session.query(MaintenanceWindowRule)
            .filter(MaintenanceWindowRule.tenant_id == tenant_id)
            .filter(MaintenanceWindowRule.enabled == True)
            .filter(MaintenanceWindowRule.end_time >= datetime.datetime.now(datetime.UTC))
            .filter(MaintenanceWindowRule.start_time <= datetime.datetime.now(datetime.UTC))
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

        self.logger.info("Checking maintenance window for alert", extra=extra)
        env = celpy.Environment()

        for maintenance_rule in self.maintenance_rules:
            if alert.status in maintenance_rule.ignore_statuses:
                self.logger.debug(
                    "Alert status is set to be ignored, ignoring maintenance windows",
                    extra={"tenant_id": self.tenant_id},
                )
                continue

            if maintenance_rule.end_time.replace(tzinfo=datetime.UTC) <= datetime.datetime.now(datetime.UTC):
                # this is wtf error, should not happen because of query in init
                self.logger.error(
                    "Fetched maintenance window which already ended by mistake, should not happen!"
                )
                continue

            cel_result = MaintenanceWindowsBl.evaluate_cel(maintenance_rule, alert, env, self.logger, extra)

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
                    if MAINTENANCE_WINDOW_ALERT_STRATEGY == "recover_previous_status":
                        alert.previous_status = alert.status
                        alert.status = AlertStatus.MAINTENANCE.value
                    else:
                        alert.status = AlertStatus.SUPPRESSED.value
                    return False

                return True
        self.logger.info("Alert is not in maintenance window", extra=extra)
        return False

    @staticmethod
    def evaluate_cel(maintenance_window: MaintenanceWindowRule, alert: AlertDto | Alert, environment: celpy.Environment, logger, logger_extra_info: dict) -> bool:

        cel = preprocess_cel_expression(maintenance_window.cel_query)
        ast = environment.compile(cel)
        prgm = environment.program(ast)

        if isinstance(alert, AlertDto):
            payload = alert.dict()
        else:
            payload = alert.event
        # todo: fix this in the future
        payload["source"] = payload["source"][0]

        activation = celpy.json_to_cel(json.loads(json.dumps(payload, default=str)))

        try:
            cel_result = prgm.evaluate(activation)
            return True if cel_result else False
        except celpy.evaluation.CELEvalError as e:
            error_msg = str(e).lower()
            if "no such member" in error_msg or "undeclared reference" in error_msg:
                logger.debug(
                    f"Skipping maintenance window rule due to missing field: {str(e)}",
                    extra={**logger_extra_info, "maintenance_rule_id": maintenance_window.id},
                )
                return False
            # Log unexpected CEL errors but don't fail the entire event processing
            logger.error(
                f"Unexpected CEL evaluation error: {str(e)}",
                extra={**logger_extra_info, "maintenance_rule_id": maintenance_window.id},
            )
            return False

    @staticmethod
    def recover_strategy(
        logger: logging.Logger,
        session: Session | None = None,
    ):
        """

        This strategy will try to recover the previous status of the alerts that were in maintenance windows,
        once the maintenance windows are over, i.e they were deleted.

        For recovering the previous status, the maintenance windows shouldn't exist and the alerts
        should accomplish the following:

            - The alert is in [inhibited_status] status.
            - The alert timestamp is before the maintenance window end time.
            - The alert timestamp is after the maintenance window start time.
            - The CEL expression should match with the both alert and maintenance window.

        Once the status is recovered, Workflows, Correlations/Incidents and Presets will be launched, in the
        same way that a new alert.


        Args:
            logger (logging.Logger): The logger to use.
            session (Session | None): The SQLAlchemy session to use. If None, a new session will be created.
        """
        logger.info("Starting recover strategy for maintenance windows review.")
        env = celpy.Environment()
        if session is None:
            session = get_session_sync()
        windows = get_maintenance_windows_started(session)
        alerts_in_maint = get_alerts_by_status(AlertStatus.MAINTENANCE, session)
        for alert in alerts_in_maint:
            active = False
            for window in windows:
                w_start = window.start_time
                w_end = window.end_time
                is_enable = window.enabled
                if window.tenant_id != alert.tenant_id:
                    continue
                # Check active windows
                if w_start < alert.timestamp and alert.timestamp < w_end and is_enable:
                    logger.info("Checking alert %s in maintenance window %s", alert.id, window.id)
                    is_in_cel = MaintenanceWindowsBl.evaluate_cel(
                                window, alert, env, logger, {"tenant_id": alert.tenant_id, "alert_id": alert.id}
                                )
                    if is_in_cel:
                        active = True
                        logger.info("Alert %s is blocked due to the maintenance window: %s.", alert.id, window.id)
                        break
            if not active:
                recover_prev_alert_status(alert, session)
                add_audit(
                    tenant_id=alert.tenant_id,
                    fingerprint=alert.fingerprint,
                    user_id="system",
                    action=ActionType.MAINTENANCE_EXPIRED,
                    description=(
                        f"Alert {alert.id} has recover its previous status, "
                        f"from {alert.event.get('previous_status')} to {alert.event.get('status')}"
                    ),
                )

                alert_dto = AlertDto(**alert.event)
                with tracer.start_as_current_span("mw_recover_strategy_push_to_workflows"):
                    try:
                        # Now run any workflow that should run based on this alert
                        # TODO: this should publish event
                        workflow_manager = WorkflowManager.get_instance()
                        # insert the events to the workflow manager process queue
                        logger.info("Adding event to the workflow manager queue")
                        workflow_manager.insert_events(alert.tenant_id, [alert_dto])
                        logger.info("Added event to the workflow manager queue")
                    except Exception:
                        logger.exception(
                            "Failed to run workflows based on alerts",
                            extra={
                                "provider_type": alert_dto.providerType,
                                "provider_id": alert_dto.providerId,
                                "tenant_id": alert.tenant_id,
                            },
                        )

                with tracer.start_as_current_span("mw_recover_strategy_run_rules_engine"):
                    # Now we need to run the rules engine
                    if KEEP_CORRELATION_ENABLED:
                        incidents = []
                        try:
                            rules_engine = RulesEngine(tenant_id=alert.tenant_id)
                            # handle incidents, also handle workflow execution as
                            incidents = rules_engine.run_rules(
                                [alert_dto], session=session
                            )
                        except Exception:
                            logger.exception(
                                "Failed to run rules engine",
                                extra={
                                    "provider_type": alert_dto.providerType,
                                    "provider_id": alert_dto.providerId,
                                    "tenant_id": alert.tenant_id,
                                },
                            )
                        pusher_cache = get_notification_cache()
                        if incidents and pusher_cache.should_notify(alert.tenant_id, "incident-change"):
                            pusher_client = get_pusher_client()
                            try:
                                pusher_client.trigger(
                                    f"private-{alert.tenant_id}",
                                    "incident-change",
                                    {},
                                )
                            except Exception:
                                logger.exception("Failed to tell the client to pull incidents")

                    try:
                        presets = get_all_presets_dtos(alert.tenant_id)
                        rules_engine = RulesEngine(tenant_id=alert.tenant_id)
                        presets_do_update = []
                        for preset_dto in presets:
                            # filter the alerts based on the search query
                            filtered_alerts = rules_engine.filter_alerts(
                                [alert_dto], preset_dto.cel_query
                            )
                            # if not related alerts, no need to update
                            if not filtered_alerts:
                                continue
                            presets_do_update.append(preset_dto)
                        if pusher_cache.should_notify(alert.tenant_id, "poll-presets"):
                            try:
                                pusher_client.trigger(
                                    f"private-{alert.tenant_id}",
                                    "poll-presets",
                                    json.dumps(
                                        [p.name.lower() for p in presets_do_update], default=str
                                    ),
                                )
                            except Exception:
                                logger.exception("Failed to send presets via pusher")
                    except Exception:
                        logger.exception(
                            "Failed to send presets via pusher",
                            extra={
                                "provider_type": alert_dto.providerType,
                                "provider_id": alert_dto.providerId,
                                "tenant_id": alert.tenant_id,
                            },
                        )
        logger.info("Finished recover strategy for maintenance windows review.")