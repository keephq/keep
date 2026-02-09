"""
ServicenowProvider is a class that implements the BaseProvider interface for Service Now updates.
"""

import os
import dataclasses
import json
from datetime import datetime

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.db.topology import TopologyServiceInDto
from keep.api.models.incident import IncidentDto, IncidentStatus, IncidentSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseTopologyProvider, BaseIncidentProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod
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
    """Manage ServiceNow tickets and incidents with bidirectional activity sync."""

    PROVIDER_CATEGORY = ["Ticketing", "Incident Management"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="itil",
            description="The user can read/write tickets from the table",
            documentation_url="https://docs.servicenow.com/bundle/sandiego-platform-administration/page/administer/roles/reference/r_BaseSystemRoles.html",
            mandatory=True,
            alias="Read from database",
        )
    ]
    PROVIDER_TAGS = ["ticketing", "incident"]
    PROVIDER_DISPLAY_NAME = "Service Now"
    
    # Mapping ServiceNow incident states to Keep incident statuses
    STATUS_MAP = {
        "1": IncidentStatus.FIRING,  # New
        "2": IncidentStatus.FIRING,  # In Progress
        "3": IncidentStatus.ACKNOWLEDGED,  # On Hold
        "6": IncidentStatus.RESOLVED,  # Resolved
        "7": IncidentStatus.RESOLVED,  # Closed
        "8": IncidentStatus.RESOLVED,  # Canceled
    }
    
    # Mapping ServiceNow severity to Keep severity
    SEVERITY_MAP = {
        "1": IncidentSeverity.CRITICAL,  # Critical
        "2": IncidentSeverity.HIGH,      # High
        "3": IncidentSeverity.WARNING,   # Moderate
        "4": IncidentSeverity.INFO,      # Low
        "5": IncidentSeverity.INFO,      # Planning
    }
    
    PROVIDER_METHODS = [
        ProviderMethod(
            name="sync_incident_activities",
            func_name="sync_incident_activities",
            description="Sync activities between ServiceNow and Keep incidents",
            type="action",
        ),
        ProviderMethod(
            name="pull_servicenow_activities",
            func_name="_get_incident_activities",
            description="Pull activities from a ServiceNow incident",
            type="action",
        ),
        ProviderMethod(
            name="push_activity_to_servicenow",
            func_name="_add_incident_activity",
            description="Add an activity to a ServiceNow incident",
            type="action",
        ),
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

    def _get_auth_and_headers(self):
        """Get authentication and headers for ServiceNow API requests."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        auth = (
            (
                self.authentication_config.username,
                self.authentication_config.password,
            )
            if not self._access_token
            else None
        )
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return auth, headers

    def _get_incidents(self) -> list[IncidentDto]:
        """
        Get incidents from ServiceNow and convert them to Keep IncidentDto objects.
        
        Returns:
            list[IncidentDto]: List of incidents from ServiceNow
        """
        self.logger.info("Getting incidents from ServiceNow")
        
        auth, headers = self._get_auth_and_headers()
        
        # Query ServiceNow incident table
        url = f"{self.authentication_config.service_now_base_url}/api/now/table/incident"
        
        # Get active incidents, ordered by most recently updated
        params = {
            "sysparm_query": "active=true^ORDERBYDESCsys_updated_on",
            "sysparm_fields": "sys_id,number,short_description,description,state,impact,urgency,priority,opened_at,resolved_at,closed_at,opened_by,resolved_by,assigned_to,caller_id,sys_created_on,sys_updated_on",
            "sysparm_limit": 100,
        }
        
        try:
            response = requests.get(
                url,
                auth=auth,
                headers=headers,
                params=params,
                verify=False,
                timeout=30,
            )
            
            if not response.ok:
                self.logger.error(
                    "Failed to get incidents from ServiceNow",
                    extra={"status_code": response.status_code, "response": response.text},
                )
                raise ProviderException(
                    f"Failed to get incidents from ServiceNow: {response.status_code}"
                )
            
            sn_incidents = response.json().get("result", [])
            self.logger.info(f"Retrieved {len(sn_incidents)} incidents from ServiceNow")
            
            incidents = []
            for sn_incident in sn_incidents:
                incident = self._format_incident(sn_incident)
                if incident:
                    incidents.append(incident)
            
            return incidents
            
        except Exception as e:
            self.logger.exception("Failed to get incidents from ServiceNow")
            raise ProviderException(f"Failed to get incidents: {str(e)}")

    @staticmethod
    def _format_incident(sn_incident: dict, provider_instance: "ServicenowProvider" = None) -> IncidentDto:
        """
        Format a ServiceNow incident into a Keep IncidentDto.
        
        Args:
            sn_incident: ServiceNow incident data
            provider_instance: Optional provider instance for additional context
            
        Returns:
            IncidentDto: Formatted incident for Keep
        """
        # Parse timestamps
        def parse_datetime(dt_str):
            if not dt_str:
                return None
            try:
                # ServiceNow format: 2024-01-15 08:30:00
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                try:
                    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    return None
        
        # Map ServiceNow state to Keep status
        state = sn_incident.get("state", "1")
        status = ServicenowProvider.STATUS_MAP.get(state, IncidentStatus.FIRING)
        
        # Map priority/impact to severity
        impact = sn_incident.get("impact", "3")
        severity = ServicenowProvider.SEVERITY_MAP.get(impact, IncidentSeverity.INFO)
        
        # Generate a UUID from the sys_id
        import hashlib
        import uuid
        md5 = hashlib.md5()
        md5.update(sn_incident.get("sys_id", "").encode("utf-8"))
        incident_id = uuid.UUID(md5.hexdigest())
        
        # Build description from description field or short description
        description = sn_incident.get("description", "") or sn_incident.get("short_description", "")
        
        # Parse timestamps
        start_time = parse_datetime(sn_incident.get("opened_at"))
        end_time = parse_datetime(sn_incident.get("resolved_at") or sn_incident.get("closed_at"))
        
        # Get assignee
        assignee = None
        assigned_to = sn_incident.get("assigned_to")
        if assigned_to and isinstance(assigned_to, dict):
            assignee = assigned_to.get("display_value") or assigned_to.get("value")
        elif assigned_to:
            assignee = assigned_to
        
        # Get caller/reporter
        reporter = None
        caller = sn_incident.get("caller_id")
        if caller and isinstance(caller, dict):
            reporter = caller.get("display_value") or caller.get("value")
        elif caller:
            reporter = caller
        
        incident_dto = IncidentDto(
            id=incident_id,
            user_generated_name=sn_incident.get("short_description", "ServiceNow Incident"),
            user_summary=description,
            assignee=assignee,
            severity=severity,
            status=status,
            creation_time=start_time or datetime.utcnow(),
            start_time=start_time,
            end_time=end_time,
            is_predicted=False,
            is_candidate=False,
            alert_sources=["servicenow"],
            services=["servicenow"],
            fingerprint=sn_incident.get("number", sn_incident.get("sys_id")),
        )
        
        # Store ServiceNow-specific data for later use (activity sync, etc.)
        incident_dto._servicenow_data = {
            "sys_id": sn_incident.get("sys_id"),
            "number": sn_incident.get("number"),
            "state": state,
            "reporter": reporter,
        }
        
        return incident_dto

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
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        auth = (
            (
                self.authentication_config.username,
                self.authentication_config.password,
            )
            if not self._access_token
            else None
        )
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        if incident_id:
            request_url = f"{request_url}/{incident_id}"

        params = {"sysparm_offset": 0, "sysparm_limit": 100}
        # Add pagination parameters if not already set
        if sysparm_limit:
            params["sysparm_limit"] = (
                sysparm_limit  # Limit number of records per request
            )
        if sysparm_offset:
            params["sysparm_offset"] = 0  # Start from beginning

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

    def pull_topology(self) -> tuple[list[TopologyServiceInDto], dict]:
        # TODO: in scale, we'll need to use pagination around here
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        auth = (
            (
                self.authentication_config.username,
                self.authentication_config.password,
            )
            if not self._access_token
            else None
        )
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
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

    def _notify(self, table_name: str, payload: dict = {}, **kwargs: dict):
        """
        Create a ticket in ServiceNow.
        Args:
            table_name (str): The name of the table to create the ticket in.
            payload (dict): The ticket payload.
            ticket_id (str): The ticket ID (optional to update a ticket).
            fingerprint (str): The fingerprint of the ticket (optional to update a ticket).
        """
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        auth = (
            (
                self.authentication_config.username,
                self.authentication_config.password,
            )
            if not self._access_token
            else None
        )
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
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
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        auth = (
            (
                self.authentication_config.username,
                self.authentication_config.password,
            )
            if self._access_token
            else None
        )
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

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
            resp.raise_for_status()

    def _get_incident_activities(self, incident_id: str) -> list[dict]:
        """
        Get activities (work notes, comments) from a ServiceNow incident.
        
        Args:
            incident_id (str): The ServiceNow incident sys_id or number
            
        Returns:
            list[dict]: List of activity entries with author, timestamp, and content
        """
        auth, headers = self._get_auth_and_headers()

        # Query sys_journal_field table for work notes and comments
        # This is where ServiceNow stores journal entries
        url = f"{self.authentication_config.service_now_base_url}/api/now/table/sys_journal_field"
        
        # Build query to get entries for this incident
        # element_id is the sys_id of the incident
        params = {
            "sysparm_query": f"element_id={incident_id}^ORname=incident^element={incident_id}^ORDERBYsys_created_on",
            "sysparm_fields": "sys_id,sys_created_on,sys_created_by,element,value,field_label",
            "sysparm_limit": 100,
        }
        
        response = requests.get(
            url,
            auth=auth,
            headers=headers,
            params=params,
            verify=False,
            timeout=10,
        )
        
        if not response.ok:
            self.logger.error(
                "Failed to get incident activities",
                extra={
                    "incident_id": incident_id,
                    "status_code": response.status_code,
                    "response": response.text,
                },
            )
            return []
        
        activities = []
        for entry in response.json().get("result", []):
            activities.append({
                "id": entry.get("sys_id"),
                "timestamp": entry.get("sys_created_on"),
                "author": entry.get("sys_created_by"),
                "content": entry.get("value"),
                "type": entry.get("field_label", "Work notes"),
            })
        
        self.logger.info(
            "Retrieved incident activities",
            extra={"incident_id": incident_id, "count": len(activities)},
        )
        return activities

    def _add_incident_activity(
        self, 
        incident_id: str, 
        content: str, 
        activity_type: str = "work_notes"
    ) -> dict:
        """
        Add an activity (work note or comment) to a ServiceNow incident.
        
        Args:
            incident_id (str): The ServiceNow incident sys_id
            content (str): The activity content to add
            activity_type (str): Either "work_notes" or "comments"
            
        Returns:
            dict: The created activity details
        """
        auth, headers = self._get_auth_and_headers()

        # Map activity type to ServiceNow field
        field_name = "work_notes" if activity_type == "work_notes" else "comments"
        
        url = f"{self.authentication_config.service_now_base_url}/api/now/table/incident/{incident_id}"
        
        # ServiceNow requires work notes to be added via update
        payload = {
            field_name: content,
        }
        
        response = requests.patch(
            url,
            auth=auth,
            headers=headers,
            data=json.dumps(payload),
            verify=False,
            timeout=10,
        )
        
        if not response.ok:
            self.logger.error(
                "Failed to add incident activity",
                extra={
                    "incident_id": incident_id,
                    "status_code": response.status_code,
                    "response": response.text,
                },
            )
            response.raise_for_status()
        
        result = response.json().get("result", {})
        self.logger.info(
            "Added incident activity",
            extra={
                "incident_id": incident_id,
                "activity_type": activity_type,
                "activity_id": result.get("sys_id"),
            },
        )
        return result

    def sync_incident_activities(
        self, 
        servicenow_incident_id: str, 
        keep_activities: list[dict] = None,
        sync_to_servicenow: bool = True,
        sync_from_servicenow: bool = True,
    ) -> dict:
        """
        Sync activities between ServiceNow and Keep incidents bidirectionally.
        
        This method pulls activities from ServiceNow and pushes Keep activities to ServiceNow,
        enabling bidirectional synchronization of incident comments and work notes.
        
        Args:
            servicenow_incident_id (str): The ServiceNow incident sys_id
            keep_activities (list[dict], optional): Activities from Keep to push to ServiceNow.
                Each activity should have: content (str), type (str, optional - "work_notes" or "comments")
            sync_to_servicenow (bool): Whether to push Keep activities to ServiceNow (default: True)
            sync_from_servicenow (bool): Whether to pull ServiceNow activities (default: True)
            
        Returns:
            dict: Sync result containing:
                - servicenow_activities: List of activities from ServiceNow
                - synced_to_servicenow: List of activities pushed to ServiceNow with status
                - sync_status: "success" or "partial" or "failed"
        """
        self.logger.info(
            "Starting bidirectional incident activity sync",
            extra={
                "servicenow_incident_id": servicenow_incident_id, 
                "keep_activities_count": len(keep_activities) if keep_activities else 0,
                "sync_to_servicenow": sync_to_servicenow,
                "sync_from_servicenow": sync_from_servicenow,
            },
        )
        
        result = {
            "servicenow_activities": [],
            "synced_to_servicenow": [],
            "sync_status": "success",
        }
        
        try:
            # Pull activities from ServiceNow
            if sync_from_servicenow:
                result["servicenow_activities"] = self._get_incident_activities(servicenow_incident_id)
            
            # Push Keep activities to ServiceNow
            if sync_to_servicenow and keep_activities:
                for activity in keep_activities:
                    try:
                        sync_result = self._add_incident_activity(
                            incident_id=servicenow_incident_id,
                            content=activity.get("content", ""),
                            activity_type=activity.get("type", "work_notes"),
                        )
                        result["synced_to_servicenow"].append({
                            "keep_activity": activity,
                            "servicenow_result": sync_result,
                            "status": "success",
                        })
                    except Exception as e:
                        self.logger.error(
                            "Failed to sync activity to ServiceNow",
                            extra={"activity": activity, "error": str(e)},
                        )
                        result["synced_to_servicenow"].append({
                            "keep_activity": activity,
                            "status": "failed",
                            "error": str(e),
                        })
                        result["sync_status"] = "partial"
            
            # Check if any sync to ServiceNow failed
            if result["sync_status"] != "partial" and keep_activities:
                failed_count = sum(1 for s in result["synced_to_servicenow"] if s["status"] == "failed")
                if failed_count == len(keep_activities) and len(keep_activities) > 0:
                    result["sync_status"] = "failed"
                elif failed_count > 0:
                    result["sync_status"] = "partial"
                    
        except Exception as e:
            self.logger.exception("Incident activity sync failed")
            result["sync_status"] = "failed"
            result["error"] = str(e)
        
        self.logger.info(
            "Bidirectional incident activity sync completed",
            extra={
                "servicenow_incident_id": servicenow_incident_id,
                "servicenow_activities_count": len(result["servicenow_activities"]),
                "synced_count": len(result["synced_to_servicenow"]),
                "sync_status": result["sync_status"],
            },
        )
        
        return result


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
