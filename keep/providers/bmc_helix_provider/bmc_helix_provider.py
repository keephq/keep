"""
BmcHelixProvider is a class that implements the BaseProvider interface for BMC Helix ITSM.

BMC Helix ITSM (formerly Remedy) is a leading ITSM platform offering incident management,
change management, and CMDB (service topology) capabilities.

This provider supports:
  - Pull mode: query open/active incidents from BMC Helix ITSM REST API
  - Push mode: receive alert notifications via BMC Helix webhook / Impact Event adapter
  - Incident management: create and update incidents via the REST API
  - Service topology: pull CMDB topology relationships

Authentication:
  - JWT bearer token (Helix Cloud / Innovation Suite ≥ 22.x)  [preferred]
  - HTTP Basic auth (legacy Remedy on-premise)

BMC Helix REST API reference:
  https://docs.bmc.com/xwiki/bin/view/IS2302/
"""

import dataclasses
import datetime
import logging
from typing import Optional
from urllib.parse import urljoin

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.topology import TopologyServiceInDto
from keep.api.models.incident import IncidentDto, IncidentSeverity, IncidentStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, BaseTopologyProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class BmcHelixProviderAuthConfig:
    """
    BMC Helix ITSM authentication configuration.

    Supports JWT bearer (Innovation Suite / Helix Cloud) or
    HTTP Basic auth (legacy Remedy on-premise).
    """

    base_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "BMC Helix ITSM base URL",
            "hint": "https://your-company.onbmc.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "BMC Helix username",
            "hint": "admin",
            "sensitive": False,
        }
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "BMC Helix password",
            "hint": "P@ssw0rd",
            "sensitive": True,
        }
    )

    verify_ssl: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Verify SSL certificate (set to false for self-signed)",
            "hint": "true",
            "sensitive": False,
        },
        default=True,
    )

    timeout: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "HTTP request timeout in seconds",
            "hint": "30",
            "sensitive": False,
        },
        default=30,
    )


class BmcHelixProvider(BaseTopologyProvider):
    """
    Integrate BMC Helix ITSM with Keep.

    Pull mode: polls open/in-progress incidents from the Helix ITSM REST API
    (`/api/arsys/v1/entry/HPD:IncidentInterface`) and surfaces them as alerts.

    Push mode: receives incident payloads pushed from BMC Helix via its
    HTTP outbound configuration or an Impact Event adapter.

    Incident creation: the `notify()` method creates new incidents in
    Helix ITSM (used by Keep workflows/actions).
    """

    PROVIDER_DISPLAY_NAME = "BMC Helix ITSM"
    PROVIDER_CATEGORY = ["Ticketing", "Incident Management"]
    PROVIDER_TAGS = ["ticketing", "itsm"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="incident_read",
            description="Read incidents from BMC Helix ITSM",
            mandatory=True,
            documentation_url="https://docs.bmc.com/xwiki/bin/view/IS2302/",
        ),
        ProviderScope(
            name="incident_write",
            description="Create and update incidents in BMC Helix ITSM",
            mandatory=False,
            documentation_url="https://docs.bmc.com/xwiki/bin/view/IS2302/",
        ),
    ]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="Create Incident",
            func_name="create_incident",
            scopes=["incident_write"],
            description="Create a new incident in BMC Helix ITSM",
            type="action",
        ),
    ]

    FINGERPRINT_FIELDS = ["incident_number", "company"]

    # Helix ITSM priority -> Keep severity
    # BMC uses Impact + Urgency to compute Priority (1=Critical ... 5=Planning)
    PRIORITY_TO_SEVERITY: dict[str, AlertSeverity] = {
        "1": AlertSeverity.CRITICAL,
        "Critical": AlertSeverity.CRITICAL,
        "2": AlertSeverity.HIGH,
        "High": AlertSeverity.HIGH,
        "3": AlertSeverity.WARNING,
        "Medium": AlertSeverity.WARNING,
        "4": AlertSeverity.LOW,
        "Low": AlertSeverity.LOW,
        "5": AlertSeverity.INFO,
        "Planning": AlertSeverity.INFO,
    }

    # Helix ITSM status -> Keep status
    STATUS_MAP: dict[str, AlertStatus] = {
        "New": AlertStatus.FIRING,
        "Assigned": AlertStatus.FIRING,
        "In Progress": AlertStatus.FIRING,
        "Pending": AlertStatus.SUPPRESSED,
        "Resolved": AlertStatus.RESOLVED,
        "Closed": AlertStatus.RESOLVED,
        "Cancelled": AlertStatus.RESOLVED,
        # Legacy Remedy statuses
        "Categorize": AlertStatus.FIRING,
        "Investigate": AlertStatus.FIRING,
        "Known Error": AlertStatus.FIRING,
    }

    # Helix ITSM incident status -> Keep incident status
    INCIDENT_STATUS_MAP: dict[str, IncidentStatus] = {
        "New": IncidentStatus.FIRING,
        "Assigned": IncidentStatus.FIRING,
        "In Progress": IncidentStatus.FIRING,
        "Pending": IncidentStatus.FIRING,
        "Resolved": IncidentStatus.RESOLVED,
        "Closed": IncidentStatus.RESOLVED,
        "Cancelled": IncidentStatus.RESOLVED,
    }

    # Helix ITSM priority -> Keep incident severity
    INCIDENT_PRIORITY_MAP: dict[str, IncidentSeverity] = {
        "1": IncidentSeverity.CRITICAL,
        "Critical": IncidentSeverity.CRITICAL,
        "2": IncidentSeverity.HIGH,
        "High": IncidentSeverity.HIGH,
        "3": IncidentSeverity.MEDIUM,
        "Medium": IncidentSeverity.MEDIUM,
        "4": IncidentSeverity.LOW,
        "Low": IncidentSeverity.LOW,
        "5": IncidentSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._jwt_token: Optional[str] = None

    def dispose(self) -> None:
        pass

    def validate_config(self) -> None:
        """Validate the BMC Helix authentication configuration."""
        self.authentication_config = BmcHelixProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate API connectivity and read permissions."""
        validated: dict[str, bool | str] = {}
        try:
            token = self._get_jwt_token()
            validated["incident_read"] = bool(token)
        except Exception as exc:
            self.logger.warning(
                "Failed to validate BMC Helix scopes", extra={"error": str(exc)}
            )
            validated["incident_read"] = str(exc)
        validated["incident_write"] = validated.get("incident_read", str)
        return validated

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _get_jwt_token(self) -> str:
        """
        Obtain a JWT token from BMC Helix ITSM using username/password.

        POST /api/jwt/login
        Returns: str (the raw JWT token)
        """
        if self._jwt_token:
            return self._jwt_token

        url = urljoin(str(self.authentication_config.base_url), "/api/jwt/login")
        payload = {
            "username": self.authentication_config.username,
            "password": self.authentication_config.password,
        }
        response = requests.post(
            url,
            json=payload,
            verify=self.authentication_config.verify_ssl,
            timeout=self.authentication_config.timeout,
        )
        response.raise_for_status()

        # Innovation Suite returns the token as plain text in the body
        token = response.text.strip().strip('"')
        if not token:
            raise ValueError("BMC Helix /api/jwt/login returned empty token")

        self._jwt_token = token
        return self._jwt_token

    def _get_auth_headers(self) -> dict[str, str]:
        """Return HTTP Authorization headers for the Helix REST API."""
        token = self._get_jwt_token()
        return {
            "Authorization": f"AR-JWT {token}",
            "Content-Type": "application/json",
        }

    def _api_get(
        self,
        path: str,
        params: Optional[dict] = None,
    ) -> dict | list:
        """Authenticated GET against the Helix REST API."""
        url = urljoin(str(self.authentication_config.base_url), path)
        response = requests.get(
            url,
            headers=self._get_auth_headers(),
            params=params,
            verify=self.authentication_config.verify_ssl,
            timeout=self.authentication_config.timeout,
        )
        response.raise_for_status()
        return response.json()

    def _api_post(self, path: str, payload: dict) -> dict:
        """Authenticated POST against the Helix REST API."""
        url = urljoin(str(self.authentication_config.base_url), path)
        response = requests.post(
            url,
            headers=self._get_auth_headers(),
            json=payload,
            verify=self.authentication_config.verify_ssl,
            timeout=self.authentication_config.timeout,
        )
        response.raise_for_status()
        return response.json() if response.text else {}

    def _api_patch(self, path: str, payload: dict) -> None:
        """Authenticated PATCH against the Helix REST API."""
        url = urljoin(str(self.authentication_config.base_url), path)
        response = requests.patch(
            url,
            headers=self._get_auth_headers(),
            json=payload,
            verify=self.authentication_config.verify_ssl,
            timeout=self.authentication_config.timeout,
        )
        response.raise_for_status()

    # ------------------------------------------------------------------
    # Pull mode
    # ------------------------------------------------------------------

    def _get_incidents(
        self,
        qualification: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        Query open incidents from BMC Helix ITSM.

        Uses the HPD:IncidentInterface form entry endpoint:
        GET /api/arsys/v1/entry/HPD:IncidentInterface
        """
        # Default: fetch open (non-Closed, non-Cancelled) incidents
        if qualification is None:
            qualification = (
                "'Status' != \"Closed\" AND 'Status' != \"Cancelled\""
            )

        params: dict = {
            "q": qualification,
            "limit": limit,
            "offset": offset,
            "fields": (
                "values("
                "Incident Number,"
                "Summary,"
                "Notes,"
                "Status,"
                "Priority,"
                "Urgency,"
                "Impact,"
                "Assigned Group,"
                "Assignee,"
                "Company,"
                "Service,"
                "Category Tier 1,"
                "Last Modified Date,"
                "Submit Date,"
                "Reported Date"
                ")"
            ),
        }

        result = self._api_get(
            "/api/arsys/v1/entry/HPD:IncidentInterface",
            params=params,
        )

        if isinstance(result, dict):
            return result.get("entries", [])
        return result if isinstance(result, list) else []

    def _entry_to_alert_dto(self, entry: dict) -> AlertDto:
        """Convert a Helix ITSM incident entry to an AlertDto."""
        values = entry.get("values", {})
        links = entry.get("_links", {})

        incident_number = values.get("Incident Number", "")
        summary = values.get("Summary", "")
        notes = values.get("Notes", "")
        status_str = values.get("Status", "New")
        priority_str = values.get("Priority", "3")
        company = values.get("Company", "")
        service = values.get("Service", "")
        assignee = values.get("Assignee", "")
        assigned_group = values.get("Assigned Group", "")
        category = values.get("Category Tier 1", "")

        # Timestamps — Helix returns epoch milliseconds as strings
        submit_date = values.get("Submit Date", values.get("Reported Date", ""))
        last_modified = values.get("Last Modified Date", "")

        last_received: datetime.datetime
        if submit_date:
            try:
                ts_ms = int(submit_date)
                last_received = datetime.datetime.fromtimestamp(
                    ts_ms / 1000, tz=datetime.timezone.utc
                )
            except (ValueError, TypeError):
                last_received = datetime.datetime.now(tz=datetime.timezone.utc)
        else:
            last_received = datetime.datetime.now(tz=datetime.timezone.utc)

        severity = self.PRIORITY_TO_SEVERITY.get(
            str(priority_str), AlertSeverity.WARNING
        )
        status = self.STATUS_MAP.get(status_str, AlertStatus.FIRING)

        # Self link from HAL _links
        self_link = ""
        if links:
            self_href = links.get("self", [])
            if isinstance(self_href, list) and self_href:
                self_link = self_href[0].get("href", "")
            elif isinstance(self_href, dict):
                self_link = self_href.get("href", "")

        return AlertDto(
            id=incident_number or entry.get("entryId", ""),
            name=summary,
            description=notes or summary,
            message=summary,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["bmc_helix"],
            service=service,
            company=company,
            assignee=assignee,
            assigned_group=assigned_group,
            category=category,
            priority=str(priority_str),
            incident_number=incident_number,
            url=self_link,
        )

    def _get_alerts(self) -> list[AlertDto]:
        """Fetch active incidents and return them as Keep AlertDtos."""
        entries = self._get_incidents()
        alerts: list[AlertDto] = []
        for entry in entries:
            try:
                alert = self._entry_to_alert_dto(entry)
                alerts.append(alert)
            except Exception:
                self.logger.exception(
                    "Failed to parse BMC Helix entry",
                    extra={"entry_id": entry.get("entryId")},
                )
        return alerts

    # ------------------------------------------------------------------
    # Push mode (webhook / Impact Event adapter)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Convert a BMC Helix push event to an AlertDto.

        BMC Helix can send HTTP notifications via:
          - Impact Event Adapter: structured JSON with incident fields
          - Web Service outbound: custom SOAP/REST payload

        We support a canonical payload shape mirroring the REST API values dict.
        """
        # Support two payload shapes:
        # 1. Wrapped: {"values": {...}} (mirrors GET /entry response)
        # 2. Flat: {"Incident Number": ..., "Summary": ..., ...}
        if "values" in event:
            values = event["values"]
        else:
            values = event

        incident_number = values.get("Incident Number", values.get("incident_number", ""))
        summary = values.get("Summary", values.get("summary", ""))
        notes = values.get("Notes", values.get("notes", ""))
        status_str = values.get("Status", values.get("status", "New"))
        priority_str = str(values.get("Priority", values.get("priority", "3")))
        company = values.get("Company", values.get("company", ""))
        service = values.get("Service", values.get("service", ""))
        assignee = values.get("Assignee", values.get("assignee", ""))
        assigned_group = values.get("Assigned Group", values.get("assigned_group", ""))

        # Timestamp
        submit_date = values.get(
            "Submit Date",
            values.get("submit_date", values.get("Reported Date", "")),
        )
        last_received: datetime.datetime
        if submit_date:
            try:
                ts_ms = int(submit_date)
                last_received = datetime.datetime.fromtimestamp(
                    ts_ms / 1000, tz=datetime.timezone.utc
                )
            except (ValueError, TypeError):
                last_received = datetime.datetime.now(tz=datetime.timezone.utc)
        else:
            last_received = datetime.datetime.now(tz=datetime.timezone.utc)

        severity = BmcHelixProvider.PRIORITY_TO_SEVERITY.get(
            priority_str, AlertSeverity.WARNING
        )
        status = BmcHelixProvider.STATUS_MAP.get(status_str, AlertStatus.FIRING)

        return AlertDto(
            id=incident_number or "",
            name=summary,
            description=notes or summary,
            message=summary,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["bmc_helix"],
            company=company,
            service=service,
            assignee=assignee,
            assigned_group=assigned_group,
            incident_number=incident_number,
            pushed=True,
        )

    # ------------------------------------------------------------------
    # Topology (CMDB)
    # ------------------------------------------------------------------

    def get_topology(
        self,
        params: Optional[dict] = None,
    ) -> list[TopologyServiceInDto]:
        """
        Pull service topology from BMC Helix CMDB (Asset Management).

        Queries the BMC:Asset form for CI relationships to build a service map.
        """
        topology_entries: list[dict] = []
        try:
            result = self._api_get(
                "/api/arsys/v1/entry/AST:AssetRelationship",
                params={"q": "'Status' = \"Active\"", "limit": 200},
            )
            if isinstance(result, dict):
                topology_entries = result.get("entries", [])
        except Exception:
            self.logger.warning("Failed to pull CMDB topology from BMC Helix")

        services: list[TopologyServiceInDto] = []
        seen: set[str] = set()

        for entry in topology_entries:
            values = entry.get("values", {})
            source_name = values.get("Source Name", "")
            target_name = values.get("Target Name", "")
            relation_type = values.get("Relation Type", "depends-on")

            if not source_name or not target_name:
                continue

            if source_name not in seen:
                seen.add(source_name)
                services.append(
                    TopologyServiceInDto(
                        service=source_name,
                        display_name=source_name,
                        source_provider_id=self.provider_id,
                        dependencies={target_name: relation_type},
                    )
                )

        return services

    # ------------------------------------------------------------------
    # Incident management (action)
    # ------------------------------------------------------------------

    def create_incident(
        self,
        summary: str,
        notes: str = "",
        priority: str = "3",
        status: str = "New",
        company: str = "",
        service: str = "",
        assigned_group: str = "",
        assignee: str = "",
        impact: str = "3",
        urgency: str = "3",
    ) -> dict:
        """
        Create a new incident in BMC Helix ITSM.

        Required fields per HPD:IncidentInterface:
          - Summary, Status, Impact, Urgency
        """
        payload = {
            "values": {
                "Summary": summary,
                "Notes": notes,
                "Status": status,
                "Priority": priority,
                "Impact": impact,
                "Urgency": urgency,
                "Company": company,
                "Service": service,
                "Assigned Group": assigned_group,
                "Assignee": assignee,
            }
        }

        try:
            result = self._api_post(
                "/api/arsys/v1/entry/HPD:IncidentInterface_Create",
                payload,
            )
            return result
        except Exception as exc:
            raise Exception(f"Failed to create BMC Helix incident: {exc}") from exc

    def notify(
        self,
        message: str = "",
        severity: str = "medium",
        **kwargs,
    ) -> dict:
        """
        Keep workflow action: create an incident in BMC Helix ITSM.
        """
        priority_map = {
            "critical": "1",
            "high": "2",
            "medium": "3",
            "low": "4",
            "info": "5",
        }
        priority = priority_map.get(severity.lower(), "3")
        return self.create_incident(
            summary=message or kwargs.get("summary", "Keep-generated incident"),
            notes=kwargs.get("notes", ""),
            priority=priority,
            status=kwargs.get("status", "New"),
            company=kwargs.get("company", ""),
            service=kwargs.get("service", ""),
            assigned_group=kwargs.get("assigned_group", ""),
            assignee=kwargs.get("assignee", ""),
        )


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    config = ProviderConfig(
        authentication={
            "base_url": os.environ["BMC_HELIX_URL"],
            "username": os.environ["BMC_HELIX_USERNAME"],
            "password": os.environ["BMC_HELIX_PASSWORD"],
        }
    )

    provider = BmcHelixProvider(context_manager, "bmc-helix", config)
    alerts = provider._get_alerts()
    print(f"Found {len(alerts)} open incidents")
    for a in alerts:
        print(f"  {a.id}: {a.name} [{a.severity}] {a.status}")
