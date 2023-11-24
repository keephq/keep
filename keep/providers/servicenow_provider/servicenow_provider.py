"""
ServicenowProvider is a class that implements the BaseProvider interface for Service Now updates.
"""
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

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

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
            )
            if response.status_code == 200:
                roles = response.json()
                roles_names = [role.get("name") for role in roles.get("result")]
                if "itil" in roles_names:
                    scopes = {
                        "itil": True,
                    }
                else:
                    scopes = {
                        "itil": "This user does not have the ITIL role",
                    }
            else:
                scopes["itil"] = "Failed to get roles from ServiceNow"
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
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            headers=headers,
            data=json.dumps(payload),
        )

        if response.status_code == 201:  # HTTP status code for "Created"
            resp = response.json()
            self.logger.info(f"Created ticket: {resp}")
            result = resp.get("result")
            # Add link to ticket
            result[
                "link"
            ] = f"{self.authentication_config.service_now_base_url}/now/nav/ui/classic/params/target/{table_name}.do%3Fsys_id%3D{result['sys_id']}"
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
        response = requests.get(
            url,
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            headers=headers,
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

    # mock alert
    context_manager = provider.context_manager

    alert = AlertDto.parse_obj(
        json.loads(
            '{"id": "4c54ce9a0d458b574d0aaa5fad23f44ce006e45bdf16fa65207cc6131979c000", "name": "Error in lambda", "status": "ALARM", "lastReceived": "2023-09-18 12:26:21.408000+00:00", "environment": "undefined", "isDuplicate": null, "duplicateReason": null, "service": null, "source": ["cloudwatch"], "message": null, "description": "Hey Shahar\\n\\nThis is a test alarm!", "severity": null, "fatigueMeter": 3, "pushed": true, "event_id": "3cbf2024-a1f0-42ac-9754-b9157c00b95e", "url": null, "AWSAccountId": "1234", "AlarmActions": ["arn:aws:sns:us-west-2:1234:Default_CloudWatch_Alarms_Topic"], "AlarmArn": "arn:aws:cloudwatch:us-west-2:1234:alarm:Error in lambda", "Trigger": {"MetricName": "Errors", "Namespace": "AWS/Lambda", "StatisticType": "Statistic", "Statistic": "AVERAGE", "Unit": null, "Dimensions": [{"value": "helloWorld", "name": "FunctionName"}], "Period": 300, "EvaluationPeriods": 1, "DatapointsToAlarm": 1, "ComparisonOperator": "GreaterThanThreshold", "Threshold": 0.0, "TreatMissingData": "missing", "EvaluateLowSampleCountPercentile": ""}, "Region": "US West (Oregon)", "InsufficientDataActions": [], "AlarmConfigurationUpdatedTimestamp": "2023-08-17T14:29:12.272+0000", "NewStateReason": "Setting state to ALARM for testing", "AlarmName": "Error in lambda", "NewStateValue": "ALARM", "OldStateValue": "INSUFFICIENT_DATA", "AlarmDescription": "Hey Shahar\\n\\nThis is a test alarm!", "OKActions": [], "StateChangeTime": "2023-09-18T12:26:21.408+0000", "trigger": "alert"}'
        )
    )
    context_manager.set_event_context(alert)
    r = provider.notify(
        table_name="incident",
        payload={
            "short_description": "My new incident",
            "category": "software",
            "created_by": "keep",
        },
    )
    print(r)
