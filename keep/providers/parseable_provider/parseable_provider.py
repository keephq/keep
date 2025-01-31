"""
Parseable Provider is a class that allows to ingest/digest data from Parseable.
"""

import dataclasses
import datetime
import logging
import os
from uuid import uuid4

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class ParseableProviderAuthConfig:
    """
    Parseable authentication configuration.
    """

    parseable_server: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Parseable Frontend URL",
            "hint": "https://demo.parseable.io",
            "sensitive": False,
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Parseable username",
            "sensitive": False,
        }
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Parseable password",
            "sensitive": True,
        }
    )


class ParseableProvider(BaseProvider):
    """Parseable provider to ingest data from Parseable."""

    PROVIDER_CATEGORY = ["Monitoring"]
    webhook_description = "This is an example of how to configure an alert to be sent to Keep using Parseable's webhook feature. Post this to https://YOUR_PARSEABLE_SERVER/api/v1/logstream/YOUR_STREAM_NAME/alert"
    webhook_template = """{{
    "version": "v1",
    "alerts": [
        {{
            "name": "Alert: Server side error",
            "message": "server reporting status as 500",
            "rule": {{
                "type": "column",
                "config": {{
                    "column": "status",
                    "operator": "=",
                    "value": 500,
                    "repeats": 2
                }}
            }},
            "targets": [
                {{
                    "type": "webhook",
                    "endpoint": "{keep_webhook_api_url}",
                    "skip_tls_check": true,
                    "repeat": {{
                        "interval": "10s",
                        "times": 5
                    }},
                    "headers": {{"X-API-KEY": "{api_key}"}}
                }}
            ]
        }}
    ]
}}"""

    SEVERITIES_MAP = {
        "disaster": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "average": AlertSeverity.WARNING,
        "low": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "pending": AlertStatus.PENDING,
        "suppressed": AlertStatus.SUPPRESSED,
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
        Validates required configuration for Parseable provider.

        """
        self.authentication_config = ParseableProviderAuthConfig(
            **self.config.authentication
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        environment = "unknown"
        id = event.pop("id", str(uuid4()))
        name = event.pop("alert", "")
        # map severity and status to keep's format
        status = ParseableProvider.STATUS_MAP.get(
            event.pop("status", None), AlertStatus.FIRING
        )
        severity = ParseableProvider.SEVERITIES_MAP.get(
            event.pop("severity", "").lower(), AlertSeverity.INFO
        )

        lastReceived = event.pop("last_received", datetime.datetime.now().isoformat())
        decription = event.pop("failing_condition", "")
        tags = event.get("tags", {})
        if isinstance(tags, dict):
            environment = tags.get("environment", "unknown")

        return AlertDto(
            **event,
            id=id,
            name=name,
            status=status,
            lastReceived=lastReceived,
            description=decription,
            environment=environment,
            pushed=True,
            source=["parseable"],
            severity=severity,
        )

    @staticmethod
    def parse_event_raw_body(raw_body: bytes | dict) -> dict:
        """
        Parse the raw body of the event.
        > b'Alert: Server side error triggered on teststream1\nMessage: server reporting status as 500\nFailing Condition: status column equal to abcd, 2 times'
        and we want to return an object
        > b"{'alert': 'Server side error triggered on teststream1', 'message': 'server reporting status as 500', 'failing_condition': 'status column equal to abcd, 2 times'}"

        Args:
            raw_body (bytes): the message in form of raw bytes sent by parseable server

        Returns:
            bytes: parseable bytes of dictionary for the rest of the flow
        """
        logger = logging.getLogger(__name__)
        raw_body_string = raw_body.decode()
        raw_body_split = raw_body_string.split("\n")
        event = {}
        for line in raw_body_split:
            if line:
                try:
                    key, value = line.split(": ")
                    event[key.lower().replace(" ", "_")] = value
                except Exception as e:
                    logger.error(f"Failed to parse line {line} with error {e}")
        return event


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

    auth_token = os.environ.get("PARSEABLE_AUTH_TOKEN")

    provider_config = {
        "authentication": {
            "auth_token": auth_token,
            "parseable_frontend_url": "http://localhost",
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="parseable-prod",
        provider_type="parseable",
        provider_config=provider_config,
    )
