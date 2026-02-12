"""
ServicenowProvider is a class that implements the BaseProvider interface for Service Now updates.
"""

import dataclasses
import datetime
import json
import os
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
    """Manage ServiceNow tickets."""

    PROVIDER_CATEGORY = ["Ticketing"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="itil",
            description="The user can read/write tickets from the table",
            documentation_url="https://docs.servicenow.com/bundle/sandiego-platform-administration/page/administer/roles/reference/r_BaseSystemRoles.html",
            mandatory=True,
            alias="Read from datahase",
        )
    ]
    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_DISPLAY_NAME = "Service Now"

    # Default mapping for ServiceNow states to Keep states
    # https://docs.servicenow.com/bundle/vancouver-it-service-management/page/product/incident-management/concept/c_IncidentStateModel.html
    INCIDENT_STATUS_MAP = {
        "1": IncidentStatus.FIRING,  # New
        "2": IncidentStatus.FIRING,  # In Progress
        "3": IncidentStatus.ACKNOWLEDGED,  # On Hold
        "6": IncidentStatus.RESOLVED,  # Resolved
        "7": IncidentStatus.RESOLVED,  # Closed
        "8": IncidentStatus.DELETED,  # Canceled
    }

    INCIDENT_SEVERITIES_MAP = {
        "1": IncidentSeverity.CRITICAL,
        "2": IncidentSeverity.HIGH,
        "3": IncidentSeverity.WARNING,
        "4": IncidentSeverity.INFO,
        "5": IncidentSeverity.LOW,
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

    def _query(
        self,
        table_name: str,
        incident_id: str = None,
        sysparm_limit: int = 100,
        sysparm_offset: int = 0,
        sysparm_query: str = None,
        **kwargs: dict,
    ):
        """
        Query ServiceNow for records.
        Args:
            table_name (str): The name of the table to query.
            incident_id (str): The incident ID to query.
            sysparm_limit (int): The maximum number of records to return.
            sysparm_offset (int): The offset to start from.
            sysparm_query (str): The query to filter records.
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

        params = {"sysparm_offset": sysparm_offset, "sysparm_limit": sysparm_limit}
        if sysparm_query:
            params["sysparm_query"] = sysparm_query

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
        Create or update a ticket in ServiceNow.
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
            
        if not table_name:
            raise ProviderException("Table name is required")

        # In ServiceNow tables are lower case
        table_name = table_name.lower()

        # Update logic
        ticket_id = kwargs.get("ticket_id") or payload.get("sys_id")
        if ticket_id:
            return self._notify_update(table_name, ticket_id, payload)

        url = f"{self.authentication_config.service_now_base_url}/api/now/table/{table_name}"
        # HTTP request
        response = requests.post(
            url,
            auth=auth,
            headers=headers,
            data=json.dumps(payload),
            verify=False,
            timeout=10,
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

    def _notify_update(self, table_name: str, ticket_id: str, payload: dict):
        """
        Update a ticket in ServiceNow using PATCH.
        """
        url = f"{self.authentication_config.service_now_base_url}/api/now/table/{table_name}/{ticket_id}"
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

        response = requests.patch(
            url,
            auth=auth,
            headers=headers,
            data=json.dumps(payload),
            verify=False,
            timeout=10,
        )
        
        if response.ok:
            resp = response.json()
            self.logger.info("Updated ticket", extra={"resp": resp})
            result = resp.get("result")
            result["link"] = (
                f"{self.authentication_config.service_now_base_url}/now/nav/ui/classic/params/target/{table_name}.do%3Fsys_id%3D{result['sys_id']}"
            )
            return result
        else:
            self.logger.error("Failed to update ticket", extra={"resp": response.text})
            response.raise_for_status()

    def add_incident_comment(self, incident_id: str, comment: str, is_internal: bool = False):
        """
        Add a comment or work note to an incident.
        """
        field = "work_notes" if is_internal else "comments"
        payload = {field: comment}
        return self._notify(table_name="incident", payload=payload, ticket_id=incident_id)

    def _get_incidents(self) -> list[IncidentDto]:
        """
        Fetch incidents from ServiceNow.
        """
        self.logger.info("Fetching incidents from ServiceNow")
        
        # Fetch active incidents
        # We can also add more filters here via config if needed
        incidents_data = self._query(table_name="incident", sysparm_query="active=true")
        
        if not incidents_data:
            return []
            
        # Fetch journal entries for these incidents
        sys_ids = [incident.get("sys_id") for incident in incidents_data]
        journal_entries = self._get_journal_entries(sys_ids)
        
        incidents = []
        for data in incidents_data:
            incident_dto = self._format_incident(data, self)
            if incident_dto:
                # Attach activities (comments/work_notes)
                incident_sys_id = data.get("sys_id")
                activities = journal_entries.get(incident_sys_id, [])
                # Attach to extra fields as Keep doesn't have activities in DTO yet
                incident_dto.activities = activities
                incidents.append(incident_dto)
                
        self.logger.info(f"Fetched {len(incidents)} incidents from ServiceNow")
        return incidents

    @staticmethod
    def _format_incident(
        data: dict, provider_instance: "ServicenowProvider" = None
    ) -> IncidentDto:
        """
        Format ServiceNow incident data into IncidentDto.
        """
        if not data:
            return None
            
        sys_id = data.get("sys_id")
        number = data.get("number")
        
        # Map status
        state = data.get("state")
        status = ServicenowProvider.INCIDENT_STATUS_MAP.get(state, IncidentStatus.FIRING)
        
        # Map severity
        # ServiceNow has 'severity', 'urgency', 'priority'
        # Usually priority is used, but the issue mentioned severity
        sn_severity = data.get("severity", "3")
        severity = ServicenowProvider.INCIDENT_SEVERITIES_MAP.get(sn_severity, IncidentSeverity.INFO)
        
        # Creation time
        created_on = data.get("sys_created_on")
        if created_on:
            try:
                # ServiceNow format: YYYY-MM-DD HH:MM:SS
                creation_time = datetime.datetime.strptime(created_on, "%Y-%m-%d %H:%M:%S")
            except Exception:
                creation_time = datetime.datetime.utcnow()
        else:
            creation_time = datetime.datetime.utcnow()
            
        # Assignee
        assigned_to = data.get("assigned_to")
        assignee = None
        if isinstance(assigned_to, dict):
            assignee = assigned_to.get("display_value") or assigned_to.get("value")
        elif assigned_to:
            assignee = assigned_to

        return IncidentDto(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"servicenow-{sys_id}"), # Deterministic UUID
            user_generated_name=f"{number}: {data.get('short_description')}",
            user_summary=data.get("description") or data.get("short_description"),
            status=status,
            severity=severity,
            creation_time=creation_time,
            assignee=assignee,
            alert_sources=["servicenow"],
            services=[], # Can be populated from cmdb if needed
            is_predicted=False,
            is_candidate=False,
            fingerprint=sys_id,
        )

    def _get_journal_entries(self, element_ids: list[str]) -> dict[str, list[dict]]:
        """
        Fetch journal entries (comments/work notes) for given sys_ids.
        """
        if not element_ids:
            return {}
            
        # ServiceNow sysparm_query supports IN operator
        query = f"element_idIN{','.join(element_ids)}"
        entries_data = self._query(table_name="sys_journal_field", sysparm_query=query)
        
        journal_map = {}
        for entry in entries_data:
            element_id = entry.get("element_id")
            if element_id not in journal_map:
                journal_map[element_id] = []
            
            # Format entry to a standard Keep activity format
            activity = {
                "id": entry.get("sys_id"),
                "text": entry.get("value"),
                "author": entry.get("sys_created_by"),
                "timestamp": entry.get("sys_created_on"),
                "type": entry.get("element"), # 'comments' or 'work_notes'
            }
            journal_map[element_id].append(activity)
            
        return journal_map


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

    service_now_base_url = os.environ.get("SERVICENOW_BASE_URL", "https://dev12345.service-now.com")
    service_now_username = os.environ.get("SERVICENOW_USERNAME", "admin")
    service_now_password = os.environ.get("SERVICENOW_PASSWORD", "admin")

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
        class MockResponse:
            def __init__(self, json_data):
                self.ok = True
                self.status_code = 200
                self.json_data = json_data
            def json(self):
                return self.json_data
        
        url = args[0]
        if "incident" in url:
            return MockResponse({"result": [{"sys_id": "123", "number": "INC123", "short_description": "Test", "state": "1", "sys_created_on": "2024-01-01 10:00:00"}]})
        elif "sys_journal_field" in url:
            return MockResponse({"result": [{"element_id": "123", "value": "Test comment", "sys_created_by": "admin", "sys_created_on": "2024-01-01 10:05:00", "element": "comments"}]})
        return MockResponse({"result": []})

    with patch("requests.get", side_effect=mock_get):
        incidents = provider.get_incidents()
        print(f"Pulled {len(incidents)} incidents")
        for inc in incidents:
            print(f"Incident: {inc.fingerprint}, Activities: {inc.activities}")
