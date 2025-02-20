"""
Datadog Provider is a class that allows to ingest/digest data from Datadog.
"""

import dataclasses
import datetime
import json
import logging
import os
import re
import time
from collections import defaultdict
from dataclasses import asdict
from typing import List, Literal, Optional

import pydantic
import requests
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.api_client import Endpoint
from datadog_api_client.exceptions import (
    ApiException,
    ForbiddenException,
    NotFoundException,
)
from datadog_api_client.v1.api.events_api import EventsApi
from datadog_api_client.v1.api.logs_api import LogsApi
from datadog_api_client.v1.api.metrics_api import MetricsApi
from datadog_api_client.v1.api.monitors_api import MonitorsApi
from datadog_api_client.v1.api.webhooks_integration_api import WebhooksIntegrationApi
from datadog_api_client.v1.model.monitor import Monitor
from datadog_api_client.v1.model.monitor_options import MonitorOptions
from datadog_api_client.v1.model.monitor_thresholds import MonitorThresholds
from datadog_api_client.v1.model.monitor_type import MonitorType
from datadog_api_client.v2.api.incidents_api import IncidentsApi
from datadog_api_client.v2.api.service_definition_api import ServiceDefinitionApi
from datadog_api_client.v2.api.users_api import UsersApi, UsersResponse
from pydantic import Field

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.topology import TopologyServiceInDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseTopologyProvider, ProviderHealthMixin
from keep.providers.base.provider_exceptions import GetAlertException
from keep.providers.datadog_provider.datadog_alert_format_description import (
    DatadogAlertFormatDescription,
)
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod
from keep.providers.providers_factory import ProvidersFactory
from keep.validation.fields import HttpsUrl

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class DatadogAlertDetails:
    metric_graph_url: Optional[str] = Field(default=None)
    metric_query: Optional[str] = Field(default=None)
    trigger_time: Optional[str] = Field(default=None)
    monitor_status_url: Optional[str] = Field(default=None)
    edit_monitor_url: Optional[str] = Field(default=None)
    related_logs_url: Optional[str] = Field(default=None)
    alert_message: Optional[str] = Field(default=None)
    mentioned_users: List[str] = Field(default_factory=list)


# Best effort to extract relevant details from the Datadog alert webhook payload body
def extract_alert_details(body: str) -> DatadogAlertDetails:
    """
    Extracts relevant details from a Datadog alert webhook payload body.

    Args:
        body: The message body from the Datadog webhook payload

    Returns:
        DatadogAlertDetails object containing extracted information
    """
    if not body:
        return DatadogAlertDetails()

    # Remove the %%% markers if present
    body = body.strip("%%%\n")

    details = DatadogAlertDetails()
    details.mentioned_users = []

    # Extract metric graph URL
    metric_graph_match = re.search(r"\[!\[Metric Graph\]\((.*?)\)\]", body)
    if metric_graph_match:
        details.metric_graph_url = metric_graph_match.group(1)

    # Extract trigger time
    trigger_time_match = re.search(r"The monitor was last triggered at (.*?)\.", body)
    if trigger_time_match:
        details.trigger_time = trigger_time_match.group(1)

    # Extract URLs from the footer
    monitor_status_match = re.search(r"\[Monitor Status\]\((.*?)\)", body)
    if monitor_status_match:
        details.monitor_status_url = monitor_status_match.group(1)

    edit_monitor_match = re.search(r"\[Edit Monitor\]\((.*?)\)", body)
    if edit_monitor_match:
        details.edit_monitor_url = edit_monitor_match.group(1)

    related_logs_match = re.search(r"\[Related Logs\]\((.*?)\)", body)
    if related_logs_match:
        details.related_logs_url = related_logs_match.group(1)

    # Extract mentioned users (starting with @)
    details.mentioned_users = re.findall(r"@([^\s]+)", body)

    # Extract the main alert message (first line of the message)
    lines = body.split("\n")
    for line in lines:
        if line and not line.startswith("%%%") and not line.startswith("@"):
            details.alert_message = line.strip()
            break

    return details


@pydantic.dataclasses.dataclass
class DatadogProviderAuthConfig:
    """
    Datadog authentication configuration.
    """

    KEEP_DATADOG_WEBHOOK_INTEGRATION_NAME = "keep-datadog-webhook-integration"

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Datadog Api Key",
            "hint": "https://docs.datadoghq.com/account_management/api-app-keys/#api-keys",
            "sensitive": True,
        },
        default="",
    )
    app_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Datadog App Key",
            "hint": "https://docs.datadoghq.com/account_management/api-app-keys/#application-keys",
            "sensitive": True,
        },
        default="",
    )
    domain: HttpsUrl = dataclasses.field(
        metadata={
            "required": False,
            "description": "Datadog API domain",
            "sensitive": False,
            "hint": "https://api.datadoghq.com",
            "validation": "https_url",
        },
        default="https://api.datadoghq.com",
    )
    environment: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Topology environment name",
            "sensitive": False,
            "hint": "Defaults to *",
        },
        default="*",
    )
    oauth_token: dict = dataclasses.field(
        metadata={
            "description": "For OAuth flow",
            "required": False,
            "sensitive": True,
            "hidden": True,
        },
        default_factory=dict,
    )


class DatadogProvider(BaseTopologyProvider, ProviderHealthMixin):
    """Pull/push alerts from Datadog."""

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "Datadog"
    OAUTH2_URL = os.environ.get("DATADOG_OAUTH2_URL")
    DATADOG_CLIENT_ID = os.environ.get("DATADOG_CLIENT_ID")
    DATADOG_CLIENT_SECRET = os.environ.get("DATADOG_CLIENT_SECRET")

    PROVIDER_SCOPES = [
        ProviderScope(
            name="events_read",
            description="Read events data.",
            mandatory=True,
            alias="Events Data Read",
        ),
        ProviderScope(
            name="monitors_read",
            description="Read monitors",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://docs.datadoghq.com/account_management/rbac/permissions/#monitors",
            alias="Monitors Read",
        ),
        ProviderScope(
            name="monitors_write",
            description="Write monitors",
            mandatory=False,
            mandatory_for_webhook=True,
            documentation_url="https://docs.datadoghq.com/account_management/rbac/permissions/#monitors",
            alias="Monitors Write",
        ),
        ProviderScope(
            name="create_webhooks",
            description="Create webhooks integrations",
            mandatory=False,
            mandatory_for_webhook=True,
            alias="Integrations Manage",
        ),
        ProviderScope(
            name="metrics_read",
            description="View custom metrics.",
            mandatory=False,
        ),
        ProviderScope(
            name="logs_read",
            description="Read log data.",
            mandatory=False,
            alias="Logs Read Data",
        ),
        ProviderScope(
            name="apm_read",
            description="Read APM data for Topology creation.",
            mandatory=False,
            alias="Read APM Data",
        ),
        ProviderScope(
            name="apm_service_catalog_read",
            description="Read APM service catalog for Topology creation.",
            mandatory=False,
            alias="Read APM service catalog Data",
        ),
    ]
    PROVIDER_METHODS = [
        ProviderMethod(
            name="Mute a Monitor",
            func_name="mute_monitor",
            scopes=["monitors_write"],
            description="Mute a monitor",
            type="action",
        ),
        ProviderMethod(
            name="Unmute a Monitor",
            func_name="unmute_monitor",
            scopes=["monitors_write"],
            description="Unmute a monitor",
            type="action",
        ),
        ProviderMethod(
            name="Get Monitor Events",
            func_name="get_monitor_events",
            scopes=["events_read"],
            description="Get all events related to this monitor",
            type="view",
        ),
        ProviderMethod(
            name="Get a Trace",
            func_name="get_trace",
            scopes=["apm_read"],
            description="Get trace by id",
            type="view",
        ),
        ProviderMethod(
            name="Create Incident",
            func_name="create_incident",
            scopes=["incidents_write"],
            description="Create an incident",
            type="action",
        ),
        ProviderMethod(
            name="Resolve Incident",
            func_name="resolve_incident",
            scopes=["incidents_write"],
            description="resolve an active incident",
            type="action",
        ),
        ProviderMethod(
            name="Add Incident Timeline Note",
            func_name="add_incident_timeline_note",
            scopes=["incidents_write"],
            description="Add a note to an incident timeline",
            type="action",
        ),
    ]
    FINGERPRINT_FIELDS = ["groups", "monitor_id"]
    WEBHOOK_PAYLOAD = json.dumps(
        {
            "body": "$EVENT_MSG",
            "last_updated": "$LAST_UPDATED",
            "event_type": "$EVENT_TYPE",
            "title": "$EVENT_TITLE",
            "severity": "$ALERT_PRIORITY",
            "alert_type": "$ALERT_TYPE",
            "alert_query": "$ALERT_QUERY",
            "alert_transition": "$ALERT_TRANSITION",
            "date": "$DATE",
            "scopes": "$ALERT_SCOPE",
            "org": {"id": "$ORG_ID", "name": "$ORG_NAME"},
            "url": "$LINK",
            "tags": "$TAGS",
            "id": "$ID",
            "monitor_id": "$ALERT_ID",
        }
    )

    SEVERITIES_MAP = {
        "P4": AlertSeverity.INFO,
        "P3": AlertSeverity.WARNING,
        "P2": AlertSeverity.HIGH,
        "P1": AlertSeverity.CRITICAL,
    }

    STATUS_MAP = {
        "Triggered": AlertStatus.FIRING,
        "Recovered": AlertStatus.RESOLVED,
        "Muted": AlertStatus.SUPPRESSED,
    }

    def convert_to_seconds(s):
        seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        return int(s[:-1]) * seconds_per_unit[s[-1]]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.configuration = Configuration(request_timeout=5)
        if self.authentication_config.api_key and self.authentication_config.app_key:
            self.configuration.api_key["apiKeyAuth"] = (
                self.authentication_config.api_key
            )
            self.configuration.api_key["appKeyAuth"] = (
                self.authentication_config.app_key
            )
            domain = self.authentication_config.domain or "https://api.datadoghq.com"
            self.configuration.host = domain
        elif self.authentication_config.oauth_token:
            domain = self.authentication_config.oauth_token.get(
                "domain", "datadoghq.com"
            )
            response = requests.post(
                f"https://api.{domain}/oauth2/v1/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": DatadogProvider.DATADOG_CLIENT_ID,
                    "client_secret": DatadogProvider.DATADOG_CLIENT_SECRET,
                    "redirect_uri": self.authentication_config.oauth_token.get(
                        "redirect_uri"
                    ),
                    "code_verifier": self.authentication_config.oauth_token.get(
                        "verifier"
                    ),
                    "code": self.authentication_config.oauth_token.get("code"),
                    "refresh_token": self.authentication_config.oauth_token.get(
                        "refresh_token"
                    ),
                },
            )
            if not response.ok:
                raise Exception("Could not refresh token, need to re-authenticate")
            response_json = response.json()
            self.configuration.access_token = response_json.get("access_token")
            self.configuration.host = f"https://api.{domain}"
            # update the oauth_token refresh_token for next run
            self.config.authentication["oauth_token"]["refresh_token"] = response_json[
                "refresh_token"
            ]
        else:
            raise Exception("No authentication provided")
        # to be exposed
        self.to = None
        self._from = None

    @staticmethod
    def oauth2_logic(**payload) -> dict:
        """
        Logic for handling oauth2 callback.

        Returns:
            dict: access token to Datadog.
        """
        domain = payload.pop("domain", "datadoghq.com")
        verifier = payload.pop("verifier", None)
        if not verifier:
            raise Exception("No verifier provided")
        code = payload.pop("code", None)
        if not code:
            raise Exception("No code provided")

        token = requests.post(
            f"https://api.{domain}/oauth2/v1/token",
            data={
                "grant_type": "authorization_code",
                "client_id": payload["client_id"],
                "client_secret": DatadogProvider.DATADOG_CLIENT_SECRET,
                "redirect_uri": payload["redirect_uri"],
                "code_verifier": verifier,
                "code": code,
            },
        ).json()

        access_token = token.get("access_token")
        if not access_token:
            raise Exception("No access token provided")

        return {
            "oauth_token": {
                **token,
                "verifier": verifier,
                "code": code,
                "redirect_uri": payload["redirect_uri"],
                "domain": domain,
            }
        }

    def get_users(self) -> UsersResponse:
        with ApiClient(self.configuration) as api_client:
            api = UsersApi(api_client)
            return api.list_users()

    def add_incident_timeline_note(self, incident_id: str, note: str):
        headers = {}
        if self.authentication_config.api_key and self.authentication_config.app_key:
            headers["DD-API-KEY"] = self.authentication_config.api_key
            headers["DD-APPLICATION-KEY"] = self.authentication_config.app_key
        else:
            headers["Authorization"] = (
                f"Bearer {self.authentication_config.oauth_token.get('access_token')}"
            )
        endpoint = f"api/v2/incidents/{incident_id}/timeline"
        url = f"{self.configuration.host}/{endpoint}"
        response = requests.post(
            url,
            headers=headers,
            json={
                "data": {
                    "attributes": {
                        "cell_type": "markdown",
                        "content": {"content": note},
                    },
                    "type": "incident_timeline_cells",
                }
            },
        )
        if response.ok:
            return response.json()
        else:
            raise Exception(
                f"Failed to add incident timeline note: {response.status_code} {response.text}"
            )

    def resolve_incident(self, incident_id: str):
        self.configuration.unstable_operations["update_incident"] = True
        with ApiClient(self.configuration) as api_client:
            api = IncidentsApi(api_client)
            response = api.update_incident(
                incident_id,
                {
                    "data": {
                        "id": incident_id,
                        "type": "incidents",
                        "attributes": {"fields": {"state": {"value": "resolved"}}},
                    }
                },
            )
            return response.data.to_dict()

    def create_incident(
        self,
        incident_name: str,
        incident_message: str,
        commander_user: str,
        customer_impacted: bool = False,
        important: bool = True,
        severity: Literal["SEV-1", "SEV-2", "SEV-3", "SEV-4", "UNKNOWN"] = "SEV-4",
        fields: dict = {"state": {"value": "active"}},
    ):
        users = self.get_users()
        commander_user_obj = next(
            (
                user
                for user in users.data
                if user.attributes.name == commander_user
                or user.attributes.handle == commander_user
            ),
            users.data[0],  # select the first user as the commander if not found
        )

        fields["severity"] = {"value": severity}
        body = {
            "data": {
                "type": "incidents",
                "attributes": {
                    "title": incident_name,
                    "fields": fields,
                    "initial_cells": [
                        {
                            "cell_type": "markdown",
                            "content": {
                                "content": incident_message,
                                "important": important,
                            },
                        }
                    ],
                    "customer_impacted": customer_impacted,
                },
                "relationships": {
                    "commander_user": {
                        "data": {
                            "type": "users",
                            "id": commander_user_obj.id,
                        },
                    },
                },
            }
        }
        self.configuration.unstable_operations["create_incident"] = True
        with ApiClient(self.configuration) as api_client:
            api = IncidentsApi(api_client)
            result = api.create_incident(body)
            host_app = self.configuration.host.replace("api", "app")
            return {
                "id": result.data.id,
                "url": f"{host_app}/incidents/{result.data.attributes.public_id}",
                "title": incident_name,
                "incident": result.data.attributes.to_dict(),
            }

    def mute_monitor(
        self,
        monitor_id: str,
        groups: list = [],
        end: datetime.datetime = datetime.datetime.now() + datetime.timedelta(days=1),
    ):
        self.logger.info("Muting monitor", extra={"monitor_id": monitor_id, "end": end})
        if isinstance(end, str):
            end = datetime.datetime.fromisoformat(end)

        groups = ",".join(groups)
        if groups == "*":
            groups = ""

        with ApiClient(self.configuration) as api_client:
            endpoint = Endpoint(
                settings={
                    "auth": ["apiKeyAuth", "appKeyAuth", "AuthZ"],
                    "endpoint_path": "/api/v1/monitor/{monitor_id}/mute",
                    "response_type": (dict,),
                    "operation_id": "mute_monitor",
                    "http_method": "POST",
                    "version": "v1",
                },
                params_map={
                    "monitor_id": {
                        "required": True,
                        "openapi_types": (int,),
                        "attribute": "monitor_id",
                        "location": "path",
                    },
                    "scope": {
                        "openapi_types": (str,),
                        "attribute": "scope",
                        "location": "query",
                    },
                    "end": {
                        "openapi_types": (int,),
                        "attribute": "end",
                        "location": "query",
                    },
                },
                headers_map={
                    "accept": ["application/json"],
                    "content_type": ["application/json"],
                },
                api_client=api_client,
            )
            endpoint.call_with_http_info(
                monitor_id=int(monitor_id),
                end=int(end.timestamp()),
                scope=groups,
            )
        self.logger.info("Monitor muted", extra={"monitor_id": monitor_id})

    def unmute_monitor(
        self,
        monitor_id: str,
        groups: list = [],
    ):
        self.logger.info("Unmuting monitor", extra={"monitor_id": monitor_id})

        groups = ",".join(groups)

        with ApiClient(self.configuration) as api_client:
            endpoint = Endpoint(
                settings={
                    "auth": ["apiKeyAuth", "appKeyAuth", "AuthZ"],
                    "endpoint_path": "/api/v1/monitor/{monitor_id}/unmute",
                    "response_type": (dict,),
                    "operation_id": "mute_monitor",
                    "http_method": "POST",
                    "version": "v1",
                },
                params_map={
                    "monitor_id": {
                        "required": True,
                        "openapi_types": (int,),
                        "attribute": "monitor_id",
                        "location": "path",
                    },
                    "scope": {
                        "openapi_types": (str,),
                        "attribute": "scope",
                        "location": "query",
                    },
                },
                headers_map={
                    "accept": ["application/json"],
                    "content_type": ["application/json"],
                },
                api_client=api_client,
            )
            endpoint.call_with_http_info(
                monitor_id=int(monitor_id),
                scope=groups,
            )
        self.logger.info("Monitor unmuted", extra={"monitor_id": monitor_id})

    # @tb: we need to standardize the way we get traces
    # e.g., create a trace model and use it across providers
    def get_trace(self, trace_id: str):
        self.logger.info("Getting trace", extra={"trace_id": trace_id})
        headers = {}
        if self.authentication_config.api_key and self.authentication_config.app_key:
            headers["DD-API-KEY"] = self.authentication_config.api_key
            headers["DD-APPLICATION-KEY"] = self.authentication_config.app_key
        else:
            headers["Authorization"] = (
                f"Bearer {self.authentication_config.oauth_token.get('access_token')}"
            )
        endpoint = f"api/unstable/ui/trace/{trace_id}"
        url = f"{self.configuration.host}/{endpoint}"
        response = requests.get(url, headers=headers)
        if response.ok:
            self.logger.info("Trace retrieved", extra={"trace_id": trace_id})
            trace_data = response.json()
            return trace_data.get("data", {}).get("attributes", {}).get("trace", {})
        else:
            self.logger.error(
                "Failed to get trace",
                extra={
                    "trace_id": trace_id,
                    "status_code": response.status_code,
                    "response": response.text,
                },
            )
            raise Exception(
                f"Failed to get traces: {response.status_code} {response.text}"
            )

    def search_traces(self, queries: list[str], **kwargs):
        if not queries:
            raise Exception("No services provided")

        self.logger.info("Searching traces", extra={"queries": queries})

        headers = {}
        if self.authentication_config.api_key and self.authentication_config.app_key:
            headers["DD-API-KEY"] = self.authentication_config.api_key
            headers["DD-APPLICATION-KEY"] = self.authentication_config.app_key
        else:
            headers["Authorization"] = (
                f"Bearer {self.authentication_config.oauth_token.get('access_token')}"
            )

        alltraces = defaultdict(list)
        for query in queries:
            self.logger.info("Searching traces", extra={"query": query})
            try:
                traces = self._search_traces(query, headers)
                traces_ids = [
                    t.get("attributes").get("trace_id") for t in traces["data"]
                ]
                alltraces[query] = traces_ids
            except Exception:
                self.logger.exception(
                    "Failed to get traces",
                    extra={
                        "query": query,
                    },
                )
                continue

        return alltraces

    def _search_traces(self, query: str, headers: dict):
        span_query = self._translate_metric_query_to_span_query(query)
        data = {
            "data": {
                "attributes": {
                    "filter": {
                        "from": "now-1800s",
                        "to": "now",
                        "query": span_query,
                    },
                    "options": {"timezone": "UTC"},
                    "page": {"limit": 5},
                    "sort": "-timestamp",
                },
                "type": "search_request",
            }
        }
        endpoint = "/api/v2/spans/events/search"
        url = f"{self.configuration.host}/{endpoint}"
        response = requests.post(url, headers=headers, json=data)
        if response.ok:
            self.logger.info("Traces retrieved", extra={"query": query})
            traces = response.json()
            return traces
        else:
            self.logger.error(
                "Failed to get traces",
                extra={
                    "query": query,
                    "status_code": response.status_code,
                    "response": response.text,
                },
            )
            raise Exception(
                f"Failed to get traces: {response.status_code} {response.text}"
            )

    def get_monitor_events(self, monitor_id: str):
        self.logger.info("Getting monitor events", extra={"monitor_id": monitor_id})
        with ApiClient(self.configuration) as api_client:
            # tb: when it's out of beta, we should move to api v2
            api = EventsApi(api_client)
            end = datetime.datetime.now()
            # tb: we can make timedelta configurable by the user if we want
            start = datetime.datetime.now() - datetime.timedelta(days=1)
            results = api.list_events(
                start=int(start.timestamp()),
                end=int(end.timestamp()),
                tags="source:alert",
            )
            # Filter out events that are related to this monitor only
            # tb: We might want to exclude some fields from event.to_dict() but let's wait for user feedback
            results = [
                event.to_dict()
                for event in results.get("events", [])
                if str(event.monitor_id) == str(monitor_id)
            ]
            self.logger.info(
                "Monitor events retrieved", extra={"monitor_id": monitor_id}
            )
            return results

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Datadog provider.

        """
        self.authentication_config = DatadogProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        scopes = {}
        self.logger.info("Validating scopes")
        with ApiClient(self.configuration) as api_client:
            for scope in self.PROVIDER_SCOPES:
                try:
                    if scope.name == "monitors_read":
                        api = MonitorsApi(api_client)
                        api.list_monitors()
                    elif scope.name == "monitors_write":
                        api = MonitorsApi(api_client)
                        body = Monitor(
                            name="Example-Monitor",
                            type=MonitorType.RUM_ALERT,
                            query='formula("1 * 100").last("15m") >= 200',
                            message="some message Notify: @hipchat-channel",
                            tags=[
                                "test:examplemonitor",
                                "env:ci",
                            ],
                            priority=3,
                            options=MonitorOptions(
                                thresholds=MonitorThresholds(
                                    critical=200,
                                ),
                                variables=[],
                            ),
                        )
                        monitor = api.create_monitor(body)
                        api.delete_monitor(monitor.id)
                    elif scope.name == "create_webhooks":
                        api = WebhooksIntegrationApi(api_client)
                        # We check if we have permissions to query webhooks, this means we have the create_webhooks scope
                        try:
                            api.create_webhooks_integration(
                                body={
                                    "name": "keep-webhook-scope-validation",
                                    "url": "https://example.com",
                                }
                            )
                            # for some reason create_webhooks does not allow to delete: api.delete_webhooks_integration(webhook_name), no scope for deletion
                        except ApiException as e:
                            # If it's something different from 403 it means we have access! (for example, already exists because we created it once)
                            if e.status == 403:
                                raise e
                    elif scope.name == "metrics_read":
                        api = MetricsApi(api_client)
                        api.query_metrics(
                            query="system.cpu.idle{*}",
                            _from=int((datetime.datetime.now()).timestamp()),
                            to=int(datetime.datetime.now().timestamp()),
                        )
                    elif scope.name == "logs_read":
                        self._query(
                            query="*",
                            timeframe="1h",
                            query_type="logs",
                        )
                    elif scope.name == "events_read":
                        api = EventsApi(api_client)
                        end = datetime.datetime.now()
                        start = datetime.datetime.now() - datetime.timedelta(hours=1)
                        api.list_events(
                            start=int(start.timestamp()), end=int(end.timestamp())
                        )
                    elif scope.name == "apm_read":
                        api_instance = ServiceDefinitionApi(api_client)
                        api_instance.list_service_definitions(schema_version="v1")
                    elif scope.name == "apm_service_catalog_read":
                        endpoint = self.__get_service_deps_endpoint(api_client)
                        epoch_time_one_year_ago = self.__get_epoch_one_year_ago()
                        endpoint.call_with_http_info(
                            env=self.authentication_config.environment,
                            start=str(epoch_time_one_year_ago),
                        )
                except ApiException as e:
                    # API failed and it means we're probably lacking some permissions
                    # perhaps we should check if status code is 403 and otherwise mark as valid?
                    self.logger.warning(
                        f"Failed to validate scope {scope.name}",
                        extra={"reason": e.reason, "code": e.status},
                    )
                    scopes[scope.name] = str(e.reason)
                    continue
                scopes[scope.name] = True
        self.logger.info("Scopes validated", extra=scopes)
        return scopes

    def expose(self):
        return {
            "to": int(self.to.timestamp()) * 1000,
            "from": int(self._from.timestamp()) * 1000,
        }

    def _query(self, query="", timeframe="", query_type="", **kwargs: dict):
        timeframe_in_seconds = DatadogProvider.convert_to_seconds(timeframe)
        self.to = datetime.datetime.fromtimestamp(time.time())
        self._from = datetime.datetime.fromtimestamp(
            time.time() - (timeframe_in_seconds)
        )
        if query_type == "logs":
            with ApiClient(self.configuration) as api_client:
                api = LogsApi(api_client)
                results = api.list_logs(
                    body={
                        "query": query,
                        "time": {
                            "_from": self._from,
                            "to": self.to,
                        },
                    }
                )
        elif query_type == "metrics":
            with ApiClient(self.configuration) as api_client:
                api = MetricsApi(api_client)
                results = api.query_metrics(
                    query=query,
                    _from=time.time() - (timeframe_in_seconds * 1000),
                    to=time.time(),
                )
        return results

    def get_alerts_configuration(self, alert_id: str | None = None):
        with ApiClient(self.configuration) as api_client:
            api = MonitorsApi(api_client)
            try:
                monitors = api.list_monitors()
            except Exception as e:
                raise GetAlertException(message=str(e), status_code=e.status)
            monitors = [
                json.dumps(monitor.to_dict(), default=str) for monitor in monitors
            ]
            if alert_id:
                monitors = list(
                    filter(lambda monitor: monitor["id"] == alert_id, monitors)
                )
        return monitors

    def _get_alerts(self) -> list[AlertDto]:
        formatted_alerts = []
        with ApiClient(self.configuration) as api_client:
            # tb: when it's out of beta, we should move to api v2
            # https://docs.datadoghq.com/api/latest/events/
            monitors_api = MonitorsApi(api_client)
            all_monitors = {
                monitor.id: monitor
                for monitor in monitors_api.list_monitors(with_downtimes=True)
            }
            api = EventsApi(api_client)
            end = datetime.datetime.now()
            # tb: we can make timedelta configurable by the user if we want
            start = datetime.datetime.now() - datetime.timedelta(days=14)
            results = api.list_events(
                start=int(start.timestamp()),
                end=int(end.timestamp()),
                tags="source:alert",
            )
            events = results.get("events", [])
            for event in events:
                try:
                    tags = {
                        k: v
                        for k, v in map(
                            lambda tag: tag.split(":", 1),
                            [tag for tag in event.tags if ":" in tag],
                        )
                    }
                    severity, status, title = event.title.split(" ", 2)
                    severity = severity.lstrip("[").rstrip("]")
                    severity = DatadogProvider.SEVERITIES_MAP.get(
                        severity, AlertSeverity.INFO
                    )
                    status = status.lstrip("[").rstrip("]")
                    received = datetime.datetime.fromtimestamp(
                        event.get("date_happened")
                    )
                    monitor = all_monitors.get(event.monitor_id)
                    is_muted = (
                        False
                        if not monitor
                        else any(
                            [
                                downtime
                                for downtime in monitor.matching_downtimes
                                if downtime.groups == event.monitor_groups
                                or downtime.scope == ["*"]
                            ]
                        )
                    )

                    status = (
                        DatadogProvider.STATUS_MAP.get(status, AlertStatus.FIRING)
                        if not is_muted
                        else AlertStatus.SUPPRESSED
                    )

                    alert = AlertDto(
                        id=event.id,
                        name=title,
                        status=status,
                        lastReceived=received.isoformat(),
                        severity=severity,
                        message=event.text,
                        monitor_id=event.monitor_id,
                        # tb: sometimes referred as scopes
                        groups=event.monitor_groups,
                        source=["datadog"],
                        tags=tags,
                        environment=tags.get("environment", "undefined"),
                        service=tags.get("service"),
                        created_by=(
                            monitor.creator.email
                            if monitor and monitor.creator
                            else None
                        ),
                    )
                    alert.fingerprint = self.get_alert_fingerprint(
                        alert, self.fingerprint_fields
                    )
                    formatted_alerts.append(alert)
                except Exception:
                    self.logger.exception(
                        "Could not parse alert event",
                        extra={"event_id": event.id, "monitor_id": event.monitor_id},
                    )
                    continue
        return formatted_alerts

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        self.logger.info("Creating or updating webhook")
        webhook_name = f"{DatadogProviderAuthConfig.KEEP_DATADOG_WEBHOOK_INTEGRATION_NAME}-{tenant_id}"
        with ApiClient(self.configuration) as api_client:
            api = WebhooksIntegrationApi(api_client)
            try:
                webhook = api.get_webhooks_integration(webhook_name=webhook_name)
                if webhook.url != keep_api_url:
                    api.update_webhooks_integration(
                        webhook.name,
                        body={
                            "url": keep_api_url,
                            "custom_headers": json.dumps(
                                {
                                    "Content-Type": "application/json",
                                    "X-API-KEY": api_key,
                                }
                            ),
                            "payload": DatadogProvider.WEBHOOK_PAYLOAD,
                        },
                    )
                    self.logger.info(
                        "Webhook updated",
                    )
            except (NotFoundException, ForbiddenException):
                try:
                    webhook = api.create_webhooks_integration(
                        body={
                            "name": webhook_name,
                            "url": keep_api_url,
                            "custom_headers": json.dumps(
                                {
                                    "Content-Type": "application/json",
                                    "X-API-KEY": api_key,
                                }
                            ),
                            "encode_as": "json",
                            "payload": DatadogProvider.WEBHOOK_PAYLOAD,
                        }
                    )
                    self.logger.info("Webhook created")
                except ApiException as exc:
                    if "Webhook already exists" in exc.body.get("errors"):
                        self.logger.info(
                            "Webhook already exists when trying to add, updating"
                        )
                        try:
                            api.update_webhooks_integration(
                                webhook_name,
                                body={
                                    "url": keep_api_url,
                                    "custom_headers": json.dumps(
                                        {
                                            "Content-Type": "application/json",
                                            "X-API-KEY": api_key,
                                        }
                                    ),
                                    "payload": DatadogProvider.WEBHOOK_PAYLOAD,
                                },
                            )
                        except ApiException:
                            self.logger.exception("Failed to update webhook")
                    else:
                        raise
            self.logger.info("Webhook created or updated")
            if setup_alerts:
                self.logger.info("Updating monitors")
                api = MonitorsApi(api_client)
                monitors = api.list_monitors()
                for monitor in monitors:
                    try:
                        self.logger.info(
                            "Updating monitor",
                            extra={
                                "monitor_id": monitor.id,
                                "monitor_name": monitor.name,
                            },
                        )
                        monitor_message = monitor.message
                        if f"@webhook-{webhook_name}" not in monitor_message:
                            monitor_message = (
                                f"{monitor_message} @webhook-{webhook_name}"
                            )
                            api.update_monitor(
                                monitor.id, body={"message": monitor_message}
                            )
                            self.logger.info(
                                "Monitor updated",
                                extra={
                                    "monitor_id": monitor.id,
                                    "monitor_name": monitor.name,
                                },
                            )
                    except Exception:
                        self.logger.exception(
                            "Could not update monitor",
                            extra={
                                "monitor_id": monitor.id,
                                "monitor_name": monitor.name,
                            },
                        )
                self.logger.info("Monitors updated")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseTopologyProvider" = None
    ) -> AlertDto:
        tags = event.get("tags", "")
        if isinstance(tags, str):
            tags_list = tags.split(",")
            tags_list.remove("monitor")
            tags = {}

            try:
                for tag in tags_list:
                    parts = tag.split(":", 1)  # Split only on first ':'
                    if len(parts) == 2:
                        key, value = parts
                        tags[key] = value
            except Exception as e:
                logger.error(
                    "Failed to parse tags", extra={"error": str(e), "tags": tags_list}
                )
                tags = {}

        service = None
        # Always remove monitor tag
        if isinstance(tags, dict):
            tags.pop("monitor", None)
            service = tags.get("service")

        event_time = datetime.datetime.fromtimestamp(
            int(event.get("last_updated")) / 1000, tz=datetime.timezone.utc
        )
        title = event.get("title")
        # format status and severity to Keep's format
        status = DatadogProvider.STATUS_MAP.get(
            event.get("alert_transition"), AlertStatus.FIRING
        )
        severity = DatadogProvider.SEVERITIES_MAP.get(
            event.get("severity"), AlertSeverity.INFO
        )

        url = event.pop("url", None)

        # https://docs.datadoghq.com/integrations/webhooks/#variables
        groups = event.get("scopes", "")
        if not groups:
            groups = ["*"]
        else:
            groups = groups.split(",")

        description = event.get("message") or event.get("body")
        alert_query = event.get("alert_query")

        # try to get more information from the monitor
        try:
            extra_details = extract_alert_details(event.get("body"))
            extra_details = asdict(extra_details)
            extra_details["imageUrl"] = extra_details.get("metric_graph_url")
        except Exception:
            logger.exception(
                "Failed to extract alert details", extra={"alert": event.get("body")}
            )
            extra_details = {
                "imageUrl": None,
            }

        alert = AlertDto(
            id=event.get("id"),
            name=title,
            status=status,
            lastReceived=str(event_time),
            source=["datadog"],
            message=event.get("body"),
            description=description,
            groups=groups,
            severity=severity,
            service=service,
            url=url,
            tags=tags,
            monitor_id=event.get("monitor_id"),
            alert_query=alert_query,
            imageUrl=extra_details.get("imageUrl"),
            extra_details=extra_details,
        )
        alert.fingerprint = DatadogProvider.get_alert_fingerprint(
            alert, DatadogProvider.FINGERPRINT_FIELDS
        )
        return alert

    def deploy_alert(self, alert: dict, alert_id: str | None = None):
        body = Monitor(**alert)
        with ApiClient(self.configuration) as api_client:
            api_instance = MonitorsApi(api_client)
            try:
                response = api_instance.create_monitor(body=body)
            except Exception as e:
                raise Exception({"message": e.body["errors"][0]})
        return response

    def get_logs(self, limit: int = 5) -> list:
        # Logs from the last 7 days
        timeframe_in_seconds = DatadogProvider.convert_to_seconds("7d")
        _from = datetime.datetime.fromtimestamp(time.time() - (timeframe_in_seconds))
        to = datetime.datetime.fromtimestamp(time.time())
        with ApiClient(self.configuration) as api_client:
            api = LogsApi(api_client)
            results = api.list_logs(
                body={"limit": limit, "time": {"_from": _from, "to": to}}
            )
        return [log.to_dict() for log in results["logs"]]

    @staticmethod
    def get_alert_schema():
        return DatadogAlertFormatDescription.schema()

    @staticmethod
    def __get_epoch_one_year_ago() -> int:
        # Get the current time
        current_time = datetime.datetime.now()

        # Calculate the time one year ago
        one_year_ago = current_time - datetime.timedelta(days=365)

        # Convert the time one year ago to epoch time
        return int(time.mktime(one_year_ago.timetuple()))

    @staticmethod
    def __get_service_deps_endpoint(api_client) -> Endpoint:
        return Endpoint(
            settings={
                "auth": ["apiKeyAuth", "appKeyAuth", "AuthZ"],
                "endpoint_path": "/api/v1/service_dependencies",
                "response_type": (dict,),
                "http_method": "GET",
                "operation_id": "get_service_dependencies",
                "version": "v1",
            },
            params_map={
                "start": {
                    "openapi_types": (str,),
                    "attribute": "start",
                    "location": "query",
                },
                "env": {
                    "openapi_types": (str,),
                    "attribute": "env",
                    "location": "query",
                },
            },
            headers_map={
                "accept": ["application/json"],
                "content_type": ["application/json"],
            },
            api_client=api_client,
        )

    @classmethod
    def simulate_alert(cls) -> dict:
        # Choose a random alert type
        import hashlib
        import random

        from keep.providers.datadog_provider.alerts_mock import ALERTS

        alert_type = random.choice(list(ALERTS.keys()))
        alert_data = ALERTS[alert_type]

        # Start with the base payload
        simulated_alert = alert_data["payload"].copy()

        # Apply variability based on parameters
        for param, choices in alert_data.get("parameters", {}).items():
            # Split param on '.' for nested parameters (if any)
            param_parts = param.split(".")
            target = simulated_alert
            for part in param_parts[:-1]:
                target = target.setdefault(part, {})

            # Choose a random value for the parameter
            target[param_parts[-1]] = random.choice(choices)

        # Apply renders
        for param, choices in alert_data.get("renders", {}).items():
            target = simulated_alert
            for key, val in target.items():
                # try to replace
                param_to_replace = "{{" + param + "}}"
                choice = random.choice(choices)
                target[key] = val.replace(param_to_replace, choice)
            target[param] = choice

        simulated_alert["last_updated"] = int(time.time() * 1000)
        simulated_alert["alert_transition"] = random.choice(
            list(DatadogProvider.STATUS_MAP.keys())
        )
        simulated_alert["id"] = hashlib.sha256(
            str(simulated_alert).encode()
        ).hexdigest()
        return simulated_alert

    def pull_topology(self) -> tuple[list[TopologyServiceInDto], dict]:
        services = {}
        with ApiClient(self.configuration) as api_client:
            api_instance = ServiceDefinitionApi(api_client)
            service_definitions = api_instance.list_service_definitions(
                schema_version="v1"
            )
            epoch_time_one_year_ago = self.__get_epoch_one_year_ago()
            endpoint = self.__get_service_deps_endpoint(api_client)
            service_dependencies = endpoint.call_with_http_info(
                env=self.authentication_config.environment,
                start=str(epoch_time_one_year_ago),
            )

        # Parse data
        environment = self.authentication_config.environment
        if environment == "*":
            environment = "unknown"
        for service_definition in service_definitions.data:
            name = service_definition.attributes.schema.info.dd_service
            services[name] = TopologyServiceInDto(
                source_provider_id=self.provider_id,
                repository=service_definition.attributes.schema.integrations.github,
                tags=service_definition.attributes.schema.tags,
                service=name,
                display_name=service_definition.attributes.schema.info.display_name,
                environment=environment,
                description=service_definition.attributes.schema.info.description,
                team=service_definition.attributes.schema.org.team,
                application=service_definition.attributes.schema.org.application,
                email=service_definition.attributes.schema.contact.email,
                slack=service_definition.attributes.schema.contact.slack,
            )
        for service_dep in service_dependencies:
            service = services.get(service_dep)
            if not service:
                service = TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=service_dep,
                    display_name=service_dep,
                    environment=environment,
                )
            dependencies = service_dependencies[service_dep].get("calls", [])
            service.dependencies = {
                dependency: "unknown" for dependency in dependencies
            }
            services[service_dep] = service
        return list(services.values()), {}

    def _translate_metric_query_to_span_query(
        self, metric_query: str
    ) -> tuple[str, int]:
        """
        Translates a Datadog metric query into a span search query.
        Returns tuple of (query_string, threshold_seconds)
        """
        import re

        # Extract tags from the curly braces
        tags_pattern = r"\{(.*?)\}"
        tags_match = re.search(tags_pattern, metric_query)
        if not tags_match:
            raise ValueError("No tags found in metric query")

        tags_str = tags_match.group(1)
        tags_dict = dict(tag.split(":") for tag in tags_str.split(","))

        # Extract threshold value (the number after '>')
        threshold_pattern = r">\s*(\d+)"
        threshold_match = re.search(threshold_pattern, metric_query)
        if not threshold_match:
            raise ValueError("No threshold found in metric query")

        threshold_seconds = int(threshold_match.group(1))

        # Extract operation name dynamically - look for the string between "trace." and ".duration"
        operation_pattern = r"trace\.(.*?)\.duration"
        operation_match = re.search(operation_pattern, metric_query)
        if not operation_match:
            raise ValueError("Could not find operation name in metric query")

        operation_name = operation_match.group(1)

        # Construct the span search query
        query_parts = [
            f'service:{tags_dict["service"]}',
            f'env:{tags_dict["env"]}',
            f"operation_name:{operation_name}",
            f"@duration:>{threshold_seconds}s",  # @ is used to indicate a span attribute
        ]

        return " ".join(query_parts)


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    api_key = os.environ.get("DATADOG_API_KEY")
    app_key = os.environ.get("DATADOG_APP_KEY")

    provider_config = {
        "authentication": {"api_key": api_key, "app_key": app_key},
    }
    provider: DatadogProvider = ProvidersFactory.get_provider(
        context_manager=context_manager,
        provider_id="datadog-keephq",
        provider_type="datadog",
        provider_config=provider_config,
    )
    result = provider.create_incident(
        "tal test from provider", "what will I tell you?", "Tal Borenstein"
    )
    print(result)
