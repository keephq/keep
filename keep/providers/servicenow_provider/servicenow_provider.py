"""
ServicenowProvider is a class that implements the BaseProvider interface for Service Now updates.
"""

import datetime
import hashlib
import json
import os
import dataclasses
import uuid

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.incident import IncidentSeverity, IncidentStatus
from keep.api.models.db.topology import TopologyServiceInDto
from keep.api.models.incident import IncidentDto
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import (
    BaseIncidentProvider,
    BaseTopologyProvider,
)
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class ServicenowProviderAuthConfig:
    """ServiceNow authentication configuration."""

    service_now_base_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "The base URL of the ServiceNow instance",
            "sensitive": False,
            "hint": "https://dev12345.service-now.com",
            "validation": "https_url",
        }
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The username of the ServiceNow user",
            "sensitive": False,
        }
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The password of the ServiceNow user",
            "sensitive": True,
        }
    )

    # @tb: based on this https://www.servicenow.com/community/developer-blog/oauth-2-0-with-inbound-rest/ba-p/2278926
    client_id: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "The client ID to use OAuth 2.0 based authentication",
            "sensitive": False,
        },
        default="",
    )

    client_secret: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "The client secret to use OAuth 2.0 based authentication",
            "sensitive": True,
        },
        default="",
    )

    ticket_creation_url: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "URL for creating new tickets",
            "sensitive": False,
            "hint": "https://dev12345.service-now.com/now/sow/record/incident/-1",
        },
        default="",
    )


class ServicenowProvider(BaseTopologyProvider, BaseIncidentProvider):
    """Manage ServiceNow tickets and pull incident activity."""

    PROVIDER_CATEGORY = ["Ticketing", "Incident Management"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="itil",
            description="The user can read/write tickets from the table",
            documentation_url="https://docs.servicenow.com/bundle/sandiego-platform-administration/page/administer/roles/reference/r_BaseSystemRoles.html",
            mandatory=True,
            alias="Read from datahase",
        )
    ]
    PROVIDER_TAGS = ["ticketing", "incident"]
    PROVIDER_DISPLAY_NAME = "Service Now"

    # ServiceNow incident states → Keep AlertStatus
    ALERT_STATUS_MAP = {
        "1": AlertStatus.FIRING,       # New
        "2": AlertStatus.ACKNOWLEDGED,  # In Progress
        "3": AlertStatus.SUPPRESSED,    # On Hold
        "6": AlertStatus.RESOLVED,      # Resolved
        "7": AlertStatus.RESOLVED,      # Closed
        "8": AlertStatus.RESOLVED,      # Canceled
    }

    # ServiceNow incident states → Keep IncidentStatus
    INCIDENT_STATUS_MAP = {
        "1": IncidentStatus.FIRING,        # New
        "2": IncidentStatus.ACKNOWLEDGED,  # In Progress
        "3": IncidentStatus.ACKNOWLEDGED,  # On Hold
        "6": IncidentStatus.RESOLVED,      # Resolved
        "7": IncidentStatus.RESOLVED,      # Closed
        "8": IncidentStatus.RESOLVED,      # Canceled
    }

    # ServiceNow priority → Keep AlertSeverity
    ALERT_SEVERITY_MAP = {
        "1": AlertSeverity.CRITICAL,  # Critical
        "2": AlertSeverity.HIGH,      # High
        "3": AlertSeverity.WARNING,   # Moderate
        "4": AlertSeverity.LOW,       # Low
        "5": AlertSeverity.INFO,      # Planning
    }

    # ServiceNow priority → Keep IncidentSeverity
    INCIDENT_SEVERITY_MAP = {
        "1": IncidentSeverity.CRITICAL,  # Critical
        "2": IncidentSeverity.HIGH,      # High
        "3": IncidentSeverity.WARNING,   # Moderate
        "4": IncidentSeverity.LOW,       # Low
        "5": IncidentSeverity.INFO,      # Planning
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._access_token = None
        if (
            self.authentication_config.client_id
            and self.authentication_config.client_secret
        ):
            url = f"{self.authentication_config.service_now_base_url}/oauth_token.do"
            payload = {
                "grant_type": "password",
                "username": self.authentication_config.username,
                "password": self.authentication_config.password,
                "client_id": self.authentication_config.client_id,
                "client_secret": self.authentication_config.client_secret,
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
            response = requests.post(
                url,
                data=payload,
                headers=headers,
            )
            if response.ok:
                self._access_token = response.json().get("access_token")
            else:
                self.logger.error(
                    "Failed to get access token",
                    extra={
                        "response": response.text,
                        "status_code": response.status_code,
                        "provider_id": self.provider_id,
                    },
                )
                raise ProviderException(
                    f"Failed to get OAuth access token from ServiceNow: {response.status_code}, {response.text}."
                    " Please check your ServiceNow logs, information about this error should be there."
                )

    def validate_scopes(self):
        """
        Validates that the user has the required scopes to use the provider.
        """

        # Optional scope validation skipping
        if (
            os.environ.get(
                "KEEP_SERVICENOW_PROVIDER_SKIP_SCOPE_VALIDATION", "false"
            ).lower()
            == "true"
        ):
            return {"itil": True}

        try:
            self.logger.info("Validating ServiceNow scopes")
            url = f"{self.authentication_config.service_now_base_url}/api/now/table/sys_user_role?sysparm_query=user_name={self.authentication_config.username}"
            if self._access_token:
                response = requests.get(
                    url,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    verify=False,
                    timeout=10,
                )
            else:
                response = requests.get(
                    url,
                    auth=HTTPBasicAuth(
                        self.authentication_config.username,
                        self.authentication_config.password,
                    ),
                    verify=False,
                    timeout=10,
                )

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                self.logger.exception(f"Failed to get roles from ServiceNow: {e}")
                scopes = {"itil": str(e)}
                return scopes

            if response.ok:
                roles = response.json()
                roles_names = [role.get("name") for role in roles.get("result")]
                if "itil" in roles_names:
                    self.logger.info("User has ITIL role")
                    scopes = {
                        "itil": True,
                    }
                else:
                    self.logger.info("User does not have ITIL role")
                    scopes = {
                        "itil": "This user does not have the ITIL role",
                    }
            else:
                self.logger.error(
                    "Failed to get roles from ServiceNow",
                    extra={
                        "response": response.text,
                        "status_code": response.status_code,
                    },
                )
                scopes = {"itil": "Failed to get roles from ServiceNow"}
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {
                "itil": str(e),
            }
        return scopes

    def validate_config(self):
        self.authentication_config = ServicenowProviderAuthConfig(
            **self.config.authentication
        )

    def _get_headers(self):
        """Get common request headers."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _get_auth(self):
        """Get auth tuple for requests (None if using OAuth token)."""
        if self._access_token:
            return None
        return (
            self.authentication_config.username,
            self.authentication_config.password,
        )

    def _query(
        self,
        table_name: str,
        incident_id: str = None,
        sysparm_limit: int = 100,
        sysparm_offset: int = 0,
        **kwargs: dict,
    ):
        """
        Query ServiceNow for records.
        Args:
            table_name (str): The name of the table to query.
            incident_id (str): The incident ID to query.
            sysparm_limit (int): The maximum number of records to return.
            sysparm_offset (int): The offset to start from.
        """
        request_url = f"{self.authentication_config.service_now_base_url}/api/now/table/{table_name}"
        headers = self._get_headers()
        auth = self._get_auth()

        if incident_id:
            request_url = f"{request_url}/{incident_id}"

        params = {"sysparm_offset": sysparm_offset, "sysparm_limit": sysparm_limit}

        # Add any extra query params
        for key, value in kwargs.items():
            if key.startswith("sysparm_"):
                params[key] = value

        response = requests.get(
            request_url,
            headers=headers,
            auth=auth,
            params=params,
            verify=False,
            timeout=10,
        )

        if not response.ok:
            self.logger.error(
                f"Failed to query {table_name}",
                extra={"status_code": response.status_code, "response": response.text},
            )
            return []

        return response.json().get("result", [])

    def _get_paginated_results(
        self,
        table_name: str,
        sysparm_query: str = "",
        sysparm_fields: str = "",
        sysparm_limit: int = 100,
        max_pages: int = 10,
    ) -> list[dict]:
        """
        Get paginated results from a ServiceNow table.

        Args:
            table_name: The name of the ServiceNow table.
            sysparm_query: The query string for filtering.
            sysparm_fields: Comma-separated list of fields to return.
            sysparm_limit: Number of records per page.
            max_pages: Maximum number of pages to retrieve.

        Returns:
            A list of result dictionaries.
        """
        all_results = []
        offset = 0

        for page in range(max_pages):
            params = {
                "sysparm_limit": sysparm_limit,
                "sysparm_offset": offset,
            }
            if sysparm_query:
                params["sysparm_query"] = sysparm_query
            if sysparm_fields:
                params["sysparm_fields"] = sysparm_fields

            request_url = f"{self.authentication_config.service_now_base_url}/api/now/table/{table_name}"
            response = requests.get(
                request_url,
                headers=self._get_headers(),
                auth=self._get_auth(),
                params=params,
                verify=False,
                timeout=30,
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to query {table_name} at offset {offset}",
                    extra={
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                )
                break

            results = response.json().get("result", [])
            if not results:
                break

            all_results.extend(results)
            self.logger.info(
                f"Fetched page {page + 1} from {table_name}",
                extra={"count": len(results), "total_so_far": len(all_results)},
            )

            if len(results) < sysparm_limit:
                break

            offset += sysparm_limit

        return all_results

    # ---- Alert pulling (incidents as alerts) ----

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull ServiceNow incidents as Keep alerts.
        Each ServiceNow incident is mapped to an AlertDto.
        """
        self.logger.info("Pulling incidents as alerts from ServiceNow")

        incidents = self._get_paginated_results(
            table_name="incident",
            sysparm_query="ORDERBYDESCsys_updated_on",
            sysparm_fields=(
                "sys_id,number,short_description,description,state,priority,"
                "severity,urgency,impact,assigned_to,assignment_group,"
                "opened_at,closed_at,resolved_at,sys_updated_on,sys_created_on,"
                "category,subcategory,cmdb_ci,caller_id,close_code,close_notes"
            ),
        )

        self.logger.info(
            "Fetched incidents from ServiceNow",
            extra={"count": len(incidents)},
        )

        alerts = []
        for incident in incidents:
            try:
                alert = self._format_incident_as_alert(incident)
                alerts.append(alert)
            except Exception:
                self.logger.exception(
                    "Failed to format incident as alert",
                    extra={"incident_number": incident.get("number")},
                )

        self.logger.info(
            "Completed pulling alerts from ServiceNow",
            extra={"alert_count": len(alerts)},
        )
        return alerts

    def _format_incident_as_alert(self, incident: dict) -> AlertDto:
        """Convert a ServiceNow incident record to a Keep AlertDto."""
        incident_number = incident.get("number", "")
        state = str(incident.get("state", "1"))
        priority = str(incident.get("priority", "4"))
        sys_id = incident.get("sys_id", "")

        status = self.ALERT_STATUS_MAP.get(state, AlertStatus.FIRING)
        severity = self.ALERT_SEVERITY_MAP.get(priority, AlertSeverity.INFO)

        # Parse timestamps
        last_received = incident.get("sys_updated_on") or incident.get("sys_created_on") or ""
        opened_at = incident.get("opened_at", "")

        # Build URL to incident in ServiceNow
        url = (
            f"{self.authentication_config.service_now_base_url}"
            f"/nav_to.do?uri=incident.do%3Fsys_id%3D{sys_id}"
        )

        # Build description with activity context
        description = incident.get("description", "") or incident.get("short_description", "")

        # Get assigned_to - it may be a string or a dict with a 'display_value'
        assigned_to = incident.get("assigned_to", "")
        if isinstance(assigned_to, dict):
            assigned_to = assigned_to.get("display_value", assigned_to.get("value", ""))

        # Extract labels
        labels = {
            "category": incident.get("category", ""),
            "subcategory": incident.get("subcategory", ""),
            "urgency": incident.get("urgency", ""),
            "impact": incident.get("impact", ""),
            "priority": priority,
            "state": state,
        }

        # Add assignment group info
        assignment_group = incident.get("assignment_group", "")
        if isinstance(assignment_group, dict):
            assignment_group = assignment_group.get(
                "display_value", assignment_group.get("value", "")
            )
        labels["assignment_group"] = assignment_group

        # Add CI information
        cmdb_ci = incident.get("cmdb_ci", "")
        if isinstance(cmdb_ci, dict):
            cmdb_ci = cmdb_ci.get("display_value", cmdb_ci.get("value", ""))
        service = cmdb_ci if cmdb_ci else None

        fingerprint = f"servicenow-{incident_number}"

        return AlertDto(
            id=sys_id,
            name=f"ServiceNow Incident {incident_number}",
            status=status,
            severity=severity,
            lastReceived=last_received,
            firingStartTime=opened_at if opened_at else None,
            source=["servicenow"],
            message=incident.get("short_description", ""),
            description=description,
            url=url,
            fingerprint=fingerprint,
            service=service,
            assignee=assigned_to if assigned_to else None,
            labels=labels,
        )

    # ---- Incident pulling ----

    @staticmethod
    def _get_incident_id(incident_number: str) -> uuid.UUID:
        """Create a deterministic UUID from a ServiceNow incident number."""
        md5 = hashlib.md5()
        md5.update(incident_number.encode("utf-8"))
        return uuid.UUID(md5.hexdigest())

    def _get_incidents(self) -> list[IncidentDto]:
        """
        Pull ServiceNow incidents as Keep IncidentDtos.
        Also pulls associated activity (comments and work notes).
        """
        self.logger.info("Pulling incidents from ServiceNow")

        incidents = self._get_paginated_results(
            table_name="incident",
            sysparm_query="ORDERBYDESCsys_updated_on",
            sysparm_fields=(
                "sys_id,number,short_description,description,state,priority,"
                "severity,urgency,impact,assigned_to,assignment_group,"
                "opened_at,closed_at,resolved_at,sys_updated_on,sys_created_on,"
                "category,subcategory,cmdb_ci,caller_id,close_code,close_notes,"
                "comments_and_work_notes"
            ),
        )

        self.logger.info(
            "Fetched incidents from ServiceNow",
            extra={"count": len(incidents)},
        )

        incident_dtos = []
        for incident in incidents:
            try:
                incident_dto = self._format_incident(
                    {"event": incident}
                )
                if incident_dto:
                    # Fetch activity (comments/work notes) for this incident
                    try:
                        activity_alerts = self._get_incident_activity(
                            incident.get("sys_id", "")
                        )
                        incident_dto._alerts = activity_alerts
                    except Exception:
                        self.logger.exception(
                            "Failed to fetch activity for incident",
                            extra={
                                "incident_number": incident.get("number"),
                                "provider_id": self.provider_id,
                            },
                        )
                    incident_dtos.append(incident_dto)
            except Exception:
                self.logger.exception(
                    "Failed to format incident",
                    extra={"incident_number": incident.get("number")},
                )

        self.logger.info(
            "Completed pulling incidents from ServiceNow",
            extra={"incident_count": len(incident_dtos)},
        )
        return incident_dtos

    @staticmethod
    def _format_incident(
        event: dict, provider_instance: "ServicenowProvider" = None
    ) -> IncidentDto | list[IncidentDto]:
        """
        Format a ServiceNow incident event into an IncidentDto.
        The event dict should have the structure: {"event": <incident_record>}
        """
        incident = event.get("event", event)

        incident_number = incident.get("number", "")
        if not incident_number:
            return []

        incident_id = ServicenowProvider._get_incident_id(incident_number)
        sys_id = incident.get("sys_id", "")

        state = str(incident.get("state", "1"))
        priority = str(incident.get("priority", "4"))

        status = ServicenowProvider.INCIDENT_STATUS_MAP.get(
            state, IncidentStatus.FIRING
        )
        severity = ServicenowProvider.INCIDENT_SEVERITY_MAP.get(
            priority, IncidentSeverity.INFO
        )

        # Parse timestamps
        created_at = incident.get("sys_created_on") or incident.get("opened_at")
        if created_at:
            try:
                created_at = datetime.datetime.strptime(
                    created_at, "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, TypeError):
                created_at = datetime.datetime.now(tz=datetime.timezone.utc)
        else:
            created_at = datetime.datetime.now(tz=datetime.timezone.utc)

        last_seen = incident.get("sys_updated_on")
        if last_seen:
            try:
                last_seen = datetime.datetime.strptime(
                    last_seen, "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, TypeError):
                last_seen = None

        end_time = incident.get("resolved_at") or incident.get("closed_at")
        if end_time:
            try:
                end_time = datetime.datetime.strptime(
                    end_time, "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, TypeError):
                end_time = None

        # Extract service info from CI
        cmdb_ci = incident.get("cmdb_ci", "")
        if isinstance(cmdb_ci, dict):
            cmdb_ci = cmdb_ci.get("display_value", cmdb_ci.get("value", ""))
        services = [cmdb_ci] if cmdb_ci else []

        # Build user-generated name
        short_desc = incident.get("short_description", "Unknown")
        user_generated_name = f"SN-{incident_number}: {short_desc}"

        return IncidentDto(
            id=incident_id,
            user_generated_name=user_generated_name,
            user_summary=incident.get("description", ""),
            status=status,
            severity=severity,
            creation_time=created_at,
            start_time=created_at,
            last_seen_time=last_seen,
            end_time=end_time,
            alert_sources=["servicenow"],
            alerts_count=0,
            services=services,
            is_predicted=False,
            is_candidate=False,
            fingerprint=f"{sys_id}" if sys_id else incident_number,
            assignee=_extract_display_value(incident.get("assigned_to")),
        )

    # ---- Activity / Journal Entries ----

    def _get_incident_activity(self, incident_sys_id: str) -> list[AlertDto]:
        """
        Pull journal entries (comments and work notes) for a specific ServiceNow incident.
        Returns them as AlertDto objects so they can be associated as incident alerts.

        Uses the sys_journal_field table to get work notes and comments.
        """
        if not incident_sys_id:
            return []

        self.logger.info(
            "Fetching activity for incident",
            extra={"incident_sys_id": incident_sys_id},
        )

        # Query journal entries for this incident
        # element_id is the sys_id of the incident
        # element is the field name: 'comments' for additional comments, 'work_notes' for work notes
        journal_entries = self._get_paginated_results(
            table_name="sys_journal_field",
            sysparm_query=(
                f"element_id={incident_sys_id}"
                "^element=comments^ORelement=work_notes"
                "^ORDERBYDESCsys_created_on"
            ),
            sysparm_fields=(
                "sys_id,element_id,element,value,sys_created_on,"
                "sys_created_by,name"
            ),
            sysparm_limit=50,
            max_pages=2,
        )

        self.logger.info(
            "Fetched journal entries",
            extra={
                "incident_sys_id": incident_sys_id,
                "entry_count": len(journal_entries),
            },
        )

        activity_alerts = []
        for entry in journal_entries:
            try:
                alert = self._format_journal_entry_as_alert(
                    entry, incident_sys_id
                )
                activity_alerts.append(alert)
            except Exception:
                self.logger.exception(
                    "Failed to format journal entry",
                    extra={"entry_sys_id": entry.get("sys_id")},
                )

        return activity_alerts

    def _format_journal_entry_as_alert(
        self, entry: dict, incident_sys_id: str
    ) -> AlertDto:
        """Convert a ServiceNow journal field entry to an AlertDto."""
        entry_sys_id = entry.get("sys_id", "")
        element = entry.get("element", "")
        value = entry.get("value", "")
        created_on = entry.get("sys_created_on", "")
        created_by = entry.get("sys_created_by", "")

        # Determine if this is a comment or work note
        entry_type = "Work Note" if element == "work_notes" else "Comment"

        # Build a descriptive alert
        name = f"ServiceNow {entry_type} on {incident_sys_id}"
        message = f"[{entry_type}] by {created_by}: {value[:200]}" if value else f"[{entry_type}] by {created_by}"

        fingerprint = f"servicenow-journal-{entry_sys_id}"

        return AlertDto(
            id=entry_sys_id,
            name=name,
            status=AlertStatus.FIRING,
            severity=AlertSeverity.INFO,
            lastReceived=created_on,
            source=["servicenow"],
            message=message,
            description=value,
            fingerprint=fingerprint,
            labels={
                "entry_type": entry_type,
                "element": element,
                "created_by": created_by,
                "incident_sys_id": incident_sys_id,
            },
        )

    def _add_comment(self, incident_sys_id: str, comment: str) -> dict:
        """
        Add a comment (additional comment / customer-visible) to a ServiceNow incident.

        Args:
            incident_sys_id: The sys_id of the incident.
            comment: The comment text to add.

        Returns:
            The response result dict.
        """
        return self._add_journal_entry(incident_sys_id, "comments", comment)

    def _add_work_note(self, incident_sys_id: str, work_note: str) -> dict:
        """
        Add a work note (internal) to a ServiceNow incident.

        Args:
            incident_sys_id: The sys_id of the incident.
            work_note: The work note text to add.

        Returns:
            The response result dict.
        """
        return self._add_journal_entry(incident_sys_id, "work_notes", work_note)

    def _add_journal_entry(
        self, incident_sys_id: str, field: str, value: str
    ) -> dict:
        """
        Add a journal entry (comment or work note) to a ServiceNow incident.

        Args:
            incident_sys_id: The sys_id of the incident.
            field: Either 'comments' or 'work_notes'.
            value: The text content.

        Returns:
            The response result dict.
        """
        url = (
            f"{self.authentication_config.service_now_base_url}"
            f"/api/now/table/incident/{incident_sys_id}"
        )

        payload = {field: value}
        response = requests.patch(
            url,
            headers=self._get_headers(),
            auth=self._get_auth(),
            data=json.dumps(payload),
            verify=False,
            timeout=10,
        )

        if not response.ok:
            self.logger.error(
                f"Failed to add {field} to incident",
                extra={
                    "incident_sys_id": incident_sys_id,
                    "status_code": response.status_code,
                    "response": response.text,
                },
            )
            raise ProviderException(
                f"Failed to add {field} to incident {incident_sys_id}: "
                f"{response.status_code} - {response.text}"
            )

        return response.json().get("result", {})

    # ---- Topology pulling (existing functionality) ----

    def pull_topology(self) -> tuple[list[TopologyServiceInDto], dict]:
        # TODO: in scale, we'll need to use pagination around here
        headers = self._get_headers()
        auth = self._get_auth()
        topology = []
        self.logger.info(
            "Pulling topology", extra={"tenant_id": self.context_manager.tenant_id}
        )

        self.logger.info("Pulling CMDB items")
        fields = [
            "name",
            "sys_id",
            "ip_address",
            "mac_address",
            "owned_by.name"
            "manufacturer.name",  # Retrieve the name of the manufacturer
            "short_description",
            "environment",
        ]

        # Set parameters for the request
        cmdb_params = {
            "sysparm_fields": ",".join(fields),
            "sysparm_query": "active=true",
        }
        cmdb_response = requests.get(
            f"{self.authentication_config.service_now_base_url}/api/now/table/cmdb_ci",
            headers=headers,
            auth=auth,
            params=cmdb_params,
        )

        if not cmdb_response.ok:
            self.logger.info(
                "Failed to pull topology with cmdb_params, retrying with no params.",
                extra={
                    "tenant_id": self.context_manager.tenant_id,
                    "status_code": cmdb_response.status_code,
                    "response_body": cmdb_response.text,
                    "using_access_token": self._access_token is not None,
                    "provider_id": self.provider_id,
                },
            )
            # Retry without params, may happen because of lack of permissions.
            # The following code is tolerant to missing data.
            cmdb_response = requests.get(
                f"{self.authentication_config.service_now_base_url}/api/now/table/cmdb_ci",
                headers=headers,
                auth=auth,
            )
            if not cmdb_response.ok:
                self.logger.error(
                    "Failed to pull topology without params.",
                    extra={
                        "tenant_id": self.context_manager.tenant_id,
                        "status_code": cmdb_response.status_code,
                        "response_body": cmdb_response.text,
                        "using_access_token": self._access_token is not None,
                        "provider_id": self.provider_id,
                    },
                )
                return topology, {}

        cmdb_data = cmdb_response.json().get("result", [])
        self.logger.info(
            "Pulling CMDB items completed", extra={"len_of_cmdb_items": len(cmdb_data)}
        )

        self.logger.info("Pulling relationship types")
        relationship_types = {}
        rel_type_response = requests.get(
            f"{self.authentication_config.service_now_base_url}/api/now/table/cmdb_rel_type",
            auth=auth,
            headers=headers,
        )
        if not rel_type_response.ok:
            self.logger.error(
                "Failed to get topology types",
                extra={
                    "tenant_id": self.context_manager.tenant_id,
                    "status_code": cmdb_response.status_code,
                    "response_body": cmdb_response.text,
                    "using_access_token": self._access_token is not None,
                    "provider_id": self.provider_id,
                },
            )
        else:
            rel_type_json = rel_type_response.json()
            for result in rel_type_json.get("result", []):
                relationship_types[result.get("sys_id")] = result.get("sys_name")
            self.logger.info("Pulling relationship types completed")

        self.logger.info("Pulling relationships")
        relationships = {}
        rel_response = requests.get(
            f"{self.authentication_config.service_now_base_url}/api/now/table/cmdb_rel_ci",
            auth=auth,
            headers=headers,
        )
        if not rel_response.ok:
            self.logger.error(
                "Failed to get topology relationships",
                extra={
                    "tenant_id": self.context_manager.tenant_id,
                    "status_code": cmdb_response.status_code,
                    "response_body": cmdb_response.text,
                    "using_access_token": self._access_token is not None,
                    "provider_id": self.provider_id,
                },
            )
        else:
            rel_json = rel_response.json()
            for relationship in rel_json.get("result", []):
                parent = relationship.get("parent", {})
                if type(parent) is dict:
                    parent_id = relationship.get("parent", {}).get("value")
                else:
                    parent_id = None
                child = relationship.get("child", {})
                if type(child) is dict:
                    child_id = child.get("value")
                else:
                    child_id = None
                relationship_type_id = relationship.get("type", {}).get("value")
                relationship_type = relationship_types.get(relationship_type_id)
                if parent_id not in relationships:
                    relationships[parent_id] = {}
                relationships[parent_id][child_id] = relationship_type
            self.logger.info("Pulling relationships completed")

        self.logger.info("Mixing up all topology data")
        for entity in cmdb_data:
            sys_id = entity.get("sys_id")
            owned_by = entity.get("owned_by.name")
            environment = entity.get("environment")
            if environment is None:
                environment = ""
            topology_service = TopologyServiceInDto(
                source_provider_id=self.provider_id,
                service=sys_id,
                display_name=entity.get("name"),
                description=entity.get("short_description"),
                environment=environment,
                team=owned_by,
                dependencies=relationships.get(sys_id, {}),
                ip_address=entity.get("ip_address"),
                mac_address=entity.get("mac_address"),
            )
            topology.append(topology_service)

        self.logger.info(
            "Topology pulling completed",
            extra={
                "tenant_id": self.context_manager.tenant_id,
                "len_of_topology": len(topology),
                "using_access_token": self._access_token is not None,
                "provider_id": self.provider_id,
            },
        )
        return topology, {}

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(self, table_name: str = None, payload: dict = {}, **kwargs: dict):
        """
        Create a ticket or add activity to a ServiceNow incident.

        Args:
            table_name (str): The name of the table to create the ticket in.
            payload (dict): The ticket payload.
            ticket_id (str): The ticket ID (optional to update a ticket).
            fingerprint (str): The fingerprint of the ticket (optional to update a ticket).
        """
        headers = self._get_headers()
        auth = self._get_auth()

        # Handle adding comments/work notes
        if kwargs.get("comment") and kwargs.get("incident_sys_id"):
            return self._add_comment(
                kwargs["incident_sys_id"], kwargs["comment"]
            )
        if kwargs.get("work_note") and kwargs.get("incident_sys_id"):
            return self._add_work_note(
                kwargs["incident_sys_id"], kwargs["work_note"]
            )

        # otherwise, create the ticket
        if not table_name:
            raise ProviderException("Table name is required")

        # TODO - this could be separated into a ServicenowUpdateProvider once we support
        if "ticket_id" in kwargs:
            ticket_id = kwargs.pop("ticket_id")
            fingerprint = kwargs.pop("fingerprint")
            return self._notify_update(table_name, ticket_id, fingerprint)

        # In ServiceNow tables are lower case
        table_name = table_name.lower()

        url = f"{self.authentication_config.service_now_base_url}/api/now/table/{table_name}"
        # HTTP request
        response = requests.post(
            url,
            auth=auth,
            headers=headers,
            data=json.dumps(payload),
            verify=False,
        )

        if response.status_code == 201:  # HTTP status code for "Created"
            resp = response.json()
            self.logger.info(f"Created ticket: {resp}")
            result = resp.get("result")
            # Add link to ticket
            result["link"] = (
                f"{self.authentication_config.service_now_base_url}/now/nav/ui/classic/params/target/{table_name}.do%3Fsys_id%3D{result['sys_id']}"
            )
            return result
        # if the instance is down due to hibranate you'll get 200 instead of 201
        elif response.status_code == 200:
            raise ProviderException(
                "ServiceNow instance is down, you need to restart the instance."
            )

        else:
            self.logger.info(f"Failed to create ticket: {response.text}")
            response.raise_for_status()

    def _notify_update(self, table_name: str, ticket_id: str, fingerprint: str):
        url = f"{self.authentication_config.service_now_base_url}/api/now/table/{table_name}/{ticket_id}"
        headers = self._get_headers()
        auth = self._get_auth()

        response = requests.get(
            url,
            auth=auth,
            headers=headers,
            verify=False,
        )
        if response.status_code == 200:
            resp = response.text
            # if the instance is down due to hibranate you'll get 200 instead of 201
            if "Want to find out why instances hibernate?" in resp:
                raise ProviderException(
                    "ServiceNow instance is down, you need to restart the instance."
                )
            # else, we are ok
            else:
                resp = json.loads(resp)
            self.logger.info("Updated ticket", extra={"resp": resp})
            resp = resp.get("result")
            resp["fingerprint"] = fingerprint
            return resp
        else:
            self.logger.info("Failed to update ticket", extra={"resp": response.text})
            response.raise_for_status()


def _extract_display_value(field_value) -> str | None:
    """Helper to extract a display value from a ServiceNow field that
    may be a string, a dict with 'display_value'/'value', or empty."""
    if not field_value:
        return None
    if isinstance(field_value, dict):
        return field_value.get("display_value", field_value.get("value", ""))
    return str(field_value) if field_value else None


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os
    from unittest.mock import patch

    service_now_base_url = os.environ.get("SERVICENOW_BASE_URL", "https://meow.me")
    service_now_username = os.environ.get("SERVICENOW_USERNAME", "admin")
    service_now_password = os.environ.get("SERVICENOW_PASSWORD", "admin")
    mock_real_requests_with_json_data = (
        os.environ.get("MOCK_REAL_REQUESTS_WITH_JSON_DATA", "true").lower() == "true"
    )

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Service Now Provider",
        authentication={
            "service_now_base_url": service_now_base_url,
            "username": service_now_username,
            "password": service_now_password,
        },
    )
    provider = ServicenowProvider(
        context_manager, provider_id="servicenow", config=config
    )

    def mock_get(*args, **kwargs):
        """
        Mock topology responses using json files.
        """

        class MockResponse:
            def __init__(self):
                self.ok = True
                self.status_code = 200
                self.url = args[0]

            def json(self):
                if "cmdb_ci" in self.url:
                    with open(
                        os.path.join(os.path.dirname(__file__), "cmdb_ci.json")
                    ) as f:
                        return json.load(f)
                elif "cmdb_rel_type" in self.url:
                    with open(
                        os.path.join(os.path.dirname(__file__), "cmdb_rel_type.json")
                    ) as f:
                        return json.load(f)
                elif "cmdb_rel_ci" in self.url:
                    with open(
                        os.path.join(os.path.dirname(__file__), "cmdb_rel_ci.json")
                    ) as f:
                        return json.load(f)
                return {}

        return MockResponse()

    if mock_real_requests_with_json_data:
        with patch("requests.get", side_effect=mock_get):
            r = provider.pull_topology()
    else:
        r = provider.pull_topology()
    print(r)
