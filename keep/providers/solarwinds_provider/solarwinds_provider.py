"""
SolarwindsProvider pulls active alerts from a SolarWinds Orion / NPM deployment
via the SolarWinds Information Service (SWIS) REST endpoint.

Reference (SolarWinds): https://github.com/solarwinds/OrionSDK/wiki/REST
Query surface: SWQL against `Orion.AlertActive` (and joined entities) returns
the live set of firing alerts. Resolved/historical alerts live in
`Orion.AlertHistory` and are out of scope for the "current alerts" use-case.
"""

import dataclasses
import datetime
import urllib.parse

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """Auth + endpoint for an Orion SWIS deployment."""

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": (
                "SolarWinds Orion server base URL, typically https://<host>:17774. "
                "The provider appends /SolarWinds/InformationService/v3/Json/Query."
            ),
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds user (read access to Orion.AlertActive)",
            "sensitive": False,
        },
        default=None,
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds password",
            "sensitive": True,
        },
        default=None,
    )

    verify_ssl: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": (
                "Verify TLS certificates. Many Orion installs use self-signed certs; "
                "set false when that's the case."
            ),
            "sensitive": False,
        },
        default=True,
    )


class SolarwindsProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User can query Orion.AlertActive via SWIS",
        ),
    ]

    # SolarWinds severity is an integer 0..3 on `Orion.AlertConfigurations.Severity`.
    # Mapping below mirrors the SolarWinds UI: Notice / Info / Warning / Critical / Serious.
    # See https://thwack.solarwinds.com/groups/orion-platform-product-blog/blog/2017/09/13/whats-new-in-the-orion-platform-201724-alerts
    SEVERITY_MAP = {
        0: AlertSeverity.INFO,        # Informational
        1: AlertSeverity.INFO,        # Notice
        2: AlertSeverity.WARNING,     # Warning
        3: AlertSeverity.CRITICAL,    # Critical
        4: AlertSeverity.CRITICAL,    # Serious — same destination, just amplified
    }

    # Anything that surfaces in Orion.AlertActive is firing. Once acknowledged
    # the row still exists in AlertActive but with AcknowledgedDateTime populated.
    @classmethod
    def _status_from_row(cls, row: dict) -> AlertStatus:
        if row.get("AcknowledgedDateTime"):
            return AlertStatus.ACKNOWLEDGED
        return AlertStatus.FIRING

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def __query_url(self) -> str:
        base = str(self.authentication_config.host_url).rstrip("/")
        return f"{base}/SolarWinds/InformationService/v3/Json/Query"

    def __auth(self) -> HTTPBasicAuth:
        return HTTPBasicAuth(
            self.authentication_config.username,
            self.authentication_config.password,
        )

    def __swql_query(self, query: str) -> list[dict]:
        """Execute a SWQL query and return the `results` array as a list of dicts."""
        url = self.__query_url()
        try:
            response = requests.get(
                url,
                params={"query": query},
                auth=self.__auth(),
                verify=self.authentication_config.verify_ssl,
                timeout=30,
                headers={"Content-Type": "application/json"},
            )
        except requests.RequestException as e:
            raise ProviderException(
                f"SolarWinds SWIS request failed: {e}"
            ) from e
        if not response.ok:
            raise ProviderException(
                f"SolarWinds SWIS responded {response.status_code}: {response.text[:300]}"
            )
        try:
            return response.json().get("results", [])
        except ValueError as e:
            raise ProviderException(
                f"SolarWinds SWIS returned non-JSON: {e}"
            ) from e

    def validate_scopes(self) -> dict[str, bool | str]:
        """Verify the credentials by hitting a cheap SWIS query."""
        try:
            # Single-row probe; counts only.
            self.__swql_query("SELECT TOP 1 AlertObjectID FROM Orion.AlertActive")
            return {"authenticated": True}
        except Exception as e:
            return {"authenticated": f"Error validating scopes: {e}"}

    def _get_alerts(self) -> list[AlertDto]:
        """Fetch all currently-firing alerts from `Orion.AlertActive`."""
        # Joining AlertConfigurations gives us human-readable AlertName + Severity.
        swql = (
            "SELECT "
            " ac.AlertObjectID AS AlertObjectID, "
            " ao.AlertActiveID AS AlertActiveID, "
            " ac.Name AS Name, "
            " ac.Severity AS Severity, "
            " ac.Description AS Description, "
            " ao.TriggeredDateTime AS TriggeredDateTime, "
            " ao.AcknowledgedDateTime AS AcknowledgedDateTime, "
            " ao.EntityCaption AS EntityCaption, "
            " ao.EntityType AS EntityType, "
            " ao.RelatedNodeCaption AS RelatedNodeCaption, "
            " ao.AlertNote AS AlertNote "
            "FROM Orion.AlertActive ao "
            "LEFT JOIN Orion.AlertConfigurations ac "
            " ON ao.AlertObjectID = ac.AlertObjectID"
        )
        rows = self.__swql_query(swql)
        alerts: list[AlertDto] = []
        for row in rows:
            try:
                alerts.append(self._row_to_alert(row))
            except Exception as e:  # one bad row shouldn't drop the rest
                self.logger.warning(
                    "SolarWinds: skipping alert row due to parse error: %s", e
                )
        return alerts

    def _row_to_alert(self, row: dict) -> AlertDto:
        severity_int = row.get("Severity")
        severity = self.SEVERITY_MAP.get(
            severity_int if isinstance(severity_int, int) else -1,
            AlertSeverity.INFO,
        )
        triggered = row.get("TriggeredDateTime")
        if isinstance(triggered, str):
            last_received = triggered
        elif isinstance(triggered, (int, float)):
            last_received = datetime.datetime.fromtimestamp(triggered).isoformat()
        else:
            last_received = datetime.datetime.utcnow().isoformat()

        entity_caption = row.get("EntityCaption") or row.get("RelatedNodeCaption") or ""
        name = row.get("Name") or f"SolarWinds alert {row.get('AlertActiveID', '')}"
        description = row.get("Description") or row.get("AlertNote") or ""

        return AlertDto(
            id=str(row.get("AlertActiveID") or row.get("AlertObjectID") or ""),
            name=name,
            description=description,
            severity=severity,
            status=self._status_from_row(row),
            lastReceived=last_received,
            source=["solarwinds"],
            entity_caption=entity_caption,
            entity_type=row.get("EntityType"),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    host_url = os.environ.get("SOLARWINDS_HOST_URL")
    username = os.environ.get("SOLARWINDS_USER")
    password = os.environ.get("SOLARWINDS_PASS")

    if not host_url or not username or not password:
        raise ProviderException(
            "Set SOLARWINDS_HOST_URL, SOLARWINDS_USER, SOLARWINDS_PASS to smoke-test."
        )

    config = ProviderConfig(
        description="SolarWinds Provider",
        authentication={
            "host_url": host_url,
            "username": username,
            "password": password,
            "verify_ssl": os.environ.get("SOLARWINDS_VERIFY_SSL", "true").lower()
            != "false",
        },
    )
    provider = SolarwindsProvider(
        context_manager, provider_id="solarwinds", config=config
    )
    alerts = provider._get_alerts()
    print(f"Fetched {len(alerts)} SolarWinds alert(s)")
    for a in alerts[:5]:
        print(" -", a)
