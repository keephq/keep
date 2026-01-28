"""
ServicenowProvider is a class that implements the BaseProvider interface for Service Now updates.

Supports:
- Topology pulling from CMDB
- Ticket creation and updates
- Pulling incidents as Keep alerts
- Pulling incidents as Keep incidents (with activity / comments / work notes)

ServiceNow REST API references:
    Table API: /api/now/table/{tableName}
    Journal (activity): /api/now/table/sys_journal_field
"""

import dataclasses
import datetime
import hashlib
import json
import os
import typing
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
    """Manage ServiceNow tickets and pull incidents."""

    PROVIDER_DISPLAY_NAME = "Service Now"
    PROVIDER_CATEGORY = ["Ticketing", "Incident Management"]
    PROVIDER_TAGS = ["ticketing", "alert", "incident"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="itil",
            description="The user can read/write tickets from the table",
            documentation_url="https://docs.servicenow.com/bundle/sandiego-platform-administration/page/administer/roles/reference/r_BaseSystemRoles.html",
            mandatory=True,
            alias="Read from datahase",
        ),
    ]

    FINGERPRINT_FIELDS = ["incident_id"]

    # ── ServiceNow incident state → Keep AlertStatus ──────────────────
    # Standard OOTB states: 1=New, 2=InProgress, 3=OnHold, 6=Resolved, 7=Closed, 8=Canceled
    STATUS_MAP: dict[int, AlertStatus] = {
        1: AlertStatus.FIRING,        # New
        2: AlertStatus.FIRING,        # In Progress
        3: AlertStatus.ACKNOWLEDGED,  # On Hold
        6: AlertStatus.RESOLVED,      # Resolved
        7: AlertStatus.RESOLVED,      # Closed
        8: AlertStatus.SUPPRESSED,    # Canceled
    }

    INCIDENT_STATUS_MAP: dict[int, IncidentStatus] = {
        1: IncidentStatus.FIRING,        # New
        2: IncidentStatus.FIRING,        # In Progress
        3: IncidentStatus.ACKNOWLEDGED,  # On Hold
        6: IncidentStatus.RESOLVED,      # Resolved
        7: IncidentStatus.RESOLVED,      # Closed
        8: IncidentStatus.RESOLVED,      # Canceled
    }

    # ── ServiceNow priority → Keep AlertSeverity ──────────────────────
    # 1=Critical, 2=High, 3=Moderate, 4=Low, 5=Planning
    SEVERITY_MAP: dict[int, AlertSeverity] = {
        1: AlertSeverity.CRITICAL,
        2: AlertSeverity.HIGH,
        3: AlertSeverity.WARNING,
        4: AlertSeverity.LOW,
        5: AlertSeverity.INFO,
    }

    INCIDENT_SEVERITY_MAP: dict[int, IncidentSeverity] = {
        1: IncidentSeverity.CRITICAL,
        2: IncidentSeverity.HIGH,
        3: IncidentSeverity.WARNING,
        4: IncidentSeverity.LOW,
        5: IncidentSeverity.INFO,
    }

    # Fields to retrieve from the incident table
    INCIDENT_FIELDS = [
        "sys_id",
        "number",
        "short_description",
        "description",
        "state",
        "priority",
        "severity",
        "impact",
        "urgency",
        "category",
        "subcategory",
        "assignment_group",
        "assigned_to",
        "caller_id",
        "opened_by",
        "opened_at",
        "closed_at",
        "resolved_at",
        "sys_updated_on",
        "sys_created_on",
        "close_code",
        "close_notes",
        "cmdb_ci",
        "business_service",
        "contact_type",
    ]

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

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_auth(self):
        """Return auth tuple or None when using OAuth tokens."""
        if self._access_token:
            return None
        return (
            self.authentication_config.username,
            self.authentication_config.password,
        )

    def _get_headers(self) -> dict:
        """Build common request headers."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    @staticmethod
    def _get_incident_id(incident_number: str) -> uuid.UUID:
        """Create a deterministic UUID from a ServiceNow incident number."""
        md5 = hashlib.md5()
        md5.update(incident_number.encode("utf-8"))
        return uuid.UUID(md5.hexdigest())

    @staticmethod
    def _parse_snow_datetime(value: str | None) -> datetime.datetime | None:
        """Parse a ServiceNow datetime string (YYYY-MM-DD HH:MM:SS) into a datetime."""
        if not value:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.datetime.strptime(value, fmt).replace(
                    tzinfo=datetime.timezone.utc
                )
            except ValueError:
                continue
        return None

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        """Safely convert a value to int."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _display_value(field) -> str:
        """Extract display value from a ServiceNow field that may be a dict or string."""
        if isinstance(field, dict):
            return field.get("display_value", field.get("value", ""))
        return str(field) if field else ""

    # ── Config / scopes ──────────────────────────────────────────────

    def validate_config(self):
        self.authentication_config = ServicenowProviderAuthConfig(
            **self.config.authentication
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

    def dispose(self):
        """No need to dispose of anything, so just do nothing."""
        pass

    # ── Core API helpers ─────────────────────────────────────────────

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

    def _query_incidents(
        self,
        sysparm_limit: int = 100,
        sysparm_offset: int = 0,
        sysparm_query: str = "",
    ) -> list[dict]:
        """
        Pull incidents from the ServiceNow incident table.

        Args:
            sysparm_limit: Max records to return.
            sysparm_offset: Pagination offset.
            sysparm_query: Encoded query string (e.g. "state!=7^state!=8" for non-closed).

        Returns:
            A list of incident records.
        """
        url = f"{self.authentication_config.service_now_base_url}/api/now/table/incident"
        headers = self._get_headers()
        auth = self._get_auth()

        params = {
            "sysparm_limit": sysparm_limit,
            "sysparm_offset": sysparm_offset,
            "sysparm_fields": ",".join(self.INCIDENT_FIELDS),
            "sysparm_display_value": "all",  # Get both value and display_value
        }
        if sysparm_query:
            params["sysparm_query"] = sysparm_query

        all_records: list[dict] = []
        offset = sysparm_offset

        while True:
            params["sysparm_offset"] = offset
            response = requests.get(
                url,
                headers=headers,
                auth=auth,
                params=params,
                verify=False,
                timeout=30,
            )

            if not response.ok:
                self.logger.error(
                    "Failed to query incidents",
                    extra={
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                )
                break

            results = response.json().get("result", [])
            if not results:
                break

            all_records.extend(results)

            # If we got fewer records than the limit, we've reached the end
            if len(results) < sysparm_limit:
                break

            offset += sysparm_limit

        return all_records

    def _query_incident_activity(
        self, incident_sys_ids: list[str]
    ) -> dict[str, list[dict]]:
        """
        Pull activity (comments and work notes) for a list of incidents from
        the sys_journal_field table.

        Args:
            incident_sys_ids: List of incident sys_id values.

        Returns:
            A dict mapping sys_id → list of journal entries.
        """
        if not incident_sys_ids:
            return {}

        url = f"{self.authentication_config.service_now_base_url}/api/now/table/sys_journal_field"
        headers = self._get_headers()
        auth = self._get_auth()

        # Build encoded query: name=incident^element_idIN<comma-separated ids>
        ids_csv = ",".join(incident_sys_ids)
        sysparm_query = f"name=incident^element_idIN{ids_csv}^ORDERBYDESCsys_created_on"

        params = {
            "sysparm_query": sysparm_query,
            "sysparm_fields": "sys_id,element_id,element,value,sys_created_on,sys_created_by,name",
            "sysparm_limit": 500,
        }

        response = requests.get(
            url,
            headers=headers,
            auth=auth,
            params=params,
            verify=False,
            timeout=30,
        )

        activity_map: dict[str, list[dict]] = {sid: [] for sid in incident_sys_ids}

        if not response.ok:
            self.logger.warning(
                "Failed to query incident activity from sys_journal_field",
                extra={
                    "status_code": response.status_code,
                    "response": response.text,
                },
            )
            return activity_map

        for entry in response.json().get("result", []):
            element_id = entry.get("element_id")
            if element_id in activity_map:
                activity_map[element_id].append(
                    {
                        "type": entry.get("element", ""),  # "comments" or "work_notes"
                        "value": entry.get("value", ""),
                        "created_on": entry.get("sys_created_on", ""),
                        "created_by": entry.get("sys_created_by", ""),
                    }
                )

        return activity_map

    # ── Pull alerts (incidents as alerts) ────────────────────────────

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull incidents from ServiceNow and return them as Keep AlertDto objects.

        This queries all non-closed, non-canceled incidents by default,
        maps their state/priority to Keep's AlertStatus/AlertSeverity, and
        enriches each alert with recent activity (comments + work notes).
        """
        alerts: list[AlertDto] = []

        try:
            self.logger.info("Pulling incidents from ServiceNow as alerts")

            # Pull active + recently-resolved incidents
            raw_incidents = self._query_incidents(
                sysparm_query="ORDERBYDESCsys_updated_on",
                sysparm_limit=100,
            )

            if not raw_incidents:
                self.logger.info("No incidents found in ServiceNow")
                return alerts

            # Gather sys_ids to fetch activity in bulk
            sys_ids = [
                inc.get("sys_id", {}).get("value", inc.get("sys_id", ""))
                if isinstance(inc.get("sys_id"), dict)
                else inc.get("sys_id", "")
                for inc in raw_incidents
            ]
            activity_map = self._query_incident_activity(sys_ids)

            for incident in raw_incidents:
                try:
                    sys_id = self._display_value(incident.get("sys_id"))
                    alert = self._format_alert(
                        incident,
                        provider_instance=self,
                        activity=activity_map.get(sys_id, []),
                    )
                    alerts.append(alert)
                except Exception as e:
                    self.logger.warning(
                        "Failed to format ServiceNow incident as alert: %s",
                        e,
                        extra={"incident": incident.get("number", "unknown")},
                    )

            self.logger.info(
                "Collected %d alerts from ServiceNow",
                len(alerts),
            )
        except Exception as e:
            self.logger.error("Error pulling alerts from ServiceNow: %s", e)

        return alerts

    @staticmethod
    def _format_alert(
        event: dict,
        provider_instance: "ServicenowProvider" = None,
        activity: list[dict] | None = None,
    ) -> AlertDto:
        """
        Format a ServiceNow incident record into a Keep AlertDto.

        Args:
            event: A ServiceNow incident record (with display_value/value).
            provider_instance: The provider instance (used for building URLs).
            activity: List of journal entries for this incident.

        Returns:
            An AlertDto representing the ServiceNow incident.
        """
        # Helper to extract value from {value, display_value} dicts
        def _val(field_name: str, use_display: bool = False) -> str:
            raw = event.get(field_name, "")
            if isinstance(raw, dict):
                return raw.get("display_value" if use_display else "value", "")
            return str(raw) if raw else ""

        sys_id = _val("sys_id")
        number = _val("number")
        state = ServicenowProvider._safe_int(_val("state"))
        priority = ServicenowProvider._safe_int(_val("priority"))

        status = ServicenowProvider.STATUS_MAP.get(state, AlertStatus.FIRING)
        severity = ServicenowProvider.SEVERITY_MAP.get(priority, AlertSeverity.INFO)

        # Parse timestamps
        opened_at = _val("opened_at")
        updated_on = _val("sys_updated_on")
        last_received = updated_on or opened_at or datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()

        # Build description from short_description + description
        short_desc = _val("short_description")
        long_desc = _val("description")
        description = short_desc
        if long_desc and long_desc != short_desc:
            description = f"{short_desc}\n\n{long_desc}"

        # Build URL to the incident in ServiceNow
        url = None
        if provider_instance:
            base = str(
                provider_instance.authentication_config.service_now_base_url
            ).rstrip("/")
            url = f"{base}/nav_to.do?uri=incident.do?sys_id={sys_id}"

        # Build activity/enrichment summary
        enrichments: dict = {}
        if activity:
            comments = [
                a for a in activity if a.get("type") == "comments"
            ]
            work_notes = [
                a for a in activity if a.get("type") == "work_notes"
            ]
            enrichments["comments_count"] = len(comments)
            enrichments["work_notes_count"] = len(work_notes)
            enrichments["recent_activity"] = activity[:10]  # Last 10 entries
            if comments:
                enrichments["last_comment"] = comments[0].get("value", "")
                enrichments["last_comment_by"] = comments[0].get("created_by", "")
                enrichments["last_comment_at"] = comments[0].get("created_on", "")
            if work_notes:
                enrichments["last_work_note"] = work_notes[0].get("value", "")
                enrichments["last_work_note_by"] = work_notes[0].get("created_by", "")
                enrichments["last_work_note_at"] = work_notes[0].get("created_on", "")

        return AlertDto(
            id=sys_id,
            name=f"[{number}] {short_desc}" if number else short_desc,
            status=status,
            severity=severity,
            lastReceived=last_received,
            firingStartTime=opened_at or None,
            description=description,
            source=["servicenow"],
            url=url,
            fingerprint=number or sys_id,
            # ServiceNow-specific fields
            incident_id=number,
            incident_sys_id=sys_id,
            incident_state=state,
            incident_state_display=_val("state", use_display=True),
            priority=priority,
            priority_display=_val("priority", use_display=True),
            impact=_val("impact", use_display=True),
            urgency=_val("urgency", use_display=True),
            category=_val("category", use_display=True),
            subcategory=_val("subcategory", use_display=True),
            assignment_group=_val("assignment_group", use_display=True),
            assigned_to=_val("assigned_to", use_display=True),
            caller=_val("caller_id", use_display=True),
            opened_by=_val("opened_by", use_display=True),
            close_code=_val("close_code"),
            close_notes=_val("close_notes"),
            cmdb_ci=_val("cmdb_ci", use_display=True),
            business_service=_val("business_service", use_display=True),
            contact_type=_val("contact_type"),
            # Enrichments from activity
            **enrichments,
        )

    # ── Pull incidents ───────────────────────────────────────────────

    def _get_incidents(self) -> list[IncidentDto]:
        """
        Pull incidents from ServiceNow and return them as Keep IncidentDto objects.
        Each incident includes its alerts (the incident itself as an AlertDto)
        and activity enrichment data.
        """
        incidents: list[IncidentDto] = []

        try:
            self.logger.info("Pulling incidents from ServiceNow")

            raw_incidents = self._query_incidents(
                sysparm_query="ORDERBYDESCsys_updated_on",
                sysparm_limit=100,
            )

            if not raw_incidents:
                self.logger.info("No incidents found in ServiceNow")
                return incidents

            # Fetch activity for all incidents in bulk
            sys_ids = [
                self._display_value(inc.get("sys_id"))
                for inc in raw_incidents
            ]
            activity_map = self._query_incident_activity(sys_ids)

            for raw_incident in raw_incidents:
                try:
                    incident = self._format_incident(
                        {"event": raw_incident},
                        provider_instance=self,
                        activity=activity_map,
                    )
                    if incident:
                        # Attach the incident's own alert representation
                        sys_id = self._display_value(raw_incident.get("sys_id"))
                        alert = self._format_alert(
                            raw_incident,
                            provider_instance=self,
                            activity=activity_map.get(sys_id, []),
                        )
                        incident._alerts = [alert]
                        incidents.append(incident)
                except Exception as e:
                    self.logger.warning(
                        "Failed to format ServiceNow incident: %s",
                        e,
                        extra={"incident": raw_incident.get("number", "unknown")},
                    )

            self.logger.info(
                "Collected %d incidents from ServiceNow",
                len(incidents),
            )
        except Exception as e:
            self.logger.error("Error pulling incidents from ServiceNow: %s", e)

        return incidents

    @staticmethod
    def _format_incident(
        event: dict,
        provider_instance: "ServicenowProvider" = None,
        activity: dict[str, list[dict]] | None = None,
    ) -> IncidentDto | None:
        """
        Format a ServiceNow incident record into a Keep IncidentDto.

        Args:
            event: A dict with key "event" containing the raw incident record.
            provider_instance: The provider instance.
            activity: A dict mapping sys_id → list of journal entries.

        Returns:
            An IncidentDto, or None if the record can't be formatted.
        """
        raw = event.get("event", event)

        def _val(field_name: str, use_display: bool = False) -> str:
            field = raw.get(field_name, "")
            if isinstance(field, dict):
                return field.get("display_value" if use_display else "value", "")
            return str(field) if field else ""

        sys_id = _val("sys_id")
        number = _val("number")
        if not number:
            return None

        state = ServicenowProvider._safe_int(_val("state"))
        priority = ServicenowProvider._safe_int(_val("priority"))

        status = ServicenowProvider.INCIDENT_STATUS_MAP.get(
            state, IncidentStatus.FIRING
        )
        severity = ServicenowProvider.INCIDENT_SEVERITY_MAP.get(
            priority, IncidentSeverity.INFO
        )

        # Timestamps
        opened_at = ServicenowProvider._parse_snow_datetime(_val("opened_at"))
        resolved_at = ServicenowProvider._parse_snow_datetime(_val("resolved_at"))
        closed_at = ServicenowProvider._parse_snow_datetime(_val("closed_at"))
        created_on = ServicenowProvider._parse_snow_datetime(_val("sys_created_on"))
        updated_on = ServicenowProvider._parse_snow_datetime(_val("sys_updated_on"))

        incident_id = ServicenowProvider._get_incident_id(number)

        service = _val("business_service", use_display=True) or _val(
            "cmdb_ci", use_display=True
        )
        services = [service] if service else []

        assignee = _val("assigned_to", use_display=True) or None

        short_desc = _val("short_description")

        # Build enrichments from activity
        enrichments: dict = {}
        if activity:
            incident_activity = activity.get(sys_id, [])
            if incident_activity:
                comments = [a for a in incident_activity if a.get("type") == "comments"]
                work_notes = [
                    a for a in incident_activity if a.get("type") == "work_notes"
                ]
                enrichments["comments_count"] = len(comments)
                enrichments["work_notes_count"] = len(work_notes)
                enrichments["recent_activity"] = incident_activity[:10]

        return IncidentDto(
            id=incident_id,
            user_generated_name=f"SNOW-{number}: {short_desc}",
            status=status,
            severity=severity,
            creation_time=created_on or opened_at,
            start_time=opened_at,
            end_time=closed_at or resolved_at,
            last_seen_time=updated_on,
            alert_sources=["servicenow"],
            alerts_count=1,
            services=services,
            assignee=assignee,
            is_predicted=False,
            is_candidate=False,
            fingerprint=number,
            enrichments=enrichments,
        )

    # ── Topology ─────────────────────────────────────────────────────

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

    # ── Notify (ticket creation / update) ────────────────────────────

    def _notify(self, table_name: str, payload: dict = {}, **kwargs: dict):
        """
        Create a ticket in ServiceNow.
        Args:
            table_name (str): The name of the table to create the ticket in.
            payload (dict): The ticket payload.
            ticket_id (str): The ticket ID (optional to update a ticket).
            fingerprint (str): The fingerprint of the ticket (optional to update a ticket).
        """
        headers = self._get_headers()
        auth = self._get_auth()

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
