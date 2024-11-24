import dataclasses
import datetime

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class PingdomProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "description": "Pingdom API Key",
            "sensitive": True,
            "required": True,
        },
    )


class PingdomProvider(BaseProvider):
    "Get alerts from Pingdom."
    webhook_description = """Install Keep as Pingdom webhook
    1. Go to Settings > Integrations.
    2. Click Add Integration.
    3. Enter:
            Type = Webhook
            Name = Keep
            URL = {keep_webhook_api_url_with_auth}
    4. Click Save Integration.
"""
    webhook_template = """"""
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="read",
            description="Read alerts from Pingdom.",
            mandatory=True,
        ),
    ]
    # N/A
    SEVERITIES_MAP = {}
    STATUS_MAP = {
        "down": AlertStatus.FIRING,
        "up": AlertStatus.RESOLVED,
        "paused": AlertStatus.SUPPRESSED,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate_config(self):
        """
        Validate provider configuration specific to Pingdom.
        """
        self.authentication_config = PingdomProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        Dispose provider resources.
        """
        pass

    def _get_headers(self):
        """
        Helper method to get headers for Pingdom API requests.
        """
        return {
            "Authorization": f"Bearer {self.authentication_config.api_key}",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate Pingdom scopes.
        """
        # try get alerts from pingdom
        try:
            self.get_alerts()
            return {
                "read": True,
            }
        except Exception as e:
            return {"read": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Retrieve alerts from Pingdom.
        """
        # Example API call to Pingdom to retrieve alerts
        alerts_response = requests.get(
            "https://api.pingdom.com/api/3.1/actions", headers=self._get_headers()
        )
        alerts_response.raise_for_status()
        alerts = alerts_response.json().get("actions", {}).get("alerts")

        checks_response = requests.get(
            "https://api.pingdom.com/api/3.1/checks", headers=self._get_headers()
        )
        checks_response.raise_for_status()
        checks = checks_response.json().get("checks", [])

        alerts_dtos = []
        for alert in alerts:
            check_name = next(
                (
                    check.get("name")
                    for check in checks
                    if check.get("id") == alert.get("checkid")
                ),
                None,
            )
            # map severity and status to keep's format
            status = PingdomProvider.STATUS_MAP.get(
                alert.get("status"), AlertStatus.FIRING
            )
            # its N/A but maybe in the future we will have it
            severity = PingdomProvider.SEVERITIES_MAP.get(
                alert.get("severity"), AlertSeverity.INFO
            )

            alert_dto = AlertDto(
                id=alert.get("checkid"),
                fingerprint=alert.get("checkid"),
                name=check_name,
                severity=severity,
                status=status,
                lastReceived=datetime.datetime.now().isoformat(),
                description=alert.get("messagefull"),
                charged=alert.get("charged"),
                source=["pingdom"],
                username=alert.get("username"),
                userid=alert.get("userid"),
                via=alert.get("via"),
            )
            alerts_dtos.append(alert_dto)

        return alerts_dtos

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # https://pingdom.com/resources/webhooks/#Examples-of-webhook-JSON-output-for-uptime-checks

        # map severity and status to keep's format

        alert = AlertDto(
            id=event.get("check_id"),
            fingerprint=event.get("check_id"),
            name=event.get("check_name"),
            status=event.get("current_state"),
            severity=event.get("importance_level", None),
            lastReceived=datetime.datetime.now().isoformat(),
            description=event.get("long_description"),
            source=["pingdom"],
            check_params=event.get("check_params", {}),
            check_type=event.get("check_type", None),
            short_description=event.get("description", None),
            previous_status=event.get("previous_state", None),
            tags=event.get("tags", []),
            version=event.get("version", 1),
            state_changed_utc_time=event.get("state_changed_utc_time", None),
            state_changed_timestamp=event.get("state_changed_timestamp", None),
            custom_message=event.get("custom_message", None),
            first_probe=event.get("first_probe", None),
            second_probe=event.get("second_probe", None),
        )
        return alert


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    api_key = os.environ.get("PINGDOM_API_KEY")
    if not api_key:
        raise Exception("PINGDOM_API_KEY environment variable is not set")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = {"authentication": {"api_key": api_key}}
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="pingdom-keephq",
        provider_type="pingdom",
        provider_config=config,
    )
    scopes = provider.validate_scopes()
    alerts = provider.get_alerts()
    print(alerts)
