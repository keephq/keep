"""
StatuspageProvider is a class that allows to get incidents and component statuses from Atlassian Statuspage.
"""

import dataclasses
import datetime
from typing import List
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class StatuspageProviderAuthConfig:
    """
    StatuspageProviderAuthConfig is a class that allows to authenticate in Atlassian Statuspage.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Statuspage API Key",
            "hint": "Found under your Statuspage account settings → API info",
            "sensitive": True,
        },
    )

    page_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Statuspage Page ID",
            "hint": "Found in the URL of your Statuspage dashboard (e.g. https://manage.statuspage.io/pages/<page_id>)",
            "sensitive": False,
        },
    )


class StatuspageProvider(BaseProvider):
    """Pull incidents and component outages from Atlassian Statuspage."""

    PROVIDER_DISPLAY_NAME = "Statuspage"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Incident Management"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated",
            mandatory=True,
            alias="authenticated",
        ),
        ProviderScope(
            name="incidents_read",
            description="Can read incidents",
            mandatory=True,
            alias="incidents_read",
        ),
    ]

    SEVERITIES_MAP = {
        "under_maintenance": AlertSeverity.INFO,
        "degraded_performance": AlertSeverity.WARNING,
        "partial_outage": AlertSeverity.HIGH,
        "major_outage": AlertSeverity.CRITICAL,
        "operational": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "investigating": AlertStatus.FIRING,
        "identified": AlertStatus.FIRING,
        "monitoring": AlertStatus.ACKNOWLEDGED,
        "resolved": AlertStatus.RESOLVED,
        "postmortem": AlertStatus.RESOLVED,
        "scheduled": AlertStatus.PENDING,
        "in_progress": AlertStatus.FIRING,
        "verifying": AlertStatus.ACKNOWLEDGED,
        "completed": AlertStatus.RESOLVED,
    }

    BASE_URL = "https://api.statuspage.io/v1/"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = StatuspageProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self):
        return {
            "Authorization": f"OAuth {self.authentication_config.api_key}",
            "Content-Type": "application/json",
        }

    def __get_url(self, path: str) -> str:
        return urljoin(
            self.BASE_URL,
            f"pages/{self.authentication_config.page_id}/{path}",
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        try:
            response = requests.get(
                urljoin(self.BASE_URL, f"pages/{self.authentication_config.page_id}"),
                headers=self.__get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                scopes["authenticated"] = True
                scopes["incidents_read"] = True
            elif response.status_code == 401:
                scopes["authenticated"] = "Invalid API key"
                scopes["incidents_read"] = "Invalid API key"
            else:
                msg = f"Unexpected status code: {response.status_code}"
                scopes["authenticated"] = msg
                scopes["incidents_read"] = msg
        except Exception as e:
            self.logger.error("Error validating Statuspage scopes: %s", e)
            scopes["authenticated"] = str(e)
            scopes["incidents_read"] = str(e)
        return scopes

    def __get_incidents(self) -> List[AlertDto]:
        try:
            response = requests.get(
                self.__get_url("incidents"),
                headers=self.__get_headers(),
                timeout=10,
            )
            if not response.ok:
                self.logger.error(
                    "Failed to get incidents from Statuspage: %s", response.text
                )
                return []

            incidents = response.json()
            alerts = []
            for incident in incidents:
                severity = AlertSeverity.INFO
                # Derive severity from affected components
                for component in incident.get("components", []):
                    comp_status = component.get("status", "operational")
                    comp_severity = self.SEVERITIES_MAP.get(
                        comp_status, AlertSeverity.INFO
                    )
                    if comp_severity.value > severity.value:
                        severity = comp_severity

                status = self.STATUS_MAP.get(
                    incident.get("status", "investigating"), AlertStatus.FIRING
                )

                last_received = incident.get("updated_at") or incident.get(
                    "created_at"
                )
                if last_received:
                    try:
                        last_received = datetime.datetime.fromisoformat(
                            last_received.replace("Z", "+00:00")
                        ).isoformat()
                    except Exception:
                        pass

                alerts.append(
                    AlertDto(
                        id=incident["id"],
                        name=incident["name"],
                        description=incident.get("incident_updates", [{}])[0].get(
                            "body", ""
                        )
                        if incident.get("incident_updates")
                        else "",
                        severity=severity,
                        status=status,
                        lastReceived=last_received,
                        url=incident.get("shortlink", ""),
                        source=["statuspage"],
                        labels={
                            "impact": incident.get("impact", ""),
                            "components": ", ".join(
                                c.get("name", "")
                                for c in incident.get("components", [])
                            ),
                        },
                    )
                )
            return alerts

        except Exception as e:
            self.logger.error("Error getting incidents from Statuspage: %s", e)
            return []

    def _get_alerts(self) -> List[AlertDto]:
        self.logger.info("Collecting incidents from Statuspage")
        return self.__get_incidents()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """Format a Statuspage webhook payload into an AlertDto."""
        incident = event.get("incident", {})
        page = event.get("page", {})

        impact = incident.get("impact", "none")
        severity_map = {
            "critical": AlertSeverity.CRITICAL,
            "major": AlertSeverity.HIGH,
            "minor": AlertSeverity.WARNING,
            "none": AlertSeverity.INFO,
        }
        severity = severity_map.get(impact, AlertSeverity.INFO)

        status_map = {
            "investigating": AlertStatus.FIRING,
            "identified": AlertStatus.FIRING,
            "monitoring": AlertStatus.ACKNOWLEDGED,
            "resolved": AlertStatus.RESOLVED,
            "postmortem": AlertStatus.RESOLVED,
        }
        status = status_map.get(incident.get("status", "investigating"), AlertStatus.FIRING)

        last_received = incident.get("updated_at") or incident.get("created_at", "")
        if last_received:
            try:
                last_received = datetime.datetime.fromisoformat(
                    last_received.replace("Z", "+00:00")
                ).isoformat()
            except Exception:
                pass

        updates = incident.get("incident_updates", [])
        description = updates[0].get("body", "") if updates else ""

        return AlertDto(
            id=incident.get("id", ""),
            name=incident.get("name", "Statuspage Incident"),
            description=description,
            severity=severity,
            status=status,
            lastReceived=last_received,
            url=incident.get("shortlink", ""),
            source=["statuspage"],
            labels={
                "page_id": page.get("id", ""),
                "page_name": page.get("name", ""),
                "impact": impact,
                "components": ", ".join(
                    c.get("name", "")
                    for c in incident.get("components", [])
                ),
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

    api_key = os.environ.get("STATUSPAGE_API_KEY")
    page_id = os.environ.get("STATUSPAGE_PAGE_ID")

    if not api_key or not page_id:
        raise Exception("STATUSPAGE_API_KEY and STATUSPAGE_PAGE_ID must be set")

    config = ProviderConfig(
        description="Statuspage Provider",
        authentication={
            "api_key": api_key,
            "page_id": page_id,
        },
    )

    provider = StatuspageProvider(
        context_manager,
        provider_id="statuspage",
        config=config,
    )

    alerts = provider._get_alerts()
    print(alerts)
