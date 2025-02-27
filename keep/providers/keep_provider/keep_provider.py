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

    def _build_alert(self, alert_data, fingerprint_fields=[], **kwargs):
        """
        Build alerts from Keep.
        """
        labels = copy.copy(kwargs.get("labels", {}))
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
            workflowId=self.context_manager.workflow_id,
            **alert_data,
        )
        # if fingerprint_fields are not provided, use labels
        if not fingerprint_fields:
            fingerprint_fields = ["labels." + label for label in list(labels.keys())]

        # workflowId is used as the "rule id" - it's used to identify the rule that created the alert
        fingerprint_fields.append("workflowId")
        alert.fingerprint = self.get_alert_fingerprint(alert, fingerprint_fields)
        return alert

    def _handle_state_alerts(
        self, _for, state_alerts: list[AlertDto], keep_firing_for=timedelta(minutes=15)
    ):
        """
        Handle state alerts with proper state transitions.
        Args:
            _for: timedelta indicating how long alert should be PENDING before FIRING
            state_alerts: list of new alerts from current evaluation
            keep_firing_for: (future use) how long to keep alerts FIRING after stopping matching (default 15m)
        Returns:
            list of alerts that need state updates
        """
        self.logger.info(
            "Starting state alert handling", extra={"num_alerts": len(state_alerts)}
        )
        alerts_to_notify = []
        search_engine = SearchEngine(tenant_id=self.context_manager.tenant_id)
        curr_alerts = search_engine.search_alerts_by_cel(
            cel_query=f"providerId == '{self.context_manager.workflow_id}'"
        )
        self.logger.debug(
            "Found existing alerts", extra={"num_curr_alerts": len(curr_alerts)}
        )

        # Create lookup by fingerprint for efficient comparison
        curr_alerts_map = {alert.fingerprint: alert for alert in curr_alerts}
        state_alerts_map = {alert.fingerprint: alert for alert in state_alerts}
        self.logger.debug(
            "Created alert maps",
            extra={
                "curr_alerts_count": len(curr_alerts_map),
                "state_alerts_count": len(state_alerts_map),
            },
        )

        # Handle existing alerts
        for fingerprint, curr_alert in curr_alerts_map.items():
            now = datetime.now(timezone.utc)
            alert_still_exists = fingerprint in state_alerts_map
            self.logger.debug(
                "Processing existing alert",
                extra={
                    "fingerprint": fingerprint,
                    "still_exists": alert_still_exists,
                    "current_status": curr_alert.status,
                },
            )

            if curr_alert.status == AlertStatus.FIRING.value:
                if not alert_still_exists:
                    # TODO: keep_firing_for logic
                    # Alert no longer exists, transition to RESOLVED
                    curr_alert.status = AlertStatus.RESOLVED
                    curr_alert.lastReceived = datetime.now(timezone.utc).isoformat()
                    alerts_to_notify.append(curr_alert)
                    self.logger.info(
                        "Alert resolved",
                        extra={
                            "fingerprint": fingerprint,
                            "last_received": curr_alert.lastReceived,
                        },
                    )

                # else: alert still exists, maintain FIRING state
                else:
                    curr_alert.status = AlertStatus.FIRING
                    alerts_to_notify.append(curr_alert)
                    self.logger.debug(
                        "Alert still firing", extra={"fingerprint": fingerprint}
                    )
            elif curr_alert.status == AlertStatus.PENDING.value:
                if not alert_still_exists:
                    # If PENDING alerts are not triggered, make them RESOLVED
                    # TODO: maybe INACTIVE? but we don't have this status yet
                    curr_alert.status = AlertStatus.RESOLVED
                    curr_alert.lastReceived = datetime.now(timezone.utc).isoformat()
                    alerts_to_notify.append(curr_alert)
                    self.logger.info(
                        "Pending alert resolved",
                        extra={
                            "fingerprint": fingerprint,
                            "last_received": curr_alert.lastReceived,
                        },
                    )
                else:
                    # Check if should transition to FIRING
                    if not hasattr(curr_alert, "activeAt"):
                        # This shouldn't happen but handle it gracefully
                        curr_alert.activeAt = curr_alert.lastReceived
                        self.logger.debug(
                            "Alert missing activeAt, using lastReceived",
                            extra={
                                "fingerprint": fingerprint,
                                "activeAt": curr_alert.lastReceived,
                            },
                        )

                    if isinstance(curr_alert.activeAt, str):
                        activeAt = datetime.fromisoformat(curr_alert.activeAt)
                    else:
                        activeAt = curr_alert.activeAt

                    # Convert duration string to timedelta
                    # Parse duration string like "1m", "5m", etc
                    try:
                        value = int(_for[:-1])
                        unit = _for[-1]
                    except ValueError:
                        raise ValueError(f"Invalid duration format: {_for}")
                    if unit == "m":
                        duration = timedelta(minutes=value)
                    elif unit == "h":
                        duration = timedelta(hours=value)
                    elif unit == "s":
                        duration = timedelta(seconds=value)
                    else:
                        raise ValueError(f"Invalid duration unit: {unit}")

                    curr_alert.lastReceived = datetime.now(timezone.utc).isoformat()
                    if now - activeAt >= duration:
                        curr_alert.status = AlertStatus.FIRING
                        self.logger.info(
                            "Alert transitioned to firing",
                            extra={
                                "fingerprint": fingerprint,
                                "duration_elapsed": str(now - activeAt),
                            },
                        )
                    # Keep pending, update lastReceived
                    else:
                        curr_alert.status = AlertStatus.PENDING
                        self.logger.debug(
                            "Alert still pending",
                            extra={
                                "fingerprint": fingerprint,
                                "time_remaining": str(duration - (now - activeAt)),
                            },
                        )
                    alerts_to_notify.append(curr_alert)
            # if alert is RESOLVED, add it to the list
            elif curr_alert.status == AlertStatus.RESOLVED.value:
                if not alert_still_exists:
                    # if alert is not in current state, add it to the list
                    alerts_to_notify.append(curr_alert)
                    self.logger.debug(
                        "Keeping resolved alert", extra={"fingerprint": fingerprint}
                    )
                else:
                    # if its resolved and with _for, then it first need to be pending
                    curr_alert.status = AlertStatus.PENDING
                    curr_alert.lastReceived = datetime.now(timezone.utc).isoformat()
                    alerts_to_notify.append(curr_alert)
                    self.logger.info(
                        "Resolved alert back to pending",
                        extra={
                            "fingerprint": fingerprint,
                            "last_received": curr_alert.lastReceived,
                        },
                    )

        # Handle new alerts not in current state
        for fingerprint, new_alert in state_alerts_map.items():
            if fingerprint not in curr_alerts_map:
                # Brand new alert - set to PENDING
                new_alert.status = AlertStatus.PENDING
                new_alert.activeAt = datetime.now(timezone.utc).isoformat()
                alerts_to_notify.append(new_alert)
                self.logger.info(
                    "New alert created",
                    extra={"fingerprint": fingerprint, "activeAt": new_alert.activeAt},
                )

        self.logger.info(
            "Completed state alert handling",
            extra={"alerts_to_notify": len(alerts_to_notify)},
        )
        return alerts_to_notify

    def _handle_stateless_alerts(
        self, stateless_alerts: list[AlertDto]
    ) -> list[AlertDto]:
        """
        Handle alerts without PENDING state - just FIRING or RESOLVED.
        Args:
            state_alerts: list of new alerts from current evaluation
        Returns:
            list of alerts that need state updates
        """
        self.logger.info(
            "Starting stateless alert handling",
            extra={"num_alerts": len(stateless_alerts)},
        )
        alerts_to_notify = []
        search_engine = SearchEngine(tenant_id=self.context_manager.tenant_id)
        curr_alerts = search_engine.search_alerts_by_cel(
            cel_query=f"providerId == '{self.context_manager.workflow_id}'"
        )
        self.logger.debug(
            "Found existing alerts", extra={"num_curr_alerts": len(curr_alerts)}
        )

        # Create lookup by fingerprint for efficient comparison
        curr_alerts_map = {alert.fingerprint: alert for alert in curr_alerts}
        state_alerts_map = {alert.fingerprint: alert for alert in stateless_alerts}
        self.logger.debug(
            "Created alert maps",
            extra={
                "curr_alerts_count": len(curr_alerts_map),
                "state_alerts_count": len(state_alerts_map),
            },
        )

        # Handle existing alerts
        for fingerprint, curr_alert in curr_alerts_map.items():
            alert_still_exists = fingerprint in state_alerts_map
            self.logger.debug(
                "Processing existing alert",
                extra={
                    "fingerprint": fingerprint,
                    "still_exists": alert_still_exists,
                    "current_status": curr_alert.status,
                },
            )

            if curr_alert.status == AlertStatus.FIRING.value:
                if not alert_still_exists:
                    # Alert no longer exists, transition to RESOLVED
                    curr_alert.status = AlertStatus.RESOLVED
                    curr_alert.lastReceived = datetime.now(timezone.utc).isoformat()
                    alerts_to_notify.append(curr_alert)
                    self.logger.info(
                        "Alert resolved",
                        extra={
                            "fingerprint": fingerprint,
                            "last_received": curr_alert.lastReceived,
                        },
                    )

        # Handle new alerts not in current state
        for fingerprint, new_alert in state_alerts_map.items():
            if fingerprint not in curr_alerts_map:
                # Brand new alert - set to FIRING immediately
                new_alert.status = AlertStatus.FIRING
                new_alert.lastReceived = datetime.now(timezone.utc).isoformat()
                alerts_to_notify.append(new_alert)
                self.logger.info(
                    "New alert firing",
                    extra={
                        "fingerprint": fingerprint,
                        "last_received": new_alert.lastReceived,
                    },
                )

        self.logger.info(
            "Completed stateless alert handling",
            extra={"alerts_to_notify": len(alerts_to_notify)},
        )
        return alerts_to_notify

    def _notify_alert(self, **kwargs):
        self.logger.debug("Starting _notify_alert", extra={"kwargs": kwargs})
        context = self.context_manager.get_full_context()
        alert_step = context.get("alert_step", None)
        self.logger.debug("Got alert step", extra={"alert_step": alert_step})

        # if alert_step is provided, get alert results
        if alert_step:
            alert_results = (
                context.get("steps", {}).get(alert_step, {}).get("results", {})
            )
            self.logger.debug(
                "Got alert results from alert_step",
                extra={"alert_results": alert_results},
            )
        # else, the last step results are the alert results
        else:
            # TODO: this is a temporary solution until we have a better way to get the alert results
            alert_results = context.get("steps", {}).get("this", {}).get("results", {})
            self.logger.debug(
                "Got alert results from 'this' step",
                extra={"alert_results": alert_results},
            )

        _if = kwargs.get("if", None)
        _for = kwargs.get("for", None)
        fingerprint_fields = kwargs.pop("fingerprint_fields", [])
        self.logger.debug(
            "Got condition parameters",
            extra={"if": _if, "for": _for, "fingerprint_fields": fingerprint_fields},
        )

        # if we need to check _if, handle the condition
        trigger_alerts = []
        if _if:
            self.logger.info(
                "Processing alerts with 'if' condition", extra={"condition": _if}
            )
            # if its multialert, handle each alert separately
            if isinstance(alert_results, list):
                self.logger.debug("Processing multiple alerts")
                for alert in alert_results:
                    # render
                    _if_rendered = self.io_handler.render(
                        _if, safe=True, additional_context=alert
                    )
                    self.logger.debug(
                        "Rendered if condition",
                        extra={"original": _if, "rendered": _if_rendered},
                    )
                    # evaluate
                    if not self._evaluate_if(_if, _if_rendered):
                        self.logger.debug(
                            "Alert did not meet condition", extra={"alert": alert}
                        )
                        continue
                    trigger_alerts.append(alert)
                    self.logger.debug("Alert met condition", extra={"alert": alert})
            else:
                pass
        # if no _if, trigger all alerts
        else:
            self.logger.info("No 'if' condition - triggering all alerts")
            trigger_alerts = alert_results

        # build the alert dtos
        alert_dtos = []
        self.logger.info(
            "Building alert DTOs", extra={"trigger_count": len(trigger_alerts)}
        )
        # render alert data
        for alert_results in trigger_alerts:
            alert_data = copy.copy(kwargs.get("alert", {}))
            # render alert data
            rendered_alert_data = self.io_handler.render_context(
                alert_data, additional_context=alert_results
            )
            self.logger.debug(
                "Rendered alert data",
                extra={"original": alert_data, "rendered": rendered_alert_data},
            )
            # render tenrary expressions
            rendered_alert_data = self._handle_tenrary_exressions(rendered_alert_data)
            alert_dto = self._build_alert(
                alert_results, fingerprint_fields, **rendered_alert_data
            )
            alert_dtos.append(alert_dto)
            self.logger.debug(
                "Built alert DTO", extra={"fingerprint": alert_dto.fingerprint}
            )

        # sanity check - if more than one alert has the same fingerprint it means something is wrong
        # this would happen if the fingerprint fields are not unique
        fingerprints = {}
        for alert in alert_dtos:
            if fingerprints.get(alert.fingerprint):
                self.logger.warning(
                    "Alert with the same fingerprint already exists - it means your fingerprint labels are not unique",
                    extra={"alert": alert, "fingerprint": alert.fingerprint},
                )
            fingerprints[alert.fingerprint] = True

        # if _for is provided, handle state alerts
        if _for:
            self.logger.info(
                "Handling state alerts with 'for' condition", extra={"for": _for}
            )
            # handle alerts with state
            alerts = self._handle_state_alerts(_for, alert_dtos)
        # else, handle all alerts
        else:
            self.logger.info("Handling stateless alerts")
            alerts = self._handle_stateless_alerts(alert_dtos)

        # handle all alerts
        self.logger.info(
            "Processing final alerts", extra={"number_of_alerts": len(alerts)}
        )
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
        self.logger.info(
            "Alerts processed successfully", extra={"alert_count": len(alerts)}
        )
        return alerts

    def _delete_workflows(self, except_workflow_id=None):
        self.logger.info("Deleting all workflows")
        workflow_store = WorkflowStore()
        workflows = workflow_store.get_all_workflows(self.context_manager.tenant_id)
        for workflow in workflows:
            if not (except_workflow_id and workflow.id == except_workflow_id):
                self.logger.info(f"Deleting workflow {workflow.id}")
                try:
                    workflow_store.delete_workflow(
                        self.context_manager.tenant_id, workflow.id
                    )
                    self.logger.info(f"Deleted workflow {workflow.id}")
                except Exception as e:
                    self.logger.exception(
                        f"Failed to delete workflow {workflow.id}: {e}"
                    )
                    raise ProviderException(
                        f"Failed to delete workflow {workflow.id}: {e}"
                    )
            else:
                self.logger.info(
                    f"Not deleting workflow {workflow.id} as it's current workflow"
                )
        self.logger.info("Deleted all workflows")

    def _notify(self, **kwargs):
        if "workflow_full_sync" in kwargs or "delete_all_other_workflows" in kwargs:
            # We need DB id, not user id for the workflow, so getting it from the wf execution.
            workflow_store = WorkflowStore()
            workflow_execution = workflow_store.get_workflow_execution(
                self.context_manager.tenant_id,
                self.context_manager.workflow_execution_id,
            )
            workflow_db_id = workflow_execution.workflow_id
            self._delete_workflows(except_workflow_id=workflow_db_id)
        elif "workflow_to_update_yaml" in kwargs:
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

                workflow = workflowstore.create_workflow(
                    tenant_id=self.context_manager.tenant_id,
                    created_by=f"workflow id: {self.context_manager.workflow_id}",
                    workflow=workflow_to_update_yaml,
                )
                self.logger.info(
                    "Workflow created successfully",
                    extra={
                        "tenant_id": self.context_manager.tenant_id,
                        "workflow": workflow,
                    },
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
            alerts = self._notify_alert(**kwargs)
            self.logger.info("Alerts notified")
            return alerts

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

    def _evaluate_if(self, if_conf, if_conf_rendered):
        # Evaluate the condition string
        from asteval import Interpreter

        aeval = Interpreter()
        evaluated_if_met = aeval(if_conf_rendered)
        # tb: when Shahar and I debugged, conclusion was:
        if isinstance(evaluated_if_met, str):
            evaluated_if_met = aeval(evaluated_if_met)
        # if the evaluation failed, raise an exception
        if aeval.error_msg:
            self.logger.error(
                f"Failed to evaluate if condition, you probably used a variable that doesn't exist. Condition: {if_conf}, Rendered: {if_conf_rendered}, Error: {aeval.error_msg}",
                extra={
                    "condition": if_conf,
                    "rendered": if_conf_rendered,
                },
            )
            return False
        return evaluated_if_met

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
