"""
Datadog Provider is a class that allows to ingest/digest data from Datadog.
"""
import dataclasses
import datetime
import json
import os
import random
import re
import time

import pydantic
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.exceptions import NotFoundException
from datadog_api_client.v1.api.logs_api import LogsApi
from datadog_api_client.v1.api.metrics_api import MetricsApi
from datadog_api_client.v1.api.monitors_api import MonitorsApi
from datadog_api_client.v1.api.webhooks_integration_api import WebhooksIntegrationApi
from datadog_api_client.v1.model.monitor import Monitor

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.base.provider_exceptions import GetAlertException
from keep.providers.datadog_provider.datadog_alert_format_description import (
    DatadogAlertFormatDescription,
)
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


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
        }
    )
    app_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Datadog App Key",
            "hint": "https://docs.datadoghq.com/account_management/api-app-keys/#application-keys",
            "sensitive": True,
        }
    )


class DatadogProvider(BaseProvider):
    """
    Datadog provider class.
    """

    EVENT_NAME_PATTERN = r".*\] (.*)"

    def convert_to_seconds(s):
        seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        return int(s[:-1]) * seconds_per_unit[s[-1]]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.configuration = Configuration(request_timeout=5)
        self.configuration.api_key["apiKeyAuth"] = self.authentication_config.api_key
        self.configuration.api_key["appKeyAuth"] = self.authentication_config.app_key
        # to be exposed
        self.to = None
        self._from = None

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

    def expose(self):
        return {
            "to": int(self.to.timestamp()) * 1000,
            "from": int(self._from.timestamp()) * 1000,
        }

    def _query(self, **kwargs: dict):
        query = kwargs.get("query")
        timeframe = kwargs.get("timeframe")
        timeframe_in_seconds = DatadogProvider.convert_to_seconds(timeframe)
        query_type = kwargs.get("query_type")
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

    @staticmethod
    def __get_priorty(priority):
        if priority == "P1":
            return "critical"
        elif priority == "P2":
            return "high"
        elif priority == "P3":
            return "medium"
        elif priority == "P4":
            return "low"

    def get_alerts(self) -> list[AlertDto]:
        formatted_alerts = []
        with ApiClient(self.configuration) as api_client:
            api = MonitorsApi(api_client)
            try:
                monitors = api.list_monitors()

                for monitor in monitors:
                    tags = {
                        k: v for k, v in map(lambda tag: tag.split(":"), monitor.tags)
                    }
                    severity = DatadogProvider.__get_priorty(f"P{monitor.priority}")
                    alert = AlertDto(
                        id=monitor.id,
                        name=monitor.name,
                        status=str(monitor.overall_state),
                        lastReceived=monitor.overall_state_modified,
                        severity=severity,
                        message=monitor.message,
                        description=monitor.name,
                        source=["datadog"],
                        **tags,
                    )
                    formatted_alerts.append(alert)

            except Exception as e:
                raise GetAlertException(message=str(e), status_code=e.status)
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
                        webhook.name, body={"url": keep_api_url}
                    )
                    self.logger.info("Webhook updated")
            except NotFoundException:
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
                        "payload": json.dumps(
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
                                "org": {"id": "$ORG_ID", "name": "$ORG_NAME"},
                                "url": "$LINK",
                                "tags": "$TAGS",
                                "id": "$ID",
                            }
                        ),
                    }
                )
                self.logger.info("Webhook created")
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

    def format_alert(event: dict) -> AlertDto:
        tags_list = event.get("tags", "").split(",")
        tags_list.remove("monitor")
        tags = {k: v for k, v in map(lambda tag: tag.split(":"), tags_list)}
        event_time = datetime.datetime.fromtimestamp(
            int(event.get("last_updated")) / 1000
        )
        event_name = event.get("title")
        match = re.match(DatadogProvider.EVENT_NAME_PATTERN, event_name)
        if match:
            event_name = match.group(1)
        return AlertDto(
            id=event.get("id"),
            name=event_name,
            status=event.get("alert_transition"),
            lastReceived=str(event_time),
            source=["datadog"],
            message=event.get("body"),
            description=event_name,
            severity=DatadogProvider.__get_priorty(event.get("severity")),
            fatigueMeter=random.randint(0, 100),
            **tags,
        )

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


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    api_key = os.environ.get("DATADOG_API_KEY")
    app_key = os.environ.get("DATADOG_APP_KEY")

    provider_config = {
        "authentication": {"api_key": api_key, "app_key": app_key},
    }
    provider = ProvidersFactory.get_provider(
        provider_id="datadog-keephq",
        provider_type="datadog",
        provider_config=provider_config,
    )
    results = provider.setup_webhook("http://localhost:8000", "1234", True)
    print(results)
