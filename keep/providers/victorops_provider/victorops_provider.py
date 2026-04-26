"""
VictorOpsProvider is a class that integrates with Splunk On-Call (formerly VictorOps).
Splunk On-Call is an incident management platform that routes and escalates alerts to
on-call teams. This provider polls the REST API for active incidents and accepts
inbound webhook payloads from alert sources routed through VictorOps.
"""

import dataclasses
import datetime
from typing import List

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class VictorOpsProviderAuthConfig:
    """
    VictorOpsProviderAuthConfig holds credentials for the Splunk On-Call (VictorOps) REST API.
    """

    api_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Splunk On-Call API ID",
            "hint": "Found in Splunk On-Call portal → Integrations → API",
            "sensitive": False,
        },
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Splunk On-Call API Key",
            "hint": "Found in Splunk On-Call portal → Integrations → API (alongside the API ID)",
            "sensitive": True,
        },
    )

    organization_slug: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Your Splunk On-Call organization slug",
            "hint": "The URL slug for your org — visible in the Splunk On-Call URL: app.victorops.com/client/<slug>",
            "sensitive": False,
        },
    )


class VictorOpsProvider(BaseProvider):
    """Integrate with Splunk On-Call (VictorOps) to receive and route incident alerts."""

    PROVIDER_DISPLAY_NAME = "Splunk On-Call (VictorOps)"
    PROVIDER_TAGS = ["alert", "incident-management"]
    PROVIDER_CATEGORY = ["Incident Management"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated with the Splunk On-Call REST API",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    # VictorOps entity states and severity values
    ENTITY_STATE_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "WARNING": AlertSeverity.WARNING,
        "INFO": AlertSeverity.INFO,
        "UNKNOWN": AlertSeverity.WARNING,
    }

    INCIDENT_STATUS_MAP = {
        "TRIGGERED": AlertStatus.FIRING,
        "ACKNOWLEDGED": AlertStatus.ACKNOWLEDGED,
        "RESOLVED": AlertStatus.RESOLVED,
    }

    _BASE_URL = "https://api.victorops.com/api-public/v1"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = VictorOpsProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self) -> dict:
        return {
            "X-VO-Api-Id": self.authentication_config.api_id,
            "X-VO-Api-Key": self.authentication_config.api_key,
            "Accept": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        try:
            resp = requests.get(
                f"{self._BASE_URL}/user",
                headers=self.__get_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                scopes["authenticated"] = True
            elif resp.status_code == 401:
                scopes["authenticated"] = "Invalid API ID or API Key"
            elif resp.status_code == 403:
                scopes["authenticated"] = "Forbidden — check your organization permissions"
            else:
                scopes["authenticated"] = (
                    f"Unexpected status code: {resp.status_code}"
                )
        except Exception as e:
            self.logger.error("Error validating Splunk On-Call scopes: %s", e)
            scopes["authenticated"] = str(e)
        return scopes

    def __get_active_incidents(self) -> List[AlertDto]:
        """
        Fetch active (TRIGGERED + ACKNOWLEDGED) incidents from the Splunk On-Call REST API.
        """
        try:
            resp = requests.get(
                f"{self._BASE_URL}/incidents",
                headers=self.__get_headers(),
                timeout=15,
            )

            if not resp.ok:
                self.logger.error(
                    "Failed to fetch incidents from Splunk On-Call: %s %s",
                    resp.status_code,
                    resp.text,
                )
                return []

            data = resp.json()
            incidents = data.get("incidents", [])

            alerts = []
            for incident in incidents:
                incident_number = str(incident.get("incidentNumber", ""))
                alert_count = incident.get("alertCount", 0)
                current_phase = incident.get("currentPhase", "TRIGGERED").upper()
                start_time_ms = incident.get("startTime", 0)
                entity_display_name = incident.get("entityDisplayName", "")
                entity_id = incident.get("entityId", incident_number)
                service = incident.get("service", "")
                teams = incident.get("teams", [])
                team_names = [t.get("name", "") for t in teams if t.get("name")]

                # Entity state from the most recent alert in the incident
                entity_state = incident.get("entityState", "WARNING").upper()

                severity = self.ENTITY_STATE_MAP.get(entity_state, AlertSeverity.WARNING)
                status = self.INCIDENT_STATUS_MAP.get(current_phase, AlertStatus.FIRING)

                last_received = ""
                if start_time_ms:
                    try:
                        last_received = datetime.datetime.fromtimestamp(
                            start_time_ms / 1000, tz=datetime.timezone.utc
                        ).isoformat()
                    except Exception:
                        pass

                alerts.append(
                    AlertDto(
                        id=f"victorops-{incident_number}",
                        name=entity_display_name or f"Incident #{incident_number}",
                        description=f"Splunk On-Call incident #{incident_number} ({alert_count} alert(s))",
                        severity=severity,
                        status=status,
                        lastReceived=last_received,
                        source=["victorops"],
                        labels={
                            "incident_number": incident_number,
                            "entity_id": entity_id,
                            "entity_state": entity_state,
                            "current_phase": current_phase,
                            "service": service,
                            "teams": ", ".join(team_names),
                            "organization": self.authentication_config.organization_slug,
                        },
                    )
                )

            return alerts

        except Exception as e:
            self.logger.error("Error fetching Splunk On-Call incidents: %s", e)
            return []

    def _get_alerts(self) -> List[AlertDto]:
        self.logger.info("Collecting active incidents from Splunk On-Call (VictorOps)")
        return self.__get_active_incidents()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a VictorOps / Splunk On-Call outbound webhook payload into an AlertDto.

        Splunk On-Call outbound webhooks fire on incident state transitions.
        The payload contains an `alert` object with entity information and
        a `state_start_time` (Unix timestamp in seconds).
        """
        alert_payload = event.get("alert", event)
        incident_number = str(
            alert_payload.get("INCIDENT_NUMBER", alert_payload.get("incidentNumber", ""))
        )

        # Entity state → severity
        entity_state = alert_payload.get(
            "ENTITY_STATE",
            alert_payload.get("entity_state", "WARNING"),
        ).upper()

        severity_map = {
            "CRITICAL": AlertSeverity.CRITICAL,
            "WARNING": AlertSeverity.WARNING,
            "INFO": AlertSeverity.INFO,
            "UNKNOWN": AlertSeverity.WARNING,
        }
        severity = severity_map.get(entity_state, AlertSeverity.WARNING)

        # Phase → status
        current_phase = alert_payload.get(
            "CURRENT_ALERT_PHASE",
            alert_payload.get("current_phase", "TRIGGERED"),
        ).upper()

        status_map = {
            "TRIGGERED": AlertStatus.FIRING,
            "ACKNOWLEDGED": AlertStatus.ACKNOWLEDGED,
            "RESOLVED": AlertStatus.RESOLVED,
        }
        status = status_map.get(current_phase, AlertStatus.FIRING)

        # Timestamps
        state_start_time = alert_payload.get(
            "STATE_START_TIME",
            alert_payload.get("state_start_time", 0),
        )
        last_received = ""
        if state_start_time:
            try:
                last_received = datetime.datetime.fromtimestamp(
                    int(state_start_time), tz=datetime.timezone.utc
                ).isoformat()
            except Exception:
                pass

        entity_display_name = alert_payload.get(
            "ENTITY_DISPLAY_NAME",
            alert_payload.get("entity_display_name", ""),
        )
        entity_id = alert_payload.get(
            "ENTITY_ID",
            alert_payload.get("entity_id", incident_number),
        )
        monitoring_tool = alert_payload.get(
            "MONITORING_TOOL",
            alert_payload.get("monitoring_tool", ""),
        )
        state_message = alert_payload.get(
            "STATE_MESSAGE",
            alert_payload.get("state_message", ""),
        )
        service = alert_payload.get("SERVICE", alert_payload.get("service", ""))

        return AlertDto(
            id=f"victorops-{incident_number or entity_id}",
            name=entity_display_name or entity_id or "VictorOps Alert",
            description=state_message,
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["victorops"],
            labels={
                "incident_number": incident_number,
                "entity_id": entity_id,
                "entity_state": entity_state,
                "current_phase": current_phase,
                "monitoring_tool": monitoring_tool,
                "service": service,
            },
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_id = os.environ.get("VICTOROPS_API_ID")
    api_key = os.environ.get("VICTOROPS_API_KEY")
    org_slug = os.environ.get("VICTOROPS_ORG_SLUG")

    if not api_id or not api_key or not org_slug:
        raise Exception(
            "VICTOROPS_API_ID, VICTOROPS_API_KEY, and VICTOROPS_ORG_SLUG must be set"
        )

    config = ProviderConfig(
        description="Splunk On-Call (VictorOps) Provider",
        authentication={
            "api_id": api_id,
            "api_key": api_key,
            "organization_slug": org_slug,
        },
    )

    provider = VictorOpsProvider(
        context_manager,
        provider_id="victorops",
        config=config,
    )

    alerts = provider._get_alerts()
    print(f"Found {len(alerts)} active incidents")
    for alert in alerts[:5]:
        print(alert)
