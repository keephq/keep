import dataclasses
import datetime
import json
import typing
import uuid

import pydantic
import requests

from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

# Todo: think about splitting in to PagerdutyIncidentsProvider and PagerdutyAlertsProvider
# Read this: https://community.pagerduty.com/forum/t/create-incident-using-python/3596/3


@pydantic.dataclasses.dataclass
class PagerdutyProviderAuthConfig:
    routing_key: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "routing_key is an integration or ruleset key",
        },
        default=None,
    )
    api_key: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "api_key is a user or team API key",
            "sensitive": True,
        },
        default=None,
    )


class PagerdutyProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def validate_config(self):
        self.authentication_config = PagerdutyProviderAuthConfig(
            **self.config.authentication
        )
        if (
            not self.authentication_config.routing_key
            and not self.authentication_config.api_key
        ):
            raise ProviderConfigException(
                "PagerdutyProvider requires either routing_key or api_key",
                provider_id=self.provider_id,
            )

    def _build_alert(
        self, title: str, alert_body: str, dedup: str
    ) -> typing.Dict[str, typing.Any]:
        """
        Builds the payload for an event alert.

        Args:
            title: Title of alert
            alert_body: UTF-8 string of custom message for alert. Shown in incident body
            dedup: Any string, max 255, characters used to deduplicate alerts

        Returns:
            Dictionary of alert body for JSON serialization
        """
        return {
            "routing_key": self.authentication_config.routing_key,
            "event_action": "trigger",
            "dedup_key": dedup,
            "payload": {
                "summary": title,
                "source": "custom_event",
                "severity": "critical",
                "custom_details": {
                    "alert_body": alert_body,
                },
            },
        }

    def _send_alert(self, title: str, alert_body: str, dedup: str | None = None):
        """
        Sends PagerDuty Alert

        Args:
            title: Title of the alert.
            alert_body: UTF-8 string of custom message for alert. Shown in incident body
            dedup: Any string, max 255, characters used to deduplicate alerts
        """
        # If no dedup is given, use epoch timestamp
        if dedup is None:
            dedup = str(datetime.datetime.utcnow().timestamp())

        url = "https://events.pagerduty.com//v2/enqueue"

        result = requests.post(url, json=self._build_alert(title, alert_body, dedup))

        self.logger.debug("Alert status: %s", result.status_code)
        self.logger.debug("Alert response: %s", result.text)

    def _trigger_incident(
        self,
        service_id: str,
        title: str,
        body: dict,
        requester: str,
        incident_key: str | None = None,
    ):
        """Triggers an incident via the V2 REST API using sample data."""

        if not incident_key:
            incident_key = str(uuid.uuid4()).replace("-", "")

        url = "https://api.pagerduty.com/incidents"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Authorization": f"Token token={self.authentication_config.api_key}",
            "From": requester,
        }

        payload = {
            "incident": {
                "type": "incident",
                "title": title,
                "service": {"id": service_id, "type": "service_reference"},
                "incident_key": incident_key,
                "body": body,
            }
        }

        r = requests.post(url, headers=headers, data=json.dumps(payload))

        print(f"Status Code: {r.status_code}")
        print(r.json())

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def notify(self, **kwargs: dict):
        """
        Create a PagerDuty alert.
            Alert/Incident is created either via the Events API or the Incidents API.
            See https://community.pagerduty.com/forum/t/create-incident-using-python/3596/3 for more information

        Args:
            kwargs (dict): The providers with context
        """
        if self.authentication_config.routing_key:
            self._send_alert(**kwargs)
        else:
            self._trigger_incident(**kwargs)
