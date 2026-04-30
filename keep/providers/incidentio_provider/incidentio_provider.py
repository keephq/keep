"""
IncidentioProvider is a class that allows to pull incidents from incident.io.
"""

import dataclasses
import hashlib
import uuid
from datetime import datetime
from typing import List
from urllib.parse import urlencode, urljoin

import pydantic
import requests

from keep.api.models.db.incident import IncidentSeverity, IncidentStatus
from keep.api.models.incident import IncidentDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseIncidentProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class IncidentioProviderAuthConfig:
    """
    Incidentio authentication configuration.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "incident.io API Key",
            "hint": "Your incident.io API key from Settings > API Keys",
            "sensitive": True,
        },
    )


class IncidentioProvider(BaseIncidentProvider, ProviderHealthMixin):
    """Pull incidents from incident.io."""

    PROVIDER_DISPLAY_NAME = "incident.io"
    PROVIDER_CATEGORY = ["Incident Management"]
    PROVIDER_TAGS = ["incident"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authenticated",
            mandatory=True,
            alias="authenticated",
        ),
        ProviderScope(
            name="read_access",
            description="User has read access to incidents",
            mandatory=True,
            alias="can_read",
        ),
    ]

    # Map incident.io severities to Keep IncidentSeverity
    # incident.io severities: Critical, Major, Minor, etc.
    SEVERITIES_MAP = {
        "critical": IncidentSeverity.CRITICAL,
        "major": IncidentSeverity.HIGH,
        "moderate": IncidentSeverity.WARNING,
        "minor": IncidentSeverity.LOW,
        "info": IncidentSeverity.INFO,
        # Handle display names as well (case-insensitive matching)
        "high": IncidentSeverity.HIGH,
        "medium": IncidentSeverity.WARNING,
        "low": IncidentSeverity.LOW,
        "warning": IncidentSeverity.WARNING,
    }

    # Map incident.io status categories to Keep IncidentStatus
    # incident.io status categories: triage, active, post-incident, closed, etc.
    STATUS_MAP = {
        "triage": IncidentStatus.ACKNOWLEDGED,
        "active": IncidentStatus.FIRING,
        "live": IncidentStatus.FIRING,
        "post-incident": IncidentStatus.ACKNOWLEDGED,
        "learning": IncidentStatus.ACKNOWLEDGED,
        "closed": IncidentStatus.RESOLVED,
        "resolved": IncidentStatus.RESOLVED,
        "declined": IncidentStatus.RESOLVED,
        "merged": IncidentStatus.MERGED,
        "canceled": IncidentStatus.RESOLVED,
        "paused": IncidentStatus.ACKNOWLEDGED,
    }

    BASE_URL = "https://api.incident.io/v2/"

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
        Validates required configuration for Incidentio provider.
        """
        self.authentication_config = IncidentioProviderAuthConfig(
            **self.config.authentication
        )

    def _get_url(self, paths: List[str] = [], query_params: dict = None) -> str:
        """
        Helper method to build the url for incident.io API requests.

        Args:
            paths: List of path segments to append to base URL
            query_params: Optional query parameters

        Returns:
            Full URL string
        """
        path_str = "/".join(str(path) for path in paths)
        url = urljoin(self.BASE_URL, path_str)

        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        return url

    def _get_headers(self) -> dict:
        """
        Build headers for API requests.
        """
        return {
            "Authorization": f"Bearer {self.authentication_config.api_key}",
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate that the API key has the required scopes.
        """
        self.logger.info("Validating incident.io scopes...")
        try:
            response = requests.get(
                url=self._get_url(paths=["incidents"]),
                headers=self._get_headers(),
                params={"page_size": 1},
                timeout=10,
            )

            if response.ok:
                return {"authenticated": True, "read_access": True}
            else:
                self.logger.error(
                    f"Failed to validate scopes: {response.status_code}",
                    extra={"response": response.text},
                )
                return {
                    "authenticated": f"Unable to authenticate: {response.status_code}",
                    "read_access": False,
                }
        except Exception as e:
            self.logger.error(
                "Error validating incident.io scopes",
                extra={"exception": str(e)},
            )
            return {
                "authenticated": f"Unable to connect: {str(e)}",
                "read_access": False,
            }

    @staticmethod
    def _generate_incident_id(incident_id: str) -> uuid.UUID:
        """
        Generate a deterministic UUID from the incident.io incident ID.

        Args:
            incident_id: The original incident.io incident ID

        Returns:
            A UUID derived from the incident ID
        """
        md5 = hashlib.md5()
        md5.update(incident_id.encode("utf-8"))
        return uuid.UUID(md5.hexdigest())

    def _parse_timestamp(self, timestamp: str | None) -> datetime | None:
        """
        Parse an ISO8601 timestamp from incident.io API.

        Args:
            timestamp: ISO8601 formatted timestamp string

        Returns:
            datetime object or None if parsing fails
        """
        if not timestamp:
            return None
        try:
            # incident.io uses ISO8601 format with timezone
            # e.g., "2024-01-15T10:30:00.000Z" or "2024-01-15T10:30:00Z"
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            return datetime.fromisoformat(timestamp)
        except ValueError:
            self.logger.warning(f"Failed to parse timestamp: {timestamp}")
            return None

    def _map_severity(self, incident: dict) -> IncidentSeverity:
        """
        Map incident.io severity to Keep IncidentSeverity.

        Args:
            incident: The incident dict from incident.io API

        Returns:
            IncidentSeverity enum value
        """
        severity_obj = incident.get("severity", {})
        if not severity_obj:
            return IncidentSeverity.INFO

        # Try the severity name first (e.g., "Critical", "Major")
        severity_name = severity_obj.get("name", "").lower()
        if severity_name in self.SEVERITIES_MAP:
            return self.SEVERITIES_MAP[severity_name]

        # Fallback to a default based on rank if available
        rank = severity_obj.get("rank", 99)
        if rank <= 1:
            return IncidentSeverity.CRITICAL
        elif rank <= 2:
            return IncidentSeverity.HIGH
        elif rank <= 3:
            return IncidentSeverity.WARNING
        elif rank <= 4:
            return IncidentSeverity.LOW
        else:
            return IncidentSeverity.INFO

    def _map_status(self, incident: dict) -> IncidentStatus:
        """
        Map incident.io status to Keep IncidentStatus.

        Args:
            incident: The incident dict from incident.io API

        Returns:
            IncidentStatus enum value
        """
        status_obj = incident.get("incident_status", {})
        if not status_obj:
            return IncidentStatus.FIRING

        # Use the category for mapping (e.g., "triage", "active", "closed")
        category = status_obj.get("category", "").lower()
        if category in self.STATUS_MAP:
            return self.STATUS_MAP[category]

        # Fallback to status name
        name = status_obj.get("name", "").lower()
        if name in self.STATUS_MAP:
            return self.STATUS_MAP[name]

        return IncidentStatus.FIRING

    def _map_incident_to_dto(self, incident: dict) -> IncidentDto:
        """
        Map an incident.io incident to Keep IncidentDto.

        Args:
            incident: The incident dict from incident.io API

        Returns:
            IncidentDto object
        """
        incident_id = incident.get("id", "")
        keep_id = self._generate_incident_id(incident_id)

        # Parse timestamps
        created_at = self._parse_timestamp(incident.get("created_at"))
        updated_at = self._parse_timestamp(incident.get("updated_at"))
        closed_at = self._parse_timestamp(incident.get("closed_at"))

        # Get severity and status
        severity = self._map_severity(incident)
        status = self._map_status(incident)

        # Extract assignee information from incident roles
        assignees = []
        for role_assignment in incident.get("incident_role_assignments", []):
            assignee = role_assignment.get("assignee")
            if assignee:
                assignee_name = assignee.get("name") or assignee.get("email", "")
                if assignee_name:
                    assignees.append(assignee_name)

        assignee_str = ", ".join(assignees) if assignees else None

        # Extract services/functionalities affected
        services = []
        for functionality in incident.get("functionalities", []):
            service_name = functionality.get("name")
            if service_name:
                services.append(service_name)

        # Get alert sources from incident source
        alert_sources = ["incident.io"]
        
        # Build the incident URL
        permalink = incident.get("permalink", "")

        return IncidentDto(
            id=keep_id,
            user_generated_name=incident.get("name", "Untitled Incident"),
            user_summary=incident.get("summary", ""),
            status=status,
            severity=severity,
            creation_time=created_at,
            start_time=created_at,
            last_seen_time=updated_at,
            end_time=closed_at if status == IncidentStatus.RESOLVED else None,
            alerts_count=0,  # incident.io doesn't directly expose this
            alert_sources=alert_sources,
            services=services,
            is_predicted=False,
            is_candidate=False,
            assignee=assignee_str,
            fingerprint=incident_id,  # Use incident.io ID as fingerprint
            incident_type=incident.get("incident_type", {}).get("name", ""),
            # Store additional incident.io-specific data in enrichments
            url=permalink,
            external_id=incident_id,
            reference=incident.get("reference", ""),
            mode=incident.get("mode", ""),
        )

    def _get_incidents(self) -> list[IncidentDto]:
        """
        Fetch all incidents from incident.io.

        Returns:
            List of IncidentDto objects
        """
        self.logger.info("Fetching incidents from incident.io")

        incidents = []
        next_cursor = None

        while True:
            try:
                params = {"page_size": 100}
                if next_cursor:
                    params["after"] = next_cursor

                response = requests.get(
                    self._get_url(paths=["incidents"]),
                    headers=self._get_headers(),
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()

            except requests.RequestException as e:
                self.logger.error(
                    "Error fetching incidents from incident.io",
                    extra={"exception": str(e)},
                )
                raise e

            data = response.json()

            # Map each incident to IncidentDto
            for incident in data.get("incidents", []):
                try:
                    incident_dto = self._map_incident_to_dto(incident)
                    incidents.append(incident_dto)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to map incident {incident.get('id')}",
                        extra={"exception": str(e)},
                    )

            # Check for more pages
            pagination_meta = data.get("pagination_meta", {})
            next_cursor = pagination_meta.get("after")

            if not next_cursor:
                break

        self.logger.info(f"Fetched {len(incidents)} incidents from incident.io")
        return incidents

    def _query(self, incident_id: str, **kwargs) -> IncidentDto | None:
        """
        Query a specific incident from incident.io.

        Args:
            incident_id: The incident.io incident ID

        Returns:
            IncidentDto object or None if not found
        """
        self.logger.info(
            "Querying incident.io incident",
            extra={"incident_id": incident_id},
        )
        try:
            response = requests.get(
                url=self._get_url(paths=["incidents", incident_id]),
                headers=self._get_headers(),
                timeout=15,
            )

            if response.ok:
                data = response.json()
                incident = data.get("incident", {})
                return self._map_incident_to_dto(incident)
            else:
                self.logger.error(
                    f"Failed to fetch incident {incident_id}",
                    extra={"status_code": response.status_code},
                )
                return None

        except Exception as e:
            self.logger.error(
                f"Error querying incident {incident_id}",
                extra={"exception": str(e)},
            )
            raise e


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.getenv("INCIDENTIO_API_KEY")
    if not api_key:
        raise Exception("INCIDENTIO_API_KEY environment variable is required")

    config = ProviderConfig(
        description="incident.io Provider",
        authentication={"api_key": api_key},
    )

    provider = IncidentioProvider(
        context_manager,
        provider_id="incidentio_provider",
        config=config,
    )

    print("Validating scopes...")
    print(provider.validate_scopes())

    print("\nFetching incidents...")
    incidents = provider._get_incidents()
    for incident in incidents[:5]:  # Print first 5
        print(f"- {incident.user_generated_name} ({incident.status})")
