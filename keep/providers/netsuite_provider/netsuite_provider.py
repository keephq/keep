"""
NetSuiteProvider is a class that allows you to create and manage tickets in NetSuite.
"""

import dataclasses
import hashlib
import hmac
import time
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NetsuiteProviderAuthConfig:
    """
    NetSuite authentication configuration using TBA (Token-Based Authentication).
    """

    account_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "NetSuite Account ID (e.g. 1234567 or 1234567_SB1 for sandbox)",
            "hint": "Found in Setup > Company > Company Information",
        },
    )
    consumer_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Consumer Key from the OAuth integration record",
            "sensitive": True,
        },
    )
    consumer_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Consumer Secret from the OAuth integration record",
            "sensitive": True,
        },
    )
    token_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Token ID from the Access Token record",
            "sensitive": True,
        },
    )
    token_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Token Secret from the Access Token record",
            "sensitive": True,
        },
    )


class NetsuiteProvider(BaseProvider):
    """Create and manage support cases/tickets in NetSuite."""

    PROVIDER_DISPLAY_NAME = "NetSuite"
    PROVIDER_CATEGORY = ["Ticketing"]
    PROVIDER_TAGS = ["ticketing"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated via TBA",
            mandatory=True,
            alias="Authenticated",
        ),
        ProviderScope(
            name="support_cases_read",
            description="Can read support cases",
            mandatory=True,
            alias="Support Cases - Read",
        ),
    ]

    NETSUITE_BASE_URL = "https://{account_id}.suitetalk.api.netsuite.com/services/rest/record/v1"

    STATUS_MAP = {
        "Open": AlertStatus.FIRING,
        "Closed": AlertStatus.RESOLVED,
        "Escalated": AlertStatus.FIRING,
        "Pending Customer Reply": AlertStatus.ACKNOWLEDGED,
        "Customer Replied": AlertStatus.FIRING,
        "Re-Opened": AlertStatus.FIRING,
    }

    SEVERITY_MAP = {
        "1 - Critical": AlertSeverity.CRITICAL,
        "2 - High": AlertSeverity.HIGH,
        "3 - Medium": AlertSeverity.WARNING,
        "4 - Low": AlertSeverity.LOW,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = NetsuiteProviderAuthConfig(
            **self.config.authentication
        )

    def _get_base_url(self) -> str:
        account_id = self.authentication_config.account_id.lower().replace("_", "-")
        return f"https://{account_id}.suitetalk.api.netsuite.com/services/rest/record/v1"

    def _build_auth_header(self, method: str, url: str) -> str:
        """Build OAuth 1.0 Authorization header using TBA."""
        nonce = uuid.uuid4().hex
        timestamp = str(int(time.time()))
        account_id = self.authentication_config.account_id.upper()

        base_string = "&".join([
            method.upper(),
            requests.utils.quote(url, safe=""),
            requests.utils.quote(
                f"oauth_consumer_key={self.authentication_config.consumer_key}"
                f"&oauth_nonce={nonce}"
                f"&oauth_signature_method=HMAC-SHA256"
                f"&oauth_timestamp={timestamp}"
                f"&oauth_token={self.authentication_config.token_id}"
                f"&oauth_version=1.0",
                safe="",
            ),
        ])

        signing_key = (
            requests.utils.quote(self.authentication_config.consumer_secret, safe="")
            + "&"
            + requests.utils.quote(self.authentication_config.token_secret, safe="")
        )

        signature = hmac.new(
            signing_key.encode("ascii"),
            base_string.encode("ascii"),
            hashlib.sha256,
        ).digest()
        import base64
        signature_b64 = base64.b64encode(signature).decode("ascii")

        return (
            f'OAuth realm="{account_id}",'
            f'oauth_consumer_key="{self.authentication_config.consumer_key}",'
            f'oauth_token="{self.authentication_config.token_id}",'
            f'oauth_signature_method="HMAC-SHA256",'
            f'oauth_timestamp="{timestamp}",'
            f'oauth_nonce="{nonce}",'
            f'oauth_version="1.0",'
            f'oauth_signature="{requests.utils.quote(signature_b64, safe="")}"'
        )

    def _get_headers(self, method: str, url: str) -> dict:
        return {
            "Authorization": self._build_auth_header(method, url),
            "Content-Type": "application/json",
            "Prefer": "transient",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        self.logger.info("Validating NetSuite provider scopes")
        url = f"{self._get_base_url()}/supportcase?limit=1"
        try:
            response = requests.get(
                url,
                headers=self._get_headers("GET", url),
                timeout=15,
            )
            if response.ok:
                return {"authenticated": True, "support_cases_read": True}
            else:
                msg = f"HTTP {response.status_code}: {response.text[:200]}"
                return {"authenticated": msg, "support_cases_read": False}
        except Exception as e:
            return {"authenticated": str(e), "support_cases_read": False}

    def _get_alerts(self) -> list[AlertDto]:
        """Pull open support cases from NetSuite."""
        self.logger.info("Fetching support cases from NetSuite")
        alerts = []
        offset = 0
        limit = 100

        while True:
            url = f"{self._get_base_url()}/supportcase?limit={limit}&offset={offset}"
            try:
                response = requests.get(
                    url,
                    headers=self._get_headers("GET", url),
                    timeout=20,
                )
                response.raise_for_status()
            except requests.RequestException as e:
                self.logger.error("Error fetching NetSuite support cases", extra={"error": str(e)})
                raise

            data = response.json()
            items = data.get("items", [])

            for case in items:
                alerts.append(self._map_case_to_alert(case))

            if len(items) < limit:
                break
            offset += limit

        return alerts

    def _map_case_to_alert(self, case: dict) -> AlertDto:
        status_str = case.get("status", {}).get("refName", "Open") if isinstance(case.get("status"), dict) else str(case.get("status", "Open"))
        severity_str = case.get("priority", {}).get("refName", "3 - Medium") if isinstance(case.get("priority"), dict) else "3 - Medium"

        return AlertDto(
            id=str(case.get("id", "")),
            fingerprint=str(case.get("id", "")),
            name=case.get("title", "NetSuite Support Case"),
            description=case.get("incomingMessage", ""),
            status=self.STATUS_MAP.get(status_str, AlertStatus.FIRING),
            severity=self.SEVERITY_MAP.get(severity_str, AlertSeverity.WARNING),
            lastReceived=case.get("lastModifiedDate", datetime.utcnow().isoformat()),
            url=f"https://{self.authentication_config.account_id}.app.netsuite.com/app/crm/support/supportcase.nl?id={case.get('id', '')}",
            source=["netsuite"],
        )

    def _notify(
        self,
        title: str = "",
        description: str = "",
        priority: str = "3 - Medium",
        **kwargs,
    ) -> dict:
        """Create a support case in NetSuite."""
        self.logger.info("Creating NetSuite support case")
        url = f"{self._get_base_url()}/supportcase"
        payload = {
            "title": title,
            "incomingMessage": description,
        }
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers("POST", url),
                timeout=20,
            )
            response.raise_for_status()
            location = response.headers.get("Location", "")
            case_id = location.split("/")[-1] if location else ""
            self.logger.info("NetSuite support case created", extra={"case_id": case_id})
            return {"case_id": case_id, "location": location}
        except requests.RequestException as e:
            self.logger.error("Failed to create NetSuite support case", extra={"error": str(e)})
            raise


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    config = ProviderConfig(
        description="NetSuite Provider",
        authentication={
            "account_id": os.environ["NETSUITE_ACCOUNT_ID"],
            "consumer_key": os.environ["NETSUITE_CONSUMER_KEY"],
            "consumer_secret": os.environ["NETSUITE_CONSUMER_SECRET"],
            "token_id": os.environ["NETSUITE_TOKEN_ID"],
            "token_secret": os.environ["NETSUITE_TOKEN_SECRET"],
        },
    )

    provider = NetsuiteProvider(context_manager, "netsuite", config)
    print(provider.validate_scopes())
    print(provider._get_alerts())
