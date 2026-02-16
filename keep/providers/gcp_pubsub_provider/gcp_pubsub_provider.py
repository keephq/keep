"""
GcpPubsubProvider is a provider that receives GCP Pub/Sub push messages
and can pull messages from a subscription. Useful for GKE cluster notifications.
"""

import base64
import dataclasses
import json
import logging
from datetime import datetime
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)

# Map GKE notification types to severity
GKE_SEVERITY_MAP = {
    "SECURITY_BULLETIN": AlertSeverity.CRITICAL,
    "UPGRADE_AVAILABLE": AlertSeverity.INFO,
    "UPGRADE_FORCED": AlertSeverity.WARNING,
    "END_OF_SUPPORT": AlertSeverity.HIGH,
    "SECURITY_BULLETIN_EVENT": AlertSeverity.CRITICAL,
}


@pydantic.dataclasses.dataclass
class GcpPubsubProviderAuthConfig:
    """GCP Pub/Sub authentication configuration."""

    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "GCP Project ID",
            "sensitive": False,
        }
    )
    subscription_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Pub/Sub Subscription ID",
            "sensitive": False,
        }
    )
    credentials_json: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Google Service Account JSON credentials",
            "sensitive": True,
        }
    )


class GcpPubsubProvider(BaseProvider):
    """Receive and pull alerts from Google Cloud Pub/Sub (e.g. GKE cluster notifications)."""

    PROVIDER_DISPLAY_NAME = "GCP Pub/Sub"
    PROVIDER_CATEGORY = ["Monitoring", "Queue"]
    PROVIDER_TAGS = ["queue"]
    FINGERPRINT_FIELDS = ["id"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="pubsub_pull",
            description="Pull messages from Pub/Sub subscription",
            mandatory=True,
            alias="Pub/Sub Pull",
        ),
    ]

    webhook_description = "Receive GCP Pub/Sub push messages"
    webhook_markdown = """
To send Pub/Sub messages to Keep:

1. Create a Pub/Sub push subscription pointing to: `{keep_webhook_api_url}`
2. Add the header `X-API-KEY` with value `{api_key}` in the push config.
3. Messages pushed to the topic will be forwarded to Keep as alerts.
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = GcpPubsubProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """Validate that we can access the subscription."""
        scopes = {}
        try:
            self._get_access_token()
            scopes["pubsub_pull"] = True
        except Exception as e:
            self.logger.exception("Failed to validate scopes")
            scopes["pubsub_pull"] = str(e)
        return scopes

    def _get_access_token(self) -> str:
        """Get an access token using service account credentials via OAuth2."""
        import time
        import hashlib
        import hmac

        credentials = json.loads(self.authentication_config.credentials_json)

        # Use the token endpoint from the credentials
        token_uri = credentials.get(
            "token_uri", "https://oauth2.googleapis.com/token"
        )

        # Build JWT for service account
        now = int(time.time())
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
        ).rstrip(b"=")

        claim_set = {
            "iss": credentials["client_email"],
            "scope": "https://www.googleapis.com/auth/pubsub",
            "aud": token_uri,
            "exp": now + 3600,
            "iat": now,
        }
        payload = base64.urlsafe_b64encode(
            json.dumps(claim_set).encode()
        ).rstrip(b"=")

        # Sign with RSA private key
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        private_key = serialization.load_pem_private_key(
            credentials["private_key"].encode(), password=None
        )
        signing_input = header + b"." + payload
        signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=")

        jwt_token = (signing_input + b"." + signature_b64).decode()

        response = requests.post(
            token_uri,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def _query(self, **kwargs) -> list[AlertDto]:
        """Pull messages from the Pub/Sub subscription."""
        access_token = self._get_access_token()
        project_id = self.authentication_config.project_id
        subscription_id = self.authentication_config.subscription_id

        url = (
            f"https://pubsub.googleapis.com/v1/projects/{project_id}"
            f"/subscriptions/{subscription_id}:pull"
        )

        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"maxMessages": kwargs.get("max_messages", 100)},
        )
        response.raise_for_status()

        received_messages = response.json().get("receivedMessages", [])
        alerts = []
        ack_ids = []

        for msg in received_messages:
            ack_ids.append(msg["ackId"])
            pubsub_message = msg.get("message", {})
            event = self._parse_pubsub_message(pubsub_message)
            alert = self._format_alert(event, provider_instance=self)
            if isinstance(alert, list):
                alerts.extend(alert)
            else:
                alerts.append(alert)

        # Acknowledge messages
        if ack_ids:
            ack_url = (
                f"https://pubsub.googleapis.com/v1/projects/{project_id}"
                f"/subscriptions/{subscription_id}:acknowledge"
            )
            requests.post(
                ack_url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={"ackIds": ack_ids},
            )

        return alerts

    @staticmethod
    def _parse_pubsub_message(message: dict) -> dict:
        """Decode a Pub/Sub message (base64 data + attributes)."""
        data = message.get("data", "")
        try:
            decoded = base64.b64decode(data).decode("utf-8")
            payload = json.loads(decoded)
        except Exception:
            payload = {"raw": data}

        attributes = message.get("attributes", {})
        payload["pubsub_attributes"] = attributes
        payload["pubsub_message_id"] = message.get("messageId", "")
        payload["pubsub_publish_time"] = message.get("publishTime", "")
        return payload

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Parse a Pub/Sub message payload into an AlertDto.
        Supports GKE cluster notification format.
        """
        # Try to extract GKE notification fields
        notification_type = (
            event.get("type_url", "")
            or event.get("pubsub_attributes", {}).get("type_url", "")
            or event.get("pubsub_attributes", {}).get("notification_type", "")
            or event.get("notification_type", "UNKNOWN")
        )

        # Normalize notification type (strip prefix if present)
        if "/" in notification_type:
            notification_type = notification_type.rsplit("/", 1)[-1]

        severity = GKE_SEVERITY_MAP.get(
            notification_type.upper(), AlertSeverity.INFO
        )

        message_id = (
            event.get("pubsub_message_id", "")
            or event.get("id", "")
            or event.get("incident_id", "")
        )

        cluster_name = (
            event.get("cluster_name", "")
            or event.get("pubsub_attributes", {}).get("cluster_name", "")
            or event.get("resourceName", "")
        )

        title = event.get("title", "") or event.get("summary", "") or f"GKE {notification_type}"
        description = (
            event.get("description", "")
            or event.get("detail", "")
            or event.get("message", "")
            or json.dumps(event)
        )

        publish_time = event.get("pubsub_publish_time", "")
        try:
            timestamp = datetime.fromisoformat(
                publish_time.replace("Z", "+00:00")
            ) if publish_time else datetime.utcnow()
        except (ValueError, AttributeError):
            timestamp = datetime.utcnow()

        alert = AlertDto(
            id=message_id,
            name=title,
            title=title,
            description=description,
            severity=severity,
            status=AlertStatus.FIRING,
            source=["gcp_pubsub"],
            cluster_name=cluster_name,
            notification_type=notification_type,
            lastReceived=timestamp.isoformat(),
            startedAt=timestamp.isoformat(),
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

    config = {
        "authentication": {
            "project_id": os.environ.get("GCP_PROJECT_ID", "my-project"),
            "subscription_id": os.environ.get("GCP_SUBSCRIPTION_ID", "my-sub"),
            "credentials_json": os.environ.get("GCP_CREDENTIALS_JSON", "{}"),
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="gcp_pubsub_test",
        provider_type="gcp_pubsub",
        provider_config=config,
    )
    print("Provider created successfully")
