import dataclasses
import json
import pydantic
import requests
from requests.auth import HTTPBasicAuth
from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class ServicenowProviderAuthConfig:
    """ServiceNow authentication configuration."""

    service_now_base_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The base URL of the ServiceNow instance",
            "sensitive": False,
            "hint": "https://dev12345.service-now.com",
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


class ServicenowProvider(BaseProvider):
    """Manage ServiceNow tickets."""

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

    @property
    def service_now_base_url(self):
        if not self.authentication_config.service_now_base_url.startswith("http"):
            return f"https://{self.authentication_config.service_now_base_url}"
        return self.authentication_config.service_now_base_url

    def validate_scopes(self):
        """
        Validates that the user has the required scopes to use the provider.
        """
        try:
            url = f"{self.authentication_config.service_now_base_url}/api/now/table/sys_user_role?sysparm_query=user_name={self.authentication_config.username}"
            response = requests.get(
                url,
                auth=HTTPBasicAuth(
                    self.authentication_config.username,
                    self.authentication_config.password,
                ),
                verify=False,
            )
            if response.status_code == 200:
                roles = response.json()
                roles_names = [role.get("name") for role in roles.get("result")]
                if "itil" in roles_names:
                    scopes = {"itil": True}
                else:
                    scopes = {"itil": "This user does not have the ITIL role"}
            else:
                scopes["itil"] = "Failed to get roles from ServiceNow"
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {"itil": str(e)}
        return scopes

    def validate_config(self):
        self.authentication_config = ServicenowProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(self, table_name: str, payload: dict = {}, **kwargs: dict):
        # Create ticket
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        # otherwise, create the ticket
        if not table_name:
            raise ProviderException("Table name is required")

        if "ticket_id" in kwargs:
            ticket_id = kwargs.pop("ticket_id")
            fingerprint = kwargs.pop("fingerprint")
            return self._notify_update(table_name, ticket_id, fingerprint)

        table_name = table_name.lower()

        url = f"{self.authentication_config.service_now_base_url}/api/now/table/{table_name}"
        response = requests.post(
            url,
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            headers=headers,
            data=json.dumps(payload),
            verify=False,
        )

        if response.status_code == 201:  # HTTP status code for "Created"
            resp = response.json()
            self.logger.info(f"Created ticket: {resp}")
            result = resp.get("result")
            result[
                "link"
            ] = f"{self.authentication_config.service_now_base_url}/now/nav/ui/classic/params/target/{table_name}.do%3Fsys_id%3D{result['sys_id']}"
            return result
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
        response = requests.get(
            url,
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            headers=headers,
            verify=False,
        )
        if response.status_code == 200:
            resp = response.text
            if "Want to find out why instances hibernate?" in resp:
                raise ProviderException(
                    "ServiceNow instance is down, you need to restart the instance."
                )
            else:
                resp = json.loads(resp)
            self.logger.info("Updated ticket", extra={"resp": resp})
            resp = resp.get("result")
            resp["fingerprint"] = fingerprint
            return resp
        else:
            self.logger.info("Failed to update ticket", extra={"resp": response.text})
            resp.raise_for_status()

    def fetch_incidents(self):
        """
        Fetches all incidents from ServiceNow.
        """
        url = f"{self.authentication_config.service_now_base_url}/api/now/table/incident"
        response = requests.get(
            url,
            auth=HTTPBasicAuth(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            verify=False,
        )
        if response.status_code == 200:
            incidents = response.json().get('result', [])
            return self.process_incidents(incidents)
        else:
            self.logger.info(f"Failed to fetch incidents: {response.text}")
            response.raise_for_status()

    def process_incidents(self, incidents):
        """
        Processes the fetched incidents, extracting necessary metadata.
        """
        events = []
        for incident in incidents:
            event = {
                'id': incident.get('sys_id'),
                'title': incident.get('short_description'),
                'description': incident.get('description'),
                'created_at': incident.get('sys_created_on'),
                'updated_at': incident.get('sys_updated_on'),
                'participants': self.get_participants(incident),
                'timeline': self.get_timeline(incident),
                # Add other metadata as needed
            }
            events.append(event)
        return events

    def get_participants(self, incident):
        """
        Extracts participants from an incident.
        """
        # Logic to get participants from incident
        return []

    def get_timeline(self, incident):
        """
        Extracts timeline from an incident.
        """
        # Logic to get timeline from incident
        return []


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

    service_now_base_url = os.environ.get("SERVICENOW_BASE_URL")
    service_now_username = os.environ.get("SERVICENOW_USERNAME")
    service_now_password = os.environ.get("SERVICENOW_PASSWORD")

    # Initialize the provider and provider config
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

    # Fetch and process incidents
    incidents = provider.fetch_incidents()
    print(json.dumps(incidents, indent=2))