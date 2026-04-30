"""
GcpPubSubProvider is a class that allows you to pull messages from a Google Cloud
Pub/Sub subscription and surface them as Keep alerts.

Common use-cases:
- GKE cluster lifecycle notifications (upgrades, end-of-support, security issues)
- Cloud Monitoring alert notifications forwarded via Pub/Sub
- Custom application events published to a Pub/Sub topic
"""

import base64
import dataclasses
import json
import time
from datetime import datetime, timezone

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class GcpPubSubProviderAuthConfig:
    """
    GCP authentication via a Service Account JSON key.
    The service account requires the `roles/pubsub.subscriber` role on the subscription.
    """

    service_account_json: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "GCP Service Account JSON key with Pub/Sub Subscriber role",
            "sensitive": True,
            "type": "file",
            "name": "service_account_json",
            "file_type": "application/json",
        }
    )
    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "GCP Project ID",
            "hint": "e.g. my-gcp-project",
        }
    )
    subscription_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Pub/Sub subscription ID (not topic, the subscription)",
            "hint": "e.g. my-subscription (without projects/.../subscriptions/ prefix)",
        }
    )
    max_messages: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "Maximum messages to pull per cycle (1-1000)",
            "hint": "Default: 100",
        },
        default=100,
    )


class GcpPubSubProvider(BaseProvider):
    """Pull messages from a Google Cloud Pub/Sub subscription as Keep alerts."""

    PROVIDER_DISPLAY_NAME = "GCP Pub/Sub"
    PROVIDER_CATEGORY = ["Cloud Infrastructure", "Monitoring"]
    PROVIDER_TAGS = ["alert", "cloud"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="roles/pubsub.subscriber",
            description="Pull messages from and acknowledge messages in the subscription",
            mandatory=True,
            alias="Pub/Sub Subscriber",
        ),
    ]

    # GCP OAuth2 token endpoint
    _TOKEN_URL = "https://oauth2.googleapis.com/token"
    _PUBSUB_API = "https://pubsub.googleapis.com/v1"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._access_token: str | None = None
        self._token_expiry: float = 0.0

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = GcpPubSubProviderAuthConfig(
            **self.config.authentication
        )

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _get_service_account(self) -> dict:
        sa_json = self.authentication_config.service_account_json
        if isinstance(sa_json, str):
            return json.loads(sa_json)
        return sa_json

    def _get_access_token(self) -> str:
        """Return a valid OAuth2 access token, refreshing if needed."""
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        sa = self._get_service_account()
        # Build JWT for service account auth
        import jwt  # PyJWT, already a transitive dep via several providers

        now = int(time.time())
        payload = {
            "iss": sa["client_email"],
            "scope": "https://www.googleapis.com/auth/pubsub",
            "aud": self._TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        }
        signed = jwt.encode(payload, sa["private_key"], algorithm="RS256")

        resp = requests.post(
            self._TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": signed,
            },
            timeout=15,
        )
        resp.raise_for_status()
        token_data = resp.json()
        self._access_token = token_data["access_token"]
        self._token_expiry = time.time() + token_data.get("expires_in", 3600)
        return self._access_token

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    def _subscription_path(self) -> str:
        return (
            f"projects/{self.authentication_config.project_id}"
            f"/subscriptions/{self.authentication_config.subscription_id}"
        )

    # ------------------------------------------------------------------
    # Scope validation
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict[str, bool | str]:
        self.logger.info("Validating GCP Pub/Sub scopes")
        sub_path = self._subscription_path()
        url = f"{self._PUBSUB_API}/{sub_path}"
        try:
            resp = requests.get(url, headers=self._auth_headers(), timeout=15)
            if resp.ok:
                return {"roles/pubsub.subscriber": True}
            return {"roles/pubsub.subscriber": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"roles/pubsub.subscriber": str(e)}

    # ------------------------------------------------------------------
    # Alert pulling
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """Pull messages from the Pub/Sub subscription and convert to AlertDtos."""
        self.logger.info("Pulling messages from GCP Pub/Sub")
        sub_path = self._subscription_path()
        pull_url = f"{self._PUBSUB_API}/{sub_path}:pull"

        resp = requests.post(
            pull_url,
            headers=self._auth_headers(),
            json={"maxMessages": self.authentication_config.max_messages},
            timeout=30,
        )
        resp.raise_for_status()

        received_messages = resp.json().get("receivedMessages", [])
        if not received_messages:
            self.logger.info("No messages available in Pub/Sub subscription")
            return []

        alerts = []
        ack_ids = []

        for msg_wrapper in received_messages:
            ack_ids.append(msg_wrapper["ackId"])
            pubsub_msg = msg_wrapper["message"]
            alert = self._pubsub_message_to_alert(pubsub_msg)
            alerts.append(alert)

        # Acknowledge messages so they aren't re-delivered
        if ack_ids:
            ack_url = f"{self._PUBSUB_API}/{sub_path}:acknowledge"
            try:
                requests.post(
                    ack_url,
                    headers=self._auth_headers(),
                    json={"ackIds": ack_ids},
                    timeout=15,
                )
            except Exception as e:
                self.logger.warning("Failed to acknowledge Pub/Sub messages", extra={"error": str(e)})

        self.logger.info(f"Pulled {len(alerts)} messages from Pub/Sub")
        return alerts

    def _pubsub_message_to_alert(self, pubsub_msg: dict) -> AlertDto:
        """Convert a raw Pub/Sub message to an AlertDto."""
        msg_id = pubsub_msg.get("messageId", "")
        publish_time = pubsub_msg.get("publishTime", datetime.now(timezone.utc).isoformat())
        attributes = pubsub_msg.get("attributes", {})

        # Decode base64 data payload
        raw_data = pubsub_msg.get("data", "")
        payload = {}
        description = ""
        if raw_data:
            try:
                decoded = base64.b64decode(raw_data).decode("utf-8")
                payload = json.loads(decoded)
                description = decoded
            except (ValueError, json.JSONDecodeError):
                description = base64.b64decode(raw_data).decode("utf-8", errors="replace")

        # Determine severity and status from common GKE/GCP notification patterns
        notification_type = attributes.get("notificationType", payload.get("typeUrl", ""))
        severity = self._infer_severity(notification_type, payload)
        status = self._infer_status(payload)

        name = (
            payload.get("payload", {}).get("resourceType", "")
            or attributes.get("notificationType", "")
            or "GCP Pub/Sub Message"
        )

        return AlertDto(
            id=msg_id,
            fingerprint=msg_id,
            name=name,
            description=description or str(payload),
            severity=severity,
            status=status,
            lastReceived=publish_time,
            source=["gcppubsub"],
            notificationType=notification_type,
            **{k: v for k, v in attributes.items() if k not in ("notificationType",)},
        )

    def _infer_severity(self, notification_type: str, payload: dict) -> AlertSeverity:
        nt_lower = notification_type.lower()
        if "security" in nt_lower or "critical" in nt_lower:
            return AlertSeverity.CRITICAL
        if "upgrade" in nt_lower or "end_of_support" in nt_lower or "endofsupport" in nt_lower:
            return AlertSeverity.HIGH
        if "warning" in nt_lower or "degraded" in nt_lower:
            return AlertSeverity.WARNING
        return AlertSeverity.INFO

    def _infer_status(self, payload: dict) -> AlertStatus:
        state = str(payload.get("state", payload.get("status", ""))).upper()
        if state in ("RESOLVED", "OK", "CLOSED"):
            return AlertStatus.RESOLVED
        if state in ("FIRING", "ALERTING", "OPEN"):
            return AlertStatus.FIRING
        return AlertStatus.FIRING


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    config = ProviderConfig(
        description="GCP Pub/Sub Provider",
        authentication={
            "service_account_json": open(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]).read(),
            "project_id": os.environ["GCP_PROJECT_ID"],
            "subscription_id": os.environ["PUBSUB_SUBSCRIPTION_ID"],
        },
    )

    provider = GcpPubSubProvider(context_manager, "gcppubsub", config)
    print(provider.validate_scopes())
    print(provider._get_alerts())
