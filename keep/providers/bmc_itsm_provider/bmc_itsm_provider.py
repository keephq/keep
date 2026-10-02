"""
BmcItsmProvider is a class that implements the BaseProvider interface for BMC Helix ITSM.

Supports:
- Pulling incidents from BMC Helix ITSM
- Creating incidents via the simplified REST API
- Pulling topology data (CI/CBD relationships)
- Querying individual incidents
"""

import dataclasses
import logging
import typing

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.topology import TopologyServiceInDto
from keep.api.models.incident import IncidentDto, IncidentSeverity, IncidentStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import (
    BaseIncidentProvider,
    BaseTopologyProvider,
    BaseProvider,
    ProviderHealthMixin,
)
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod
from keep.validation.fields import HttpsUrl

logger = logging.getLogger(__name__)


# BMC Helix ITSM severity mapping
BMC_SEVERITY_MAP = {
    "Critical": IncidentSeverity.CRITICAL,
    "High": IncidentSeverity.HIGH,
    "Medium": IncidentSeverity.MEDIUM,
    "Low": IncidentSeverity.LOW,
    "1-Critical": IncidentSeverity.CRITICAL,
    "2-High": IncidentSeverity.HIGH,
    "3-Medium": IncidentSeverity.MEDIUM,
    "4-Low": IncidentSeverity.LOW,
}

# BMC status mapping
BMC_STATUS_MAP = {
    "New": IncidentStatus.OPEN,
    "Assigned": IncidentStatus.OPEN,
    "In Progress": IncidentStatus.OPEN,
    "Pending": IncidentStatus.OPEN,
    "Resolved": IncidentStatus.RESOLVED,
    "Closed": IncidentStatus.RESOLVED,
}


@pydantic.dataclasses.dataclass
class BmcItsmProviderAuthConfig:
    """BMC Helix ITSM authentication configuration."""

    bmc_base_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "The base URL of the BMC Helix ITSM instance",
            "sensitive": False,
            "hint": "https://your-instance.onbmc.com",
            "validation": "https_url",
        }
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The username for BMC Helix ITSM",
            "sensitive": False,
        }
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The password for BMC Helix ITSM",
            "sensitive": True,
        }
    )

    # Optional: OAuth token (alternative to username/password)
    auth_token: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "OAuth token for authentication (alternative to username/password)",
            "sensitive": True,
        },
        default="",
    )

    # Optional: Company field for multi-tenant environments
    company: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Company name (required for multi-tenant BMC Helix environments)",
            "sensitive": False,
        },
        default="",
    )


class BmcItsmProvider(
    BaseTopologyProvider, BaseIncidentProvider, ProviderHealthMixin
):
    """Pull incidents and topology from BMC Helix ITSM, and create incidents."""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="incidents_read",
            description="Read incidents from BMC Helix ITSM",
            mandatory=True,
        ),
        ProviderScope(
            name="incidents_write",
            description="Create and update incidents in BMC Helix ITSM",
            mandatory=False,
        ),
        ProviderScope(
            name="topology_read",
            description="Read topology/CI data from BMC Helix ITSM",
            mandatory=False,
        ),
    ]

    PROVIDER_METHODS: list[ProviderMethod] = [
        ProviderMethod(
            name="create_incident",
            description="Create a new incident in BMC Helix ITSM",
            func_name="create_incident",
            scopes=["incidents_write"],
        ),
        ProviderMethod(
            name="get_incident",
            description="Get a specific incident by ID",
            func_name="get_incident",
            scopes=["incidents_read"],
        ),
        ProviderMethod(
            name="search_incidents",
            description="Search incidents with a query",
            func_name="search_incidents",
            scopes=["incidents_read"],
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def _get_auth(self) -> HTTPBasicAuth | None:
        """Get authentication object."""
        if self.authentication_config.auth_token:
            return None  # Will use token in headers
        return HTTPBasicAuth(
            self.authentication_config.username,
            self.authentication_config.password,
        )

    def _get_headers(self) -> dict:
        """Get request headers."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.authentication_config.auth_token:
            headers["Authorization"] = f"Bearer {self.authentication_config.auth_token}"
        return headers

    @property
    def _base_url(self) -> str:
        """Get base URL without trailing slash."""
        return str(self.authentication_config.bmc_base_url).rstrip("/")

    def validate_config(self):
        """Validate provider configuration."""
        if not self.authentication_config.bmc_base_url:
            raise ProviderException("BMC Helix ITSM base URL is required")
        if not self.authentication_config.auth_token:
            if not self.authentication_config.username or not self.authentication_config.password:
                raise ProviderException(
                    "Either auth_token or username/password is required"
                )

    def validate_scopes(self) -> dict:
        """Validate provider scopes by making a test API call."""
        scopes = {}
        try:
            # Try to list incidents (read scope)
            url = f"{self._base_url}/api/com.bmc.dsm.itsm.itsm-rest-api/incident"
            params = {"limit": 1}
            response = requests.get(
                url,
                headers=self._get_headers(),
                auth=self._get_auth(),
                params=params,
                timeout=10,
            )
            scopes["incidents_read"] = response.status_code in (200, 201, 204)
        except Exception:
            scopes["incidents_read"] = False

        scopes["incidents_write"] = scopes["incidents_read"]  # Same auth
        scopes["topology_read"] = scopes["incidents_read"]
        return scopes

    # --- Incident Operations ---

    def _get_incidents(self) -> list[IncidentDto]:
        """Pull incidents from BMC Helix ITSM."""
        incidents = []
        try:
            # Use simplified REST API
            url = f"{self._base_url}/api/com.bmc.dsm.itsm.itsm-rest-api/incident"
            params = {"limit": 100}

            response = requests.get(
                url,
                headers=self._get_headers(),
                auth=self._get_auth(),
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            incident_list = data if isinstance(data, list) else data.get("values", data.get("incidents", []))

            for inc_data in incident_list:
                try:
                    incident = self._format_incident(inc_data)
                    incidents.append(incident)
                except Exception as e:
                    logger.warning(f"Failed to format incident: {e}")

        except Exception as e:
            logger.error(f"Failed to get incidents from BMC Helix ITSM: {e}")
            raise

        return incidents

    def _format_incident(self, incident: dict) -> IncidentDto:
        """Format a BMC incident into Keep's IncidentDto."""
        incident_id = incident.get("id", incident.get("incidentId", ""))
        summary = incident.get("summary", incident.get("Description", ""))
        description = incident.get("description", incident.get("Detailed_Description", ""))

        # Map severity
        priority_str = str(incident.get("priority", incident.get("Impact", "")))
        severity = BMC_SEVERITY_MAP.get(priority_str, IncidentSeverity.INFO)

        # Map status
        status_str = str(incident.get("status", incident.get("Status", "")))
        status = BMC_STATUS_MAP.get(status_str, IncidentStatus.OPEN)

        return IncidentDto(
            id=incident_id,
            name=summary,
            description=description,
            severity=severity,
            status=status,
            source="bmc_itsm",
            created_at=incident.get("createDate", ""),
            updated_at=incident.get("modifiedDate", ""),
            raw=incident,
        )

    def create_incident(
        self,
        summary: str,
        description: str = "",
        impact: str = "2-High",
        urgency: str = "2-High",
        reported_source: str = "Direct Input",
        service_type: str = "User Service Restoration",
        first_name: str = "",
        last_name: str = "",
        **kwargs,
    ) -> dict:
        """Create a new incident in BMC Helix ITSM.

        Uses the AR System REST API: POST /entry/HPD:IncidentInterfaceCreate
        """
        url = f"{self._base_url}/api/com.bmc.dsm.itsm.itsm-rest-api/incident"

        payload = {
            "summary": summary,
            "description": description or summary,
            "impact": impact,
            "urgency": urgency,
            "reportedSource": reported_source,
            "serviceType": service_type,
        }

        if first_name:
            payload["customer"] = {"firstName": first_name, "lastName": last_name}

        if self.authentication_config.company:
            payload["company"] = self.authentication_config.company

        # Merge any extra kwargs
        payload.update(kwargs)

        response = requests.post(
            url,
            json=payload,
            headers=self._get_headers(),
            auth=self._get_auth(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_incident(self, incident_id: str) -> dict:
        """Get a specific incident by ID."""
        url = f"{self._base_url}/api/com.bmc.dsm.itsm.itsm-rest-api/incident/{incident_id}"
        response = requests.get(
            url,
            headers=self._get_headers(),
            auth=self._get_auth(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def search_incidents(self, query: str, limit: int = 100) -> list[dict]:
        """Search incidents using a query string."""
        url = f"{self._base_url}/api/com.bmc.dsm.itsm.itsm-rest-api/incident"
        params = {"q": query, "limit": limit}
        response = requests.get(
            url,
            headers=self._get_headers(),
            auth=self._get_auth(),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else data.get("values", data.get("incidents", []))

    # --- Topology ---

    def pull_topology(self) -> tuple[list[TopologyServiceInDto], dict]:
        """Pull topology data from BMC Helix ITSM (CI/CBD relationships).

        Uses the BMC Helix CMDB REST API to get CIs and their relationships.
        """
        topology_services = []
        topology_edges = {}

        try:
            # Get CIs (Configuration Items) from BMC Helix CMDB
            url = f"{self._base_url}/api/com.bmc.dsm.itsm.itsm-rest-api/ci"
            params = {"limit": 500}

            response = requests.get(
                url,
                headers=self._get_headers(),
                auth=self._get_auth(),
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            ci_list = data if isinstance(data, list) else data.get("values", data.get("cis", []))

            for ci in ci_list:
                try:
                    service = TopologyServiceInDto(
                        id=ci.get("id", ci.get("ciId", "")),
                        name=ci.get("name", ci.get("displayName", "")),
                        type=ci.get("type", ci.get("classId", "")),
                    )
                    topology_services.append(service)
                except Exception as e:
                    logger.warning(f"Failed to format CI: {e}")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.info("BMC Helix CMDB API not available, skipping topology")
            else:
                logger.error(f"Failed to pull topology: {e}")
        except Exception as e:
            logger.error(f"Failed to pull topology: {e}")

        return topology_services, topology_edges

    # --- Alert formatting ---

    def _format_alert(self, event: dict) -> AlertDto:
        """Format a BMC event into Keep's AlertDto."""
        severity_str = str(event.get("priority", event.get("severity", "Medium")))
        severity_map = {
            "Critical": AlertSeverity.CRITICAL,
            "High": AlertSeverity.HIGH,
            "Medium": AlertSeverity.WARNING,
            "Low": AlertSeverity.INFO,
        }

        status_str = str(event.get("status", "New"))
        status_map = {
            "New": AlertStatus.FIRING,
            "Assigned": AlertStatus.FIRING,
            "Resolved": AlertStatus.RESOLVED,
            "Closed": AlertStatus.RESOLVED,
        }

        return AlertDto(
            id=event.get("id", event.get("incidentId", "")),
            name=event.get("summary", event.get("Description", "")),
            description=event.get("description", ""),
            severity=severity_map.get(severity_str, AlertSeverity.WARNING),
            status=status_map.get(status_str, AlertStatus.FIRING),
            source="bmc_itsm",
            raw=event,
        )

    # --- Query and Notify ---

    def _query(self, incident_id: str = None, **kwargs) -> dict | list[dict]:
        """Query incidents from BMC Helix ITSM."""
        if incident_id:
            return self.get_incident(incident_id)
        return self.search_incidents(kwargs.get("query", ""), kwargs.get("limit", 100))

    def _notify(self, summary: str = "", description: str = "", **kwargs) -> dict:
        """Create an incident in BMC Helix ITSM (used by workflows)."""
        return self.create_incident(
            summary=summary,
            description=description,
            **kwargs,
        )

    # --- Health Check ---

    def get_health(self) -> dict:
        """Check the health of the BMC Helix ITSM connection."""
        try:
            url = f"{self._base_url}/api/com.bmc.dsm.itsm.itsm-rest-api/incident"
            params = {"limit": 1}
            response = requests.get(
                url,
                headers=self._get_headers(),
                auth=self._get_auth(),
                params=params,
                timeout=10,
            )
            return {
                "healthy": response.status_code in (200, 201, 204),
                "status_code": response.status_code,
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    @classmethod
    def _extract_type(cls, event: dict) -> str | None:
        """Extract alert type from BMC event."""
        return event.get("type", "bmc-itsm-alert")


if __name__ == "__main__":
    # For local testing
    import os

    provider = BmcItsmProvider(
        context_manager=ContextManager(context_id="test"),
        provider_id="bmc-itsm-test",
        config=ProviderConfig(
            authentication={
                "bmc_base_url": os.environ.get("BMC_BASE_URL", ""),
                "username": os.environ.get("BMC_USERNAME", ""),
                "password": os.environ.get("BMC_PASSWORD", ""),
            }
        ),
    )

    # Test health check
    health = provider.get_health()
    print(f"Health: {health}")
