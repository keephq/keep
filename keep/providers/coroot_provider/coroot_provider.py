"""
CorootProvider is a class that allows to ingest/digest data from Coroot.
"""

import dataclasses
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class CorootProviderAuthConfig:
    """
    Coroot authentication configuration.
    """

    api_url: str = dataclasses.field(
        metadata={
            "required": True,
            "sensitive": False,
            "description": "Coroot API URL",
            "hint": "https://coroot.example.com",
        }
    )
    api_key: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "sensitive": True,
            "description": "Coroot API Key",
        },
        default=None,
    )


class CorootProvider(BaseProvider):
    """Receive alerts from Coroot via webhooks."""

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
    To send alerts from Coroot to Keep, configure a webhook integration in Coroot:

    1. In Coroot, go to **Project Settings** → **Integrations**.
    2. Add a new **Webhook** integration.
    3. Set the webhook URL to: `{keep_webhook_api_url}`
    4. Add a custom header `X-API-KEY` with the value `{api_key}`.
    5. Use the default payload template (Coroot sends JSON with Status, Application, Reports, and URL fields).
    6. Save the integration.
    7. Alerts from Coroot will now appear in Keep when incidents are triggered.
    """

    PROVIDER_DISPLAY_NAME = "Coroot"
    PROVIDER_CATEGORY = ["Monitoring"]

    STATUS_SEVERITY_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "WARNING": AlertSeverity.WARNING,
        "OK": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "CRITICAL": AlertStatus.FIRING,
        "WARNING": AlertStatus.FIRING,
        "OK": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Coroot provider.
        """
        self.authentication_config = CorootProviderAuthConfig(
            **self.config.authentication
        )

    def _query(self, **kwargs: dict):
        """
        Query Coroot API for applications.

        Returns:
            list: List of applications from Coroot.
        """
        api_url = self.authentication_config.api_url.rstrip("/")
        headers = {}
        if self.authentication_config.api_key:
            headers["Authorization"] = f"Bearer {self.authentication_config.api_key}"

        response = requests.get(
            f"{api_url}/api/v1/applications",
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        status = event.get("Status", "WARNING")
        application = event.get("Application", {})
        reports = event.get("Reports", [])
        url = event.get("URL", "")

        app_name = application.get("Name", "unknown")
        app_namespace = application.get("Namespace", "")
        app_kind = application.get("Kind", "")

        # Build description from reports
        descriptions = []
        checks = []
        for report in reports:
            msg = report.get("Message", "")
            check = report.get("Check", "")
            report_name = report.get("Name", "")
            if msg:
                descriptions.append(f"[{report_name}/{check}] {msg}")
            if check:
                checks.append(check)

        description = "; ".join(descriptions) if descriptions else f"Coroot alert for {app_name}"

        severity = CorootProvider.STATUS_SEVERITY_MAP.get(
            status, AlertSeverity.WARNING
        )
        alert_status = CorootProvider.STATUS_MAP.get(
            status, AlertStatus.FIRING
        )

        alert = AlertDto(
            id=f"coroot-{app_namespace}-{app_kind}-{app_name}",
            name=f"{app_name} - {checks[0]}" if checks else app_name,
            description=description,
            severity=severity,
            status=alert_status,
            url=url,
            service=app_name,
            source=["coroot"],
            namespace=app_namespace,
            application_kind=app_kind,
            reports=reports,
        )

        return alert


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    import os

    api_url = os.environ.get("COROOT_API_URL", "http://localhost:8080")
    api_key = os.environ.get("COROOT_API_KEY")

    config = {
        "authentication": {"api_url": api_url, "api_key": api_key},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="coroot_test",
        provider_type="coroot",
        provider_config=config,
    )
    result = provider.query()
    print(result)
