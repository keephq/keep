"""
Grafana Incident Provider is a class that allows to query all incidents from Grafana Incident.
"""

import dataclasses
from datetime import datetime
import hashlib
from urllib.parse import urljoin
import uuid

import pydantic
import requests

from keep.api.models.alert import IncidentDto, IncidentStatus, IncidentSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseIncidentProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class GrafanaIncidentProviderAuthConfig:
    """
    GrafanaIncidentProviderAuthConfig is a class that allows to authenticate in Grafana Incident.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Grafana Host URL",
            "hint": "e.g. https://keephq.grafana.net",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    service_account_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Service Account Token",
            "sensitive": True,
        },
        default=None,
    )


class GrafanaIncidentProvider(BaseIncidentProvider):
    """
    GrafanaIncidentProvider is a class that allows to query all incidents from Grafana Incident.
    """
    PROVIDER_DISPLAY_NAME = "Grafana Incident"
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authenticated",
        ),
    ]
    PROVIDER_CATEGORY = ["Incident Management"]

    SEVERITIES_MAP = {
        "Pending": IncidentSeverity.INFO,
        "Critical": IncidentSeverity.CRITICAL,
        "Major": IncidentSeverity.HIGH,
        "Minor": IncidentSeverity.LOW,
        "Moderate": IncidentSeverity.WARNING,
        "Cosmetic": IncidentSeverity.INFO
    }

    STATUS_MAP = {"active": IncidentStatus.FIRING,
                  "resolved": IncidentStatus.RESOLVED}

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validate the configuration of the provider.
        """
        self.authentication_config = GrafanaIncidentProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self):
        """
        Get the headers for the request.
        """
        return {
            "Authorization": f"Bearer {self.authentication_config.service_account_token}",
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider.
        """
        try:
            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "/api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.QueryIncidentPreviews",
                ),
                headers=self.__get_headers(),
                json={
                    "query": {
                        "limit": 1,
                        "orderDirection": "DESC",
                        "orderField": "createdTime",
                    }
                },
            )

            if response.status_code == 200:
                return {"authenticated": True}
            else:
                self.logger.error(
                    f"Failed to validate scopes: {response.status_code}")
                scopes = {
                    "authenticated": f"Unable to query incidents: {response.status_code}"
                }
        except Exception as e:
            self.logger.error(f"Failed to validate scopes: {e}")
            scopes = {"authenticated": f"Unable to query incidents: {e}"}

        return scopes

    @staticmethod
    def _get_incident_id(incident_id: str) -> str:
        """
        Create a UUID from the incident id.

        Args:
            incident_id (str): The original incident id

        Returns:
            str: The UUID
        """
        md5 = hashlib.md5()
        md5.update(incident_id.encode("utf-8"))
        return uuid.UUID(md5.hexdigest())

    def _get_incidents(self) -> list[IncidentDto]:
        """
        Get the incidents from Grafana Incident
        """
        self.logger.info("Getting incidents from Grafana Incident")

        cursor = None
        incidents = []

        payload = {
            "query": {
                "limit": 50,
                "orderDirection": "DESC",
                "orderField": "createdTime",
            },
        }

        while True:
            self.logger.info("Getting incidents from Grafana Incident")
            try:
                if cursor:
                    payload["cursor"] = cursor

                response = requests.post(
                    urljoin(
                        self.authentication_config.host_url,
                        "api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.QueryIncidentPreviews",
                    ),
                    headers=self.__get_headers(),
                    json=payload,
                )

                if not response.ok:
                    self.logger.error(
                        f"Failed to get incidents from Grafana Incident: {response.status_code}"
                    )
                    raise Exception(
                        f"Failed to get incidents from Grafana Incident: {response.status_code} - {response.text}"
                    )

                data = response.json()

                incidents.extend(data.get("incidentPreviews", []))

                cursor = data.get("cursor")

                if cursor.get("hasMore") == False:
                    break

            except Exception as e:
                self.logger.exception(
                    "Failed to get incidents from Grafana Incident")
                raise Exception(
                    f"Failed to get incidents from Grafana Incident: {e}")
            
        self.logger.info(f"Total incidents: {len(incidents)}")

        alertDtos = []

        def parse_grafana_timestamp(timestamp):
            try:
                # Try parsing with milliseconds
                return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')
            except ValueError:
                # Fallback if milliseconds are not present
                return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')

        for incident in incidents:
            id = self._get_incident_id(incident.get("incidentID"))

            start_time = None
            end_time = None
            created_time = None

            if incident.get("incidentStart") != "":
                start_time = parse_grafana_timestamp(incident.get("incidentStart"))

            if incident.get("incidentEnd") != "":
                end_time = parse_grafana_timestamp(incident.get("incidentEnd"))

            if incident.get("createdTime") != "":
                created_time = parse_grafana_timestamp(incident.get("createdTime"))

            severity_label = GrafanaIncidentProvider.SEVERITIES_MAP.get(
                incident.get("severityLabel"), IncidentSeverity.INFO
            )

            status = GrafanaIncidentProvider.STATUS_MAP.get(
                incident.get("status"), IncidentStatus.FIRING
            )

            alerts_count = len(incidents)

            alertDto = IncidentDto(
                id=id,
                original_incident_id=incident.get("incidentID"),
                incident_id=incident.get("id"),
                severity_id=incident.get("severityID"),
                severity=severity_label,
                incident_type=incident.get("incidentType"),
                labels=incident.get("labels", []),
                is_drill=incident.get("isDrill"),
                start_time=start_time,
                end_time=end_time,
                created_time=created_time,
                modified_time=incident.get("modifiedTime"),
                closed_time=incident.get("closedTime"),
                created_by_user=incident.get("createdByUser", {}),
                title=incident.get("title"),
                description=incident.get("description"),
                summary=incident.get("summary"),
                hero_image_path=incident.get("heroImagePath"),
                status=status,
                slug=incident.get("slug"),
                incident_start=incident.get("incidentStart"),
                incident_end=incident.get("incidentEnd"),
                field_values=incident.get("fieldValues", []),
                incident_membership_preview=incident.get(
                    "incidentMembershipPreview", {}
                ),
                version=incident.get("version"),
                is_predicted=False,
                is_confirmed=True,
                services=["incidentPreviews"],
                alert_sources=["grafana_incident"],
                alerts_count=alerts_count
            )
            alertDtos.append(alertDto)

        return alertDtos

    # https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/incident/api/reference/#createincident
    def _create_incident(
        self,
        title: str = "",
        severity: str = "",
        labels=[],
        roomPrefix: str = "",
        isDrill: bool | None = None,
        status: str = "",
        attachCaption: str = "",
        attachURL: str = ""
    ) -> dict:
        """
        Create an incident in Grafana Incident with the given parameters.
        """

        self.logger.info("Creating incident in Grafana Incident")

        try:
            payload = {
                "title": title,
                "severity": severity,
                "labels": labels,
                "roomPrefix": roomPrefix,
                "isDrill": isDrill,
                "status": status,
                "attachCaption": attachCaption,
                "attachURL": attachURL,
            }

            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.CreateIncident",
                ),
                headers=self.__get_headers(),
                json=payload,
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to create incident in Grafana Incident: {response.status_code}"
                )
                raise Exception(
                    f"Failed to create incident in Grafana Incident: {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            self.logger.exception(
                "Failed to create incident in Grafana Incident")
            raise Exception(
                f"Failed to create incident in Grafana Incident: {e}")

    # https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/incident/api/reference/#removelabel
    def _remove_label(
        self,
        incident_id: str,
        label: str
    ) -> dict:
        """
        Remove the incident label in Grafana Incident with the given parameters.
        """

        self.logger.info("Removing incident label in Grafana Incident")

        try:
            payload = {
                "incidentID": incident_id,
                "label": label,
            }

            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.RemoveLabel",
                ),
                headers=self.__get_headers(),
                json=payload,
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to remove incident label in Grafana Incident: {response.status_code}"
                )
                raise Exception(
                    f"Failed to remove incident label in Grafana Incident: {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            self.logger.exception(
                "Failed to remove incident label in Grafana Incident")
            raise Exception(
                f"Failed to remove incident label in Grafana Incident: {e}")

    # https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/incident/api/reference/#unassignlabel
    def _unassign_label(
        self,
        incident_id: str,
        key: str,
        value: str
    ) -> dict:
        """
        Unassign the label in Grafana Incident with the given parameters.
        """

        self.logger.info("Unassigning label in Grafana Incident")

        try:
            payload = {
                "incidentID": incident_id,
                "key": key,
                "value": value,
            }

            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.UnassignLabel",
                ),
                headers=self.__get_headers(),
                json=payload,
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to unassign label in Grafana Incident: {response.status_code}"
                )
                raise Exception(
                    f"Failed to unassign label in Grafana Incident: {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            self.logger.exception(
                "Failed to unassign label in Grafana Incident")
            raise Exception(
                f"Failed to unassign label in Grafana Incident: {e}")

    # https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/incident/api/reference/#unassignlabelbyuuid
    def _unassign_label_by_uuid(
        self,
        incident_id: str,
        key_uuid: str,
        value_uuid: str
    ) -> dict:
        """
        Unassign the label by UUID in Grafana Incident with the given parameters.
        """

        self.logger.info("Unassigning label by UUID in Grafana Incident")

        try:
            payload = {
                "incidentID": incident_id,
                "keyUUID": key_uuid,
                "valueUUID": value_uuid,
            }

            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.UnassignLabelByUUID",
                ),
                headers=self.__get_headers(),
                json=payload,
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to unassign label by UUID in Grafana Incident: {response.status_code}"
                )
                raise Exception(
                    f"Failed to unassign label by UUID in Grafana Incident: {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            self.logger.exception(
                "Failed to unassign label by UUID in Grafana Incident")
            raise Exception(
                f"Failed to unassign label by UUID in Grafana Incident: {e}")

    # https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/incident/api/reference/#unassignrole
    def _unassign_role(
        self,
        incident_id: str,
        role: str,
        user_id: str
    ) -> dict:
        """
        Unassign the role in Grafana Incident with the given parameters.
        """

        self.logger.info("Unassigning role in Grafana Incident")

        try:
            payload = {
                "incidentID": incident_id,
                "role": role,
                "userID": user_id,
            }

            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.UnassignRole",
                ),
                headers=self.__get_headers(),
                json=payload,
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to unassign role in Grafana Incident: {response.status_code}"
                )
                raise Exception(
                    f"Failed to unassign role in Grafana Incident: {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            self.logger.exception(
                "Failed to unassign role in Grafana Incident")
            raise Exception(
                f"Failed to unassign role in Grafana Incident: {e}")

    # https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/incident/api/reference/#updateincidenteventtime
    def _update_incident_event_time(
        self,
        incident_id: str,
        event_time: str,
        event_name: str
    ) -> dict:
        """
        Update the incident event time in Grafana Incident with the given parameters.
        """

        self.logger.info("Updating incident event time in Grafana Incident")

        try:
            payload = {
                "incidentID": incident_id,
                "eventTime": event_time,
                "eventName": event_name,
                "activityItemKind": event_name,
            }

            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.UpdateIncidentEventTime",
                ),
                headers=self.__get_headers(),
                json=payload,
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to update incident event time in Grafana Incident: {response.status_code}"
                )
                raise Exception(
                    f"Failed to update incident event time in Grafana Incident: {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            self.logger.exception(
                "Failed to update incident event time in Grafana Incident")
            raise Exception(
                f"Failed to update incident event time in Grafana Incident: {e}")

    # https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/incident/api/reference/#updateincidentisdrill
    def _update_incident_isDrill(
        self,
        incident_id: str,
        isDrill: bool
    ) -> dict:
        """
        Update the incident isDrill in Grafana Incident with the given parameters.
        """

        self.logger.info("Updating incident isDrill in Grafana Incident")

        try:
            payload = {
                "incidentID": incident_id,
                "isDrill": isDrill,
            }

            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.UpdateIncidentIsDrill",
                ),
                headers=self.__get_headers(),
                json=payload,
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to update incident isDrill in Grafana Incident: {response.status_code}"
                )
                raise Exception(
                    f"Failed to update incident isDrill in Grafana Incident: {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            self.logger.exception(
                "Failed to update incident isDrill in Grafana Incident")
            raise Exception(
                f"Failed to update incident isDrill in Grafana Incident: {e}")

    # https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/incident/api/reference/#updateseverity
    def _update_incident_severity(
        self,
        incident_id: str,
        severity: str
    ) -> dict:
        """
        Update the incident severity in Grafana Incident with the given parameters.
        """

        self.logger.info("Updating incident severity in Grafana Incident")

        try:
            payload = {
                "incidentID": incident_id,
                "severity": severity,
            }

            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.UpdateSeverity",
                ),
                headers=self.__get_headers(),
                json=payload,
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to update incident severity in Grafana Incident: {response.status_code}"
                )
                raise Exception(
                    f"Failed to update incident severity in Grafana Incident: {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            self.logger.exception(
                "Failed to update incident severity in Grafana Incident")
            raise Exception(
                f"Failed to update incident severity in Grafana Incident: {e}")

    # https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/incident/api/reference/#updatestatus
    def _update_incident_status(
        self,
        incident_id: str,
        status: str
    ) -> dict:
        """
        Update the incident status in Grafana Incident with the given parameters.
        """

        self.logger.info("Updating incident status in Grafana Incident")

        try:
            payload = {
                "incidentID": incident_id,
                "status": status,
            }

            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.UpdateStatus",
                ),
                headers=self.__get_headers(),
                json=payload,
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to update incident status in Grafana Incident: {response.status_code}"
                )
                raise Exception(
                    f"Failed to update incident status in Grafana Incident: {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            self.logger.exception(
                "Failed to update incident status in Grafana Incident")
            raise Exception(
                f"Failed to update incident status in Grafana Incident: {e}")

    # https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/incident/api/reference/#updatetitle
    def _update_incident_title(
        self,
        incident_id: str,
        title: str
    ) -> dict:
        """
        Update the incident title in Grafana Incident with the given parameters.
        """

        self.logger.info("Updating incident title in Grafana Incident")

        try:
            payload = {
                "incidentID": incident_id,
                "title": title,
            }

            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.UpdateTitle",
                ),
                headers=self.__get_headers(),
                json=payload,
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to update incident title in Grafana Incident: {response.status_code}"
                )
                raise Exception(
                    f"Failed to update incident title in Grafana Incident: {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            self.logger.exception(
                "Failed to update incident title in Grafana Incident")
            raise Exception(
                f"Failed to update incident title in Grafana Incident: {e}")

    def _notify(self, operationType: str = "", updateType: str = "", **kwargs):
        if operationType == "create":
            return self._create_incident(**kwargs)
        elif operationType == "update":
            return self._update_incident(updateType, **kwargs)

    def _update_incident(self, updateType: str, **kwargs):
        if updateType == "removeLabel":
            return self._remove_label(**kwargs)
        elif updateType == "unassignLabel":
            return self._unassign_label(**kwargs)
        elif updateType == "unassignLabelByUUID":
            return self._unassign_label_by_uuid(**kwargs)
        elif updateType == "unassignRole":
            return self._unassign_role(**kwargs)
        elif updateType == "updateIncidentEventTime":
            return self._update_incident_event_time(**kwargs)
        elif updateType == "updateIncidentIsDrill":
            return self._update_incident_isDrill(**kwargs)
        elif updateType == "updateIncidentSeverity":
            return self._update_incident_severity(**kwargs)
        elif updateType == "updateIncidentStatus":
            return self._update_incident_status(**kwargs)
        elif updateType == "updateIncidentTitle":
            return self._update_incident_title(**kwargs)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    host_url = os.getenv("GRAFANA_HOST_URL")
    api_token = os.getenv("GRAFANA_SERVICE_ACCOUNT_TOKEN")

    if host_url is None or api_token is None:
        raise Exception(
            "GRAFANA_HOST_URL and GRAFANA_SERVICE_ACCOUNT_TOKEN environment variables are required"
        )

    config = ProviderConfig(
        description="Grafana Incident Provider",
        authentication={
            "host_url": host_url,
            "service_account_token": api_token,
        },
    )

    provider = GrafanaIncidentProvider(
        context_manager,
        provider_id="grafana_incident",
        config=config,
    )

    provider._get_incidents()
