"""
Keep Provider is a class that allows to ingest/digest data from Keep.
"""

import copy
import logging
from datetime import datetime, timedelta, timezone
from html import unescape

import yaml

from keep.api.core.db import get_alerts_with_filters
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.tasks.process_event_task import process_event
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.searchengine.searchengine import SearchEngine
from keep.workflowmanager.workflowstore import WorkflowStore


class KeepProvider(BaseProvider):
    """
    Automation on your alerts with Keep.
    """

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        self.io_handler = IOHandler(context_manager)
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def _calculate_time_delta(self, timerange=None, default_time_range=1):
        """Calculate time delta in days from timerange dict."""
        if not timerange or "from" not in timerange:
            return default_time_range  # default value

        from_time_str = timerange["from"]
        to_time_str = timerange.get("to", "now")

        # Parse from_time and ensure it's timezone-aware
        from_time = datetime.fromisoformat(from_time_str.replace("Z", "+00:00"))
        if from_time.tzinfo is None:
            from_time = from_time.replace(tzinfo=timezone.utc)

        # Handle 'to' time
        if to_time_str == "now":
            to_time = datetime.now(timezone.utc)
        else:
            to_time = datetime.fromisoformat(to_time_str.replace("Z", "+00:00"))
            if to_time.tzinfo is None:
                to_time = to_time.replace(tzinfo=timezone.utc)

        # Calculate difference in days
        delta = (to_time - from_time).total_seconds() / (24 * 3600)  # convert to days
        return delta

    def _query(self, filters=None, version=1, distinct=True, time_delta=1, **kwargs):
        """
        Query Keep for alerts.
        """
        self.logger.info(
            "Querying Keep for alerts",
            extra={
                "filters": filters,
                "is_distinct": distinct,
                "time_delta": time_delta,
            },
        )
        # if timerange is provided, calculate time delta
        if kwargs.get("timerange"):
            time_delta = self._calculate_time_delta(
                timerange=kwargs.get("timerange"), default_time_range=time_delta
            )
        if version == 1:
            # filters are mandatory for version 1
            if not filters:
                raise ValueError("Filters are required for version")
            db_alerts = get_alerts_with_filters(
                self.context_manager.tenant_id, filters=filters, time_delta=time_delta
            )
            fingerprints = {}
            # distinct if needed
            alerts = []
            if db_alerts:
                for alert in db_alerts:
                    if fingerprints.get(alert.fingerprint) and distinct is True:
                        continue
                    alert_event = alert.event
                    if alert.alert_enrichment:
                        alert_event["enrichments"] = alert.alert_enrichment.enrichments
                    alerts.append(alert_event)
                    fingerprints[alert.fingerprint] = True
        else:
            search_engine = SearchEngine(tenant_id=self.context_manager.tenant_id)
            _filter = kwargs.get("filter")
            if not _filter:
                raise ValueError("Filter is required for version 2")
            try:
                alerts = search_engine.search_alerts_by_cel(
                    cel_query=_filter, limit=kwargs.get("limit"), timeframe=time_delta
                )
            except Exception as e:
                self.logger.exception(
                    "Failed to search alerts by CEL: %s",
                    str(e),
                )
                raise
        self.logger.info("Got alerts from Keep", extra={"num_of_alerts": len(alerts)})
        return alerts

    def _build_alerts(self, alerts, fingerprint_fields=[], **kwargs):
        """
        Build alerts from Keep.
        """
        alert_dtos = []
        for alert_result in alerts:
            labels = copy.copy(kwargs.get("labels", {}))
            labels.update(alert_result)
            alert = AlertDto(
                name=kwargs["name"],
                status=kwargs.get("status"),
                lastReceived=kwargs.get("lastReceived"),
                environment=kwargs.get("environment", "undefined"),
                duplicateReason=kwargs.get("duplicateReason"),
                service=kwargs.get("service"),
                message=kwargs.get("message"),
                description=kwargs.get("description"),
                severity=kwargs.get("severity"),
                pushed=True,
                url=kwargs.get("url"),
                labels=labels,
                ticket_url=kwargs.get("ticket_url"),
                fingerprint=kwargs.get("fingerprint"),
                annotations=kwargs.get("annotations"),
            )
            # if fingerprint_fields are provided, calculate fingerprint
            if fingerprint_fields:
                # calculate fingerprint
                self.logger.info(
                    "Calculating fingerprint for alert",
                    extra={"fingerprint_fields": fingerprint_fields},
                )
                alert.fingerprint = self.get_alert_fingerprint(
                    alert, fingerprint_fields
                )
            # else, use labels
            else:
                fingerprint_fields = list(labels.keys())
                alert.fingerprint = self.get_alert_fingerprint(
                    alert, fingerprint_fields
                )
            alert_dtos.append(alert)

        # sanity check - if more than one alert has the same fingerprint it means something is wrong
        # this would happen if the fingerprint fields are not unique
        fingerprints = {}
        for alert in alert_dtos:
            if fingerprints.get(alert.fingerprint):
                self.logger.warning(
                    "Alert with the same fingerprint already exists - it means your fingerprint labels are not unique",
                    extra={"alert": alert},
                )
            fingerprints[alert.fingerprint] = True
        return alert_dtos

    def _handle_state_alerts(
        self, _for, state_alerts: list[AlertDto], keep_firing_for=timedelta(minutes=15)
    ):
        """
        Handle state alerts with proper state transitions.
        Args:
            _for: timedelta indicating how long alert should be PENDING before FIRING
            state_alerts: list of new alerts from current evaluation
            keep_firing_for: how long to keep alerts FIRING after stopping matching (default 15m)
        Returns:
            list of alerts that need state updates
        """
        alerts_to_notify = []
        search_engine = SearchEngine(tenant_id=self.context_manager.tenant_id)
        curr_alerts = search_engine.search_alerts_by_cel(
            cel_query=f"providerId == {self.context_manager.workflow_id}",
            limit=1,
            timeframe=1,
        )

        # Create lookup by fingerprint for efficient comparison
        curr_alerts_map = {alert.fingerprint: alert for alert in curr_alerts}
        state_alerts_map = {alert.fingerprint: alert for alert in state_alerts}

        # Handle existing alerts
        for fingerprint, curr_alert in curr_alerts_map.items():
            now = datetime.now(timezone.utc)
            alert_still_exists = fingerprint in state_alerts_map

            if curr_alert.status == AlertStatus.FIRING:
                if not alert_still_exists:
                    # Check keep_firing_for logic
                    if not hasattr(curr_alert, "keep_firing_since"):
                        curr_alert.keep_firing_since = now

                    if now - curr_alert.keep_firing_since >= keep_firing_for:
                        curr_alert.status = AlertStatus.INACTIVE
                        curr_alert.resolvedAt = now
                        alerts_to_notify.append(curr_alert)
                    # else: still within keep_firing_for window, maintain FIRING state
                # else: alert still exists, maintain FIRING state

            elif curr_alert.status == AlertStatus.PENDING:
                if not alert_still_exists:
                    # PENDING alerts are immediately dropped when not present
                    # Don't add to alerts_to_notify as they're just dropped
                    continue
                else:
                    # Check if should transition to FIRING
                    if not hasattr(curr_alert, "activeAt"):
                        # This shouldn't happen but handle it gracefully
                        curr_alert.activeAt = curr_alert.lastReceived

                    if now - curr_alert.activeAt >= _for:
                        curr_alert.status = AlertStatus.FIRING
                        curr_alert.lastReceived = now
                        alerts_to_notify.append(curr_alert)

        # Handle new alerts not in current state
        for fingerprint, new_alert in state_alerts_map.items():
            if fingerprint not in curr_alerts_map:
                # Brand new alert - set to PENDING
                new_alert.status = AlertStatus.PENDING
                new_alert.activeAt = datetime.now(timezone.utc)
                alerts_to_notify.append(new_alert)

        return alerts_to_notify

    def _notify_alert(self, **kwargs):
        context = self.context_manager.get_full_context()
        alert_step = context.get("alert_step", None)
        # if alert_step is provided, get alert results
        if alert_step:
            alert_results = (
                context.get("steps", {}).get(alert_step, {}).get("results", {})
            )
        # else, the last step results are the alert results
        else:
            # TODO: this is a temporary solution until we have a better way to get the alert results
            alert_results = context.get("steps", {}).get("this", {}).get("results", {})

        _if = kwargs.get("if", None)
        _for = kwargs.get("for", None)
        fingerprint_fields = kwargs.pop("fingerprint_fields", [])

        # if we need to check _if, handle the condition
        if _if:
            # if its multialert, handle each alert separately
            if isinstance(alert_results, list):
                for alert in alert_results:
                    # render
                    cond = self.io_handler.render(alert)
                    # evaluate
                    if not self._evaluate_if(cond):
                        continue
            else:
                pass
        # build the alert dtos
        alert_dtos = self._build_alerts(alert_results, fingerprint_fields, **kwargs)
        # if _for is provided, handle state alerts
        if _for:
            # handle alerts with state
            alerts = self._handle_state_alerts(_for, alert_dtos)
        # else, handle all alerts
        else:
            alerts = alert_dtos

        # handle all alerts
        self.logger.info("handling all alerts", extra={"number_of_alerts": len(alerts)})
        process_event(
            ctx={},
            tenant_id=self.context_manager.tenant_id,
            provider_type="keep",
            provider_id=self.context_manager.workflow_id,  # so we can track the alerts that are created by this workflow
            fingerprint=kwargs.get("fingerprint"),
            api_key_name=None,
            trace_id=None,
            event=alerts,
        )
        self.logger.info("Alerts handled")

    def _notify(self, **kwargs):
        if "workflow_to_update_yaml" in kwargs:
            workflow_to_update_yaml = kwargs["workflow_to_update_yaml"]
            self.logger.info(
                "Updating workflow YAML",
                extra={"workflow_to_update_yaml": workflow_to_update_yaml},
            )
            workflowstore = WorkflowStore()
            # Create the workflow
            try:
                # In case the workflow has HTML entities:
                workflow_to_update_yaml = unescape(workflow_to_update_yaml)
                workflow_to_update_yaml = yaml.safe_load(workflow_to_update_yaml)

                if "workflow" in workflow_to_update_yaml:
                    workflow_to_update_yaml = workflow_to_update_yaml["workflow"]

                workflowstore.create_workflow(
                    tenant_id=self.context_manager.tenant_id,
                    created_by=f"workflow id: {self.context_manager.workflow_id}",
                    workflow=workflow_to_update_yaml,
                )
            except Exception as e:
                self.logger.exception(
                    "Failed to create workflow",
                    extra={
                        "tenant_id": self.context_manager.tenant_id,
                        "workflow": self.context_manager.workflow_id,
                    },
                )
                raise ProviderException(f"Failed to create workflow: {e}")
        else:
            self.logger.info("Notifying Alerts", extra={"kwargs": kwargs})
            self._notify_alert(**kwargs)
            self.logger.info("Alerts notified")

    def validate_config(self):
        """
        Validates required configuration for Keep provider.

        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        return AlertDto(
            **event,
        )

    def _evaluate_if(self, if_conf, rendered_providers_parameters):
        # Evaluate the condition string

        # aeval = Interpreter()
        rendered_providers_parameters = self._handle_tenrary_exressions(
            rendered_providers_parameters
        )
        return rendered_providers_parameters

    def _handle_tenrary_exressions(self, rendered_providers_parameters):
        # SG: a hack to allow tenrary expressions
        #     e.g.'0.012899999999999995 > 0.9 ? "critical" : 0.012899999999999995 > 0.7 ? "warning" : "info"''
        #
        #     this is a hack and should be improved
        for key, value in rendered_providers_parameters.items():
            try:
                split_value = value.split(" ")
                if split_value[1] == ">" and split_value[3] == "?":
                    import js2py

                    rendered_providers_parameters[key] = js2py.eval_js(value)
            # we don't care, it's not a tenrary expression
            except Exception:
                pass
        return rendered_providers_parameters


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
