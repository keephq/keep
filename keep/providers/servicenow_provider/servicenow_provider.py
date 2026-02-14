"""
ServicenowProvider is a class that implements the BaseProvider interface for Service Now updates.
"""

import os
import dataclasses
import json

import pydantic
import requests
from requests.auth import HTTPBasicAuth
from dateutil.parser import parse

from keep.api.models.db.topology import TopologyServiceInDto
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.api.models.db.incident import IncidentStatus
from keep.api.models.incident import IncidentDto
from keep.providers.base.base_provider import BaseTopologyProvider, BaseIncidentProvider
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
        sysparm_display_value: bool = True,
        **kwargs: dict,
    ):
        """
        Query ServiceNow for records.
        Args:
            table_name (str): The name of the table to query.
            incident_id (str): The incident ID to query.
            sysparm_limit (int): The maximum number of records to return.
            sysparm_offset (int): The offset to start from.
            sysparm_query (str): The query to filter results.
            sysparm_display_value (bool): Whether to return display values.
        """
        request_url = f"{self.authentication_config.service_now_base_url}/api/now/table/{table_name}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        auth = None
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        else:
            auth = (
                self.authentication_config.username,
                self.authentication_config.password,
            )

        if incident_id:
            request_url = f"{request_url}/{incident_id}"

        params = {
            "sysparm_limit": sysparm_limit,
            "sysparm_offset": sysparm_offset,
            "sysparm_display_value": str(sysparm_display_value).lower(),
        }

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

        try:
            response_json = response.json()
        except Exception:
            self.logger.error(
                f"Failed to parse JSON response from {table_name}",
                extra={"status_code": response.status_code, "response": response.text},
            )
            return []

        return response_json.get("result", [])

    def _get_incidents(self) -> list[IncidentDto]:
        """
        Get incidents from ServiceNow.
        """
        # ServiceNow sys_updated_on format is YYYY-MM-DD HH:MM:SS
        # Use sysparm_display_value=false for consistent UTC/internal format
        query = "active=true"
        # Use delta-polling based on last_pull_time
        if self.config.last_pull_time:
            query += f"^sys_updated_on>{self.config.last_pull_time.strftime('%Y-%m-%d %H:%M:%S')}"

        incidents_data = []
        offset = 0
        limit = 100
        
        while True:
            batch = self._query(
                "incident", 
                sysparm_query=query, 
                sysparm_limit=limit, 
                sysparm_offset=offset,
                sysparm_display_value=False
            )
            if not batch:
                break
            incidents_data.extend(batch)
            if len(batch) < limit:
                break
            offset += limit

        # Batch fetch activity stream for all incidents to avoid N+1 query problem
        sys_ids = [incident.get("sys_id") for incident in incidents_data]
        activity_map = self._get_batch_activity_stream(sys_ids)

        incidents = []
        for incident_data in incidents_data:
            formatted_incident = self._format_incident(
                incident_data, 
                activity_stream=activity_map.get(incident_data.get("sys_id"), [])
            )
            incidents.append(formatted_incident)
        return incidents

    @staticmethod
    def _format_incident(
        incident_data: dict, activity_stream: list[dict] = None
    ) -> IncidentDto:
        """
        Format a ServiceNow incident into a Keep IncidentDto.
        """
        # Map ServiceNow states to Keep IncidentStatus
        # ServiceNow states: 1: New, 2: In Progress, 3: On Hold, 6: Resolved, 7: Closed, 8: Canceled
        sn_state = str(incident_data.get("state"))
        if sn_state in ["1", "2", "3"]:
            status = IncidentStatus.FIRING
        elif sn_state in ["6", "7"]:
            status = IncidentStatus.RESOLVED
        else:
            # Handle state 8 (Canceled) and others as resolved to avoid zombie alerts
            status = IncidentStatus.RESOLVED

        # Map ServiceNow urgency/priority to Keep IncidentSeverity (simplified)
        # Priority: 1: Critical, 2: High, 3: Moderate, 4: Low, 5: Planning
        sn_priority = str(incident_data.get("priority"))
        from keep.api.models.db.incident import IncidentSeverity

        if sn_priority == "1":
            severity = IncidentSeverity.CRITICAL
        elif sn_priority == "2":
            severity = IncidentSeverity.HIGH
        elif sn_priority == "3":
            severity = IncidentSeverity.WARNING
        else:
            severity = IncidentSeverity.INFO

        # Create the IncidentDto
        incident_dto = IncidentDto(
            id=incident_data.get("sys_id"),
            user_generated_name=incident_data.get("number"),
            user_summary=incident_data.get("short_description"),
            status=status,
            severity=severity,
            assignee=incident_data.get("assigned_to"),
            creation_time=parse(incident_data.get("sys_created_on"))
            if incident_data.get("sys_created_on")
            else None,
            start_time=parse(incident_data.get("sys_created_on"))
            if incident_data.get("sys_created_on")
            else None,
            last_seen_time=parse(incident_data.get("sys_updated_on"))
            if incident_data.get("sys_updated_on")
            else None,
            alerts_count=0,  # Will be populated by the rules engine
            alert_sources=["servicenow"],
            services=[incident_data.get("cmdb_ci")]
            if incident_data.get("cmdb_ci")
            else [],
            is_predicted=False,
            is_candidate=False,
            fingerprint=incident_data.get("sys_id"),
        )

        if activity_stream:
            incident_dto.enrichments["activity_stream"] = activity_stream

        return incident_dto

    def _get_batch_activity_stream(self, incident_sys_ids: list[str]) -> dict[str, list[dict]]:
        """
        Query the sys_journal_field table in batch to pull work_notes and comments.
        """
        if not incident_sys_ids:
            return {}

        # Batch query using IN operator
        sys_id_query = ",".join(incident_sys_ids)
        query = f"element_idIN{sys_id_query}^elementINcomments,work_notes"
        
        journal_entries = self._query(
            "sys_journal_field", 
            sysparm_query=query, 
            sysparm_limit=1000, 
            sysparm_display_value=False
        )

        activity_map = {}
        for entry in journal_entries:
            incident_id = entry.get("element_id")
            if incident_id not in activity_map:
                activity_map[incident_id] = []
            
            activity_map[incident_id].append(
                {
                    "type": entry.get("element"),
                    "value": entry.get("value"),
                    "created_by": entry.get("sys_created_by"),
                    "created_on": entry.get("sys_created_on"),
                }
            )
        
        # Sort each incident's stream by creation date
        for stream in activity_map.values():
            stream.sort(key=lambda x: x.get("created_on", ""))
            
        return activity_map

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
            "owned_by.name",
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
        auth = None
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        else:
            auth = (
                self.authentication_config.username,
                self.authentication_config.password,
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
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        auth = None
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        else:
            auth = (
                self.authentication_config.username,
                self.authentication_config.password,
            )

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
