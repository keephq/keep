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

    def _query(
        self,
        filters=None,
        version=1,
        distinct=True,
        time_delta=1,
        timerange=None,
        filter=None,
        limit: int | None = None,
        **kwargs,
    ):
        """
        Query Keep for alerts.
        Args:
            filters: filters to query Keep (only for version 1)
            version: version of Keep API
            distinct: if True, return only distinct alerts
            time_delta: time delta in days to query Keep
            timerange: timerange dict to calculate time delta
            filter: filter to query Keep (only for version 2)
            limit: limit number of results (only for version 2)
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
        if timerange:
            time_delta = int(
                self._calculate_time_delta(
                    timerange=timerange, default_time_range=time_delta
                )
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
            if not filter:
                raise ValueError("Filter is required for version 2")
            try:
                alerts = search_engine.search_alerts_by_cel(
                    cel_query=filter, limit=limit or 100, timeframe=float(time_delta)
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
        )
        # to avoid multiple key word argument, add and key,val on alert data only if it doesn't exists:
        if isinstance(alert_data, dict):
            for key, val in alert_data.items():
                if not hasattr(alert, key):
                    setattr(alert, key, val)

        # if fingerprint was explicitly mentioned in the workflow:
        if "fingerprint" in alert_data or "fingerprint" in kwargs:
            return alert

        # else, if fingerprint_fields are not provided, use labels
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
        self, stateless_alerts: list[AlertDto], read_only=False
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
        if not read_only:
            search_engine = SearchEngine(tenant_id=self.context_manager.tenant_id)
            curr_alerts = search_engine.search_alerts_by_cel(
                cel_query=f"providerId == '{self.context_manager.workflow_id}'"
            )
            self.logger.debug(
                "Found existing alerts", extra={"num_curr_alerts": len(curr_alerts)}
            )
        else:
            curr_alerts = []

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

    def _notify_alert(
        self,
        alert: dict | None = None,
        if_condition: str | None = None,
        for_duration: str | None = None,
        fingerprint_fields: list | None = None,
        override_source_with: str | None = None,
        read_only: bool = False,
        fingerprint: str | None = None,
        **kwargs,
    ) -> list:
        """
        Notify alerts with the given parameters
        Args:
            alert: alert data to create
            if_condition: condition to evaluate for alert creation
            for_duration: duration for state alerts
            fingerprint_fields: fields to use for alert fingerprinting
            override_source_with: override alert source
            read_only: if True, don't modify existing alerts
            fingerprint: alert fingerprint
        Returns:
            list of created/updated alerts
        """
        self.logger.debug("Starting _notify_alert")
        context = self.context_manager.get_full_context()

        alert_results = context.get("foreach", {}).get("items", None)

        # if foreach_context is provided, get alert results
        if alert_results:
            self.logger.debug(
                "Got alert results from foreach context",
                extra={"alert_results": alert_results},
            )
        # else, the last step results are the alert results
        else:
            # TODO: this is a temporary solution until we have a better way to get the alert results
            alert_results = context.get("steps", {}).get("this", {}).get("results", {})
            self.logger.info(
                "Got alert results from 'this' step",
                extra={"alert_results": alert_results},
            )
            # alert_results must be a list
            if not isinstance(alert_results, list):
                self.logger.warning(
                    "Alert results must be a list, but got a non-list type",
                    extra={"alert_results": alert_results},
                )
                alert_results = None

        # create_alert_in_keep.yml for example
        if not alert_results:
            self.logger.info("No alert results found")
            if alert:
                self.logger.info("Creating alert from 'alert' parameter")
                alert_results = [alert]

        self.logger.debug(
            "Got condition parameters",
            extra={
                "if": if_condition,
                "for": for_duration,
                "fingerprint_fields": fingerprint_fields,
            },
        )

        # if we need to check if_condition, handle the condition
        trigger_alerts = []
        if if_condition:
            self.logger.info(
                "Processing alerts with 'if' condition",
                extra={"condition": if_condition},
            )
            # if its multialert, handle each alert separately
            if isinstance(alert_results, list):
                self.logger.debug("Processing multiple alerts")
                for alert_result in alert_results:
                    # render
                    if_rendered = self.io_handler.render(
                        if_condition, safe=True, additional_context=alert_result
                    )
                    self.logger.debug(
                        "Rendered if condition",
                        extra={"original": if_condition, "rendered": if_rendered},
                    )
                    # evaluate
                    if not self._evaluate_if(if_condition, if_rendered):
                        self.logger.debug(
                            "Alert did not meet condition",
                            extra={"alert": alert_result},
                        )
                        continue
                    trigger_alerts.append(alert_result)
                    self.logger.debug(
                        "Alert met condition", extra={"alert": alert_result}
                    )
            else:
                pass
        # if no if_condition, trigger all alerts
        else:
            self.logger.info("No 'if' condition - triggering all alerts")
            trigger_alerts = alert_results

        # build the alert dtos
        alert_dtos = []
        self.logger.info(
            "Building alert DTOs", extra={"trigger_count": len(trigger_alerts)}
        )
        # render alert data
        for alert_result in trigger_alerts:
            alert_data = copy.deepcopy(alert or {})
            # render alert data
            if isinstance(alert_result, dict):
                rendered_alert_data = self.io_handler.render_context(
                    alert_data, additional_context=alert_result
                )
            else:
                self.logger.warning(
                    "Alert data is not a dict, skipping rendering",
                    extra={"alert_data": alert_data},
                )
                rendered_alert_data = alert_data
            self.logger.debug(
                "Rendered alert data",
                extra={"original": alert_data, "rendered": rendered_alert_data},
            )
            # render tenrary expressions
            rendered_alert_data = self._handle_ternary_expressions(rendered_alert_data)
            alert_dto = self._build_alert(
                alert_result, fingerprint_fields or [], **rendered_alert_data
            )
            if override_source_with:
                alert_dto.source = [override_source_with]

            alert_dtos.append(alert_dto)
            self.logger.debug(
                "Built alert DTO", extra={"fingerprint": alert_dto.fingerprint}
            )

        # sanity check - if more than one alert has the same fingerprint it means something is wrong
        # this would happen if the fingerprint fields are not unique
        fingerprints = {}
        for alert_dto in alert_dtos:
            if fingerprints.get(alert_dto.fingerprint):
                self.logger.warning(
                    "Alert with the same fingerprint already exists - it means your fingerprint labels are not unique",
                    extra={"alert": alert_dto, "fingerprint": alert_dto.fingerprint},
                )
            fingerprints[alert_dto.fingerprint] = True

        # if for_duration is provided, handle state alerts
        if for_duration:
            self.logger.info(
                "Handling state alerts with 'for' condition",
                extra={"for": for_duration},
            )
            # handle alerts with state
            alerts = self._handle_state_alerts(for_duration, alert_dtos)
        # else, handle all alerts
        else:
            self.logger.info("Handling stateless alerts")
            alerts = self._handle_stateless_alerts(alert_dtos, read_only=read_only)

        # handle all alerts
        self.logger.info(
            "Processing final alerts", extra={"number_of_alerts": len(alerts)}
        )
        process_event(
            ctx={},
            tenant_id=self.context_manager.tenant_id,
            provider_type="keep",
            provider_id=self.context_manager.workflow_id,
            # so we can track the alerts that are created by this workflow
            fingerprint=fingerprint,
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

    def _notify(
        self,
        delete_all_other_workflows: bool = False,
        workflow_full_sync: bool = False,
        workflow_to_update_yaml: str | None = None,
        alert: dict | None = None,
        fingerprint_fields: list | None = None,
        override_source_with: str | None = None,
        read_only: bool = False,
        fingerprint: str | None = None,
        if_: str | None = None,
        for_: str | None = None,
        **kwargs,
    ):
        """
        Notify alerts or update workflow
        Args:
            delete_all_other_workflows: if True, delete all other workflows
            workflow_full_sync: if True, sync all workflows
            workflow_to_update_yaml: workflow yaml to update
            alert: alert data to create
            if: condition to evaluate for alert creation
            for: duration for state alerts
            fingerprint_fields: fields to use for alert fingerprinting
            override_source_with: override alert source
            read_only: if True, don't modify existing alerts
            fingerprint: alert fingerprint
        """
        # TODO: refactor this to be two separate ProviderMethods, when wf engine will support calling provider methods
        is_workflow_action = (
            workflow_full_sync or delete_all_other_workflows or workflow_to_update_yaml
        )

        if workflow_full_sync or delete_all_other_workflows:
            # We need DB id, not user id for the workflow, so getting it from the wf execution.
            workflow_store = WorkflowStore()
            workflow_execution = workflow_store.get_workflow_execution(
                self.context_manager.tenant_id,
                self.context_manager.workflow_execution_id,
            )
            workflow_db_id = workflow_execution.workflow_id
            if not workflow_execution.workflow_id == "test":
                self._delete_workflows(except_workflow_id=workflow_db_id)
            else:
                self.logger.info(
                    "Not deleting workflow as it's a test run",
                )
        if workflow_to_update_yaml:
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
                    force_update=False,
                    lookup_by_name=True,
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
        elif not is_workflow_action:
            self.logger.info("Notifying Alerts")
            # for backward compatibility
            if_condition = if_ or kwargs.get("if", None)
            for_duration = for_ or kwargs.get("for", None)
            alerts = self._notify_alert(
                alert=alert,
                if_condition=if_condition,
                for_duration=for_duration,
                fingerprint_fields=fingerprint_fields,
                override_source_with=override_source_with,
                read_only=read_only,
                fingerprint=fingerprint,
            )
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

    def _handle_ternary_expressions(self, rendered_providers_parameters):
        """
        Handle ternary expressions in rendered parameters without using js2py.

        Parses and evaluates expressions like:
        "x > 0.9 ? 'critical' : x > 0.7 ? 'warning' : 'info'"

        Args:
            rendered_providers_parameters (dict): Dictionary of rendered parameters

        Returns:
            dict: Updated parameters with evaluated ternary expressions
        """
        from asteval import Interpreter

        def evaluate_ternary(expression, aeval):
            """Recursively evaluate a ternary expression using Python."""
            # Find the position of the first question mark that's not inside quotes
            in_quotes = False
            quote_type = None
            question_pos = -1

            for i, char in enumerate(expression):
                if char in ['"', "'"]:
                    if not in_quotes:
                        in_quotes = True
                        quote_type = char
                    elif char == quote_type:
                        in_quotes = False

                if char == "?" and not in_quotes:
                    question_pos = i
                    break

            if question_pos == -1:
                # No ternary operator found, evaluate as regular expression
                return aeval(expression)

            # Find the matching colon
            colon_pos = -1
            nested_level = 0

            for i in range(question_pos + 1, len(expression)):
                char = expression[i]

                if char in ['"', "'"]:
                    if not in_quotes:
                        in_quotes = True
                        quote_type = char
                    elif char == quote_type:
                        in_quotes = False

                if not in_quotes:
                    if char == "?":
                        nested_level += 1
                    elif char == ":":
                        if nested_level == 0:
                            colon_pos = i
                            break
                        else:
                            nested_level -= 1

            if colon_pos == -1:
                # Malformed ternary expression
                self.logger.warning(
                    f"Malformed ternary expression: {expression}",
                    extra={"expression": expression},
                )
                return expression

            # Split into condition, true_expr, and false_expr
            condition = expression[:question_pos].strip()
            true_expr = expression[question_pos + 1 : colon_pos].strip()
            false_expr = expression[colon_pos + 1 :].strip()

            # Evaluate the condition
            condition_result = aeval(condition)

            # Evaluate the appropriate branch (true or false)
            if condition_result:
                return evaluate_ternary(true_expr, aeval)
            else:
                return evaluate_ternary(false_expr, aeval)

        # Process each parameter value
        for key, value in rendered_providers_parameters.items():
            if not isinstance(value, str):
                continue

            # Check if the value might contain a ternary expression
            if "?" in value and ":" in value:
                try:
                    aeval = Interpreter()
                    result = evaluate_ternary(value, aeval)

                    # If there were errors during evaluation, log them but keep the original value
                    if aeval.error_msg:
                        self.logger.warning(
                            f"Error evaluating ternary expression: {value}. Error: {aeval.error_msg}",
                            extra={"value": value, "error": aeval.error_msg},
                        )
                    else:
                        rendered_providers_parameters[key] = result
                except Exception as e:
                    self.logger.warning(
                        f"Failed to evaluate potential ternary expression: {value}. Error: {str(e)}",
                        extra={"value": value, "error": str(e)},
                    )

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
