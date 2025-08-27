"""
Zabbix Provider is a class that allows to ingest/digest data from Zabbix.
"""

import dataclasses
import datetime
import json
import logging
import os
import random
from typing import Union

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.base.provider_exceptions import ProviderMethodException
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class ZabbixProviderAuthConfig:
    """
    Zabbix authentication configuration.
    """

    zabbix_frontend_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zabbix Frontend URL",
            "hint": "https://zabbix.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    auth_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zabbix Auth Token",
            "hint": "Users -> Api tokens",
            "sensitive": True,
        }
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class ZabbixProvider(BaseProvider):
    """
    Pull/Push alerts from Zabbix into Keep.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    KEEP_ZABBIX_WEBHOOK_INTEGRATION_NAME = "keep"  # keep-zabbix
    KEEP_ZABBIX_WEBHOOK_SCRIPT_FILENAME = (
        "zabbix_provider_script.js"  # zabbix mediatype script file
    )
    PROVIDER_SCOPES = [
        ProviderScope(
            name="action.create",
            description="This method allows to create new actions.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/action/create",
        ),
        ProviderScope(
            name="action.get",
            description="This method allows to retrieve actions.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/action/get",
        ),
        ProviderScope(
            name="event.acknowledge",
            description="This method allows to update events.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/event/acknowledge",
        ),
        ProviderScope(
            name="mediatype.create",
            description="This method allows to create new media types.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/mediatype/create",
        ),
        ProviderScope(
            name="mediatype.get",
            description="This method allows to retrieve media types.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/mediatype/get",
        ),
        ProviderScope(
            name="mediatype.update",
            description="This method allows to update media types.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/mediatype/update",
        ),
        ProviderScope(
            name="problem.get",
            description="The method allows to retrieve problems.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/problem/get",
        ),
        ProviderScope(
            name="script.create",
            description="This method allows to create new scripts.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/script/create",
        ),
        ProviderScope(
            name="script.get",
            description="The method allows to retrieve scripts.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/script/get",
        ),
        ProviderScope(
            name="script.update",
            description="This method allows to update scripts.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/script/update",
        ),
        ProviderScope(
            name="user.get",
            description="This method allows to retrieve users.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/user/get",
        ),
        ProviderScope(
            name="user.update",
            description="This method allows to update users.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://www.zabbix.com/documentation/current/en/manual/api/reference/user/update",
        ),
    ]
    PROVIDER_METHODS = [
        ProviderMethod(
            name="Close Problem",
            func_name="close_problem",
            scopes=["event.acknowledge"],
            type="action",
        ),
        ProviderMethod(
            name="Change Severity",
            func_name="change_severity",
            scopes=["event.acknowledge"],
            type="action",
        ),
        ProviderMethod(
            name="Suppress Problem",
            func_name="surrpress_problem",
            scopes=["event.acknowledge"],
            type="action",
        ),
        ProviderMethod(
            name="Unsuppress Problem",
            func_name="unsurrpress_problem",
            scopes=["event.acknowledge"],
            type="action",
        ),
        ProviderMethod(
            name="Acknowledge Problem",
            func_name="acknowledge_problem",
            scopes=["event.acknowledge"],
            type="action",
        ),
        ProviderMethod(
            name="Unacknowledge Problem",
            func_name="unacknowledge_problem",
            scopes=["event.acknowledge"],
            type="action",
        ),
        ProviderMethod(
            name="Add Message to Problem",
            func_name="add_message_to_problem",
            scopes=["event.acknowledge"],
            type="action",
        ),
        ProviderMethod(
            name="Get Problem Messages",
            func_name="get_problem_messages",
            scopes=["problem.get"],
            type="view",
        ),
    ]

    SEVERITIES_MAP = {
        0: AlertSeverity.LOW,
        1: AlertSeverity.INFO,
        2: AlertSeverity.WARNING,
        3: AlertSeverity.WARNING,
        4: AlertSeverity.HIGH,
        5: AlertSeverity.CRITICAL,
    }

    SEVERITY_NAME_TO_ID_MAP = {
        "not_classified": 0,
        "not classified": 0,
        "information": 1,
        "warning": 2,
        "average": 3,
        "high": 4,
        "disaster": 5,
    }

    STATUS_MAP = {
        "problem": AlertStatus.FIRING,
        "ok": AlertStatus.RESOLVED,
        "resolved": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "suppressed": AlertStatus.SUPPRESSED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def close_problem(self, id: str):
        """
        Close a problem.

        https://www.zabbix.com/documentation/current/en/manual/api/reference/event/acknowledge

        Args:
            id (str): The problem id.
        """
        self.logger.info(f"Closing problem {id}")
        self.__send_request("event.acknowledge", {"eventids": id, "action": 1})
        self.logger.info(f"Closed problem {id}")

    def unsurrpress_problem(self, id: str):
        """
        Unsuppress a problem.
        Args:
            id (str): The problem id.
        """
        self.logger.info(f"Unsuppressing problem {id}")
        self.__send_request("event.acknowledge", {"eventids": id, "action": 64})
        self.logger.info(f"Unsuppressed problem {id}")

    def surrpress_problem(
        self,
        id: str,
        suppress_until: datetime.datetime = datetime.datetime.now()
        + datetime.timedelta(days=1),
    ):
        """
        Suppress a problem.
        Args:
            id (str): The problem id.
            suppress_until (datetime.datetime): The datetime to suppress the problem until.
        """
        self.logger.info(f"Suppressing problem {id} until {suppress_until}")
        if isinstance(suppress_until, str):
            suppress_until = datetime.datetime.fromisoformat(suppress_until)
        self.__send_request(
            "event.acknowledge",
            {
                "eventids": id,
                "action": 32,
                "suppress_until": int(suppress_until.timestamp()),
            },
        )
        self.logger.info(f"Suppressed problem {id} until {suppress_until}")

    def acknowledge_problem(self, id: str):
        """
        Acknowledge a problem.
        Args:
            id (str): The problem id.
        """
        self.logger.info(f"Acknowledging problem {id}")
        self.__send_request("event.acknowledge", {"eventids": id, "action": 2})
        self.logger.info(f"Acknowledged problem {id}")

    def unacknowledge_problem(self, id: str):
        """
        Unacknowledge a problem.
        Args:
            id (str): The problem id.
        """
        self.logger.info(f"Unacknowledging problem {id}")
        self.__send_request("event.acknowledge", {"eventids": id, "action": 16})
        self.logger.info(f"Unacknowledged problem {id}")

    def add_message_to_problem(self, id: str, message_text: str):
        """
        Add a message to a problem.
        Args:
            id (str): The problem id.
            message_text (str): The message text.
        """
        self.logger.info(
            f"Adding message to problem {id}", extra={"zabbix_message": message_text}
        )
        self.__send_request(
            "event.acknowledge",
            {"eventids": id, "message": message_text, "action": 4},
        )
        self.logger.info(
            f"Added message to problem {id}", extra={"zabbix_message": message_text}
        )

    def get_problem_messages(self, id: str):
        """
        Get the messages from a problem.
        Args:
            id (str): The problem id.
        """
        problem = self.__send_request(
            "problem.get", {"eventids": id, "selectAcknowledges": "extend"}
        )
        messages = []

        problems = problem.get("result", [])
        if not problems:
            return messages

        for acknowledge in problem.get("result", [])[0].get("acknowledges", []):
            if acknowledge.get("action") == "4":
                time = datetime.datetime.fromtimestamp(int(acknowledge.get("clock")))
                messages.append(f'{time}: {acknowledge.get("message")}')
        return messages

    def change_severity(
        self,
        id: str,
        new_severity: str,
    ):
        """
        Change the severity of a problem.
        Args:
            id (str): The problem id.
            new_severity (str): The new severity. Can be an integer string (0-5) or severity name:
                - "0" or "Not classified"
                - "1" or "Information"
                - "2" or "Warning"
                - "3" or "Average"
                - "4" or "High"
                - "5" or "Disaster"
        """
        # Validate and convert input
        severity = 0

        # Handle numeric string input
        if new_severity.isdigit():
            severity_int = int(new_severity)
            if 0 <= severity_int <= 5:
                severity = severity_int
            else:
                raise ValueError(f"Invalid severity number: {new_severity}. Must be between 0-5.")
        else:
            # Handle string input
            severity_lower = new_severity.lower().strip()
            if severity_lower in ZabbixProvider.SEVERITY_NAME_TO_ID_MAP:
                severity = ZabbixProvider.SEVERITY_NAME_TO_ID_MAP[severity_lower]
            else:
                valid_severities = list(ZabbixProvider.SEVERITY_NAME_TO_ID_MAP.keys()) + ["0", "1", "2", "3", "4", "5"]
                raise ValueError(f"Invalid severity: {new_severity}. Valid values are: {valid_severities}")

        self.__send_request(
            "event.acknowledge", {"eventids": id, "severity": severity, "action": 8}
        )

    def validate_config(self):
        """
        Validates required configuration for Zabbix provider.
        """
        self.authentication_config = ZabbixProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {}
        for scope in self.PROVIDER_SCOPES:
            try:
                self.__send_request(scope.name)
            except Exception as e:
                # This is a hack to check if the error is related to permissions
                error = getattr(e, "message", e.args[0])
                # If we got here, it means it's an exception from Zabbix
                if "permission" in str(error) or "not authorized" in str(error).lower():
                    validated_scopes[scope.name] = "Permission denied"
                    continue
                else:
                    if error and any(phrase in error.lower() for phrase in [
                        "invalid parameter",
                        "incorrect arguments"
                    ]):
                        # This is OK, it means the request is broken but we have access to the endpoint.
                        pass
                    else:
                        validated_scopes[scope.name] = error
                        continue
            validated_scopes[scope.name] = True
        return validated_scopes

    def __send_request(
        self, method: str, params: dict = None, include_auth: bool = True
    ):
        """
        Send a request to Zabbix API.

        Args:
            method (str): The method to call.
            params (dict): The parameters to send.

        Returns:
            dict: The response from Zabbix API.
        """
        url = f"{self.authentication_config.zabbix_frontend_url}/api_jsonrpc.php"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.authentication_config.auth_token}",
        }
        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": random.randint(1000, 2000),
        }

        # in zabbix >=7.2 it makes requests fail.
        if include_auth:
            # zabbix < 6.4 compatibility
            data["auth"] = f"{self.authentication_config.auth_token}"

        response = requests.post(
            url, json=data, headers=headers, verify=self.authentication_config.verify
        )

        try:
            response.raise_for_status()
        except requests.HTTPError:
            self.logger.exception(
                "Error while sending request to Zabbix API",
                extra={
                    "response": response.text,
                    "tenant_id": self.context_manager.tenant_id,
                },
            )
            raise
        response_json = response.json()
        if "error" in response_json:
            self.logger.error(
                "Error while querying zabbix",
                extra={
                    "tenant_id": self.context_manager.tenant_id,
                    "response_json": response_json,
                },
            )
            error_data = response_json.get("error", {}).get("data")

            # Try to send the request without auth, probably zabbix >=7.2
            if 'unexpected parameter "auth".' in error_data and include_auth:
                return self.__send_request(method, params, include_auth=False)

            raise ProviderMethodException(error_data)
        return response_json

    @staticmethod
    def _convert_severity(severity: Union[int, str]) -> AlertSeverity:
        """
        Convert Zabbix severity to Keep AlertSeverity.

        Args:
            severity (Union[int, str]): The severity value. Can be:
                - Integer (0-5): 0=Not classified, 1=Information, 2=Warning, 3=Average, 4=High, 5=Disaster
                - String: "not classified", "information", "warning", "average", "high", "disaster"

        Returns:
            AlertSeverity: The corresponding Keep AlertSeverity
        """
        if isinstance(severity, int):
            return ZabbixProvider.SEVERITIES_MAP.get(severity, AlertSeverity.INFO)

        # Handle string input
        if isinstance(severity, str):
            severity_stripped = severity.strip()

            # First, check if it's a numeric string
            if severity_stripped.isdigit():
                severity_int = int(severity_stripped)
                if 0 <= severity_int <= 5:
                    return ZabbixProvider.SEVERITIES_MAP.get(severity_int, AlertSeverity.INFO)

            # If not a valid integer string, handle as text
            severity_lower = severity_stripped.lower()
            severity_int = ZabbixProvider.SEVERITY_NAME_TO_ID_MAP.get(severity_lower, 1)  # Default to Information
            return ZabbixProvider.SEVERITIES_MAP.get(severity_int, AlertSeverity.INFO)

        # Fallback for any other type
        return AlertSeverity.INFO

    def _get_alerts(self) -> list[AlertDto]:
        # https://www.zabbix.com/documentation/current/en/manual/api/reference/problem/get
        time_from = int(
            (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()
        )
        problems = self.__send_request(
            "problem.get",
            {
                "recent": False,
                "selectSuppressionData": "extend",
                "time_from": time_from,
            },
        )
        formatted_alerts = []
        for problem in problems.get("result", []):
            name = problem.pop("name")
            problem.pop("source")

            environment = problem.pop("environment", None)
            if environment is None:
                environment = "unknown"

            severity = self._convert_severity(problem.pop("severity", 1))
            status = ZabbixProvider.STATUS_MAP.get(
                problem.pop("status", "").lower(), AlertStatus.FIRING
            )

            formatted_alerts.append(
                AlertDto(
                    id=problem.pop("eventid"),
                    name=name,
                    status=status,
                    lastReceived=datetime.datetime.fromtimestamp(
                        int(problem.get("clock"))
                        + 10  # to override pushed problems, 10 is just random, could probably be 1
                    ).isoformat(),
                    source=["zabbix"],
                    message=name,
                    severity=severity,
                    environment=environment,
                    problem=problem,
                )
            )
        return formatted_alerts

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        # Copied from https://git.zabbix.com/projects/ZBX/repos/zabbix/browse/templates/media/ilert/media_ilert.yaml?at=release%2F6.4
        # Based on @SomeAverageDev hints and suggestions ;) Thanks!
        # TODO: this can be done once when loading the provider file
        self.logger.info("Reading webhook JS script file")
        __location__ = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__))
        )

        with open(
            os.path.join(
                __location__, ZabbixProvider.KEEP_ZABBIX_WEBHOOK_SCRIPT_FILENAME
            )
        ) as f:
            script = f.read()

        self.logger.info("Creating or updating webhook")
        script_name = (
            f"{ZabbixProvider.KEEP_ZABBIX_WEBHOOK_INTEGRATION_NAME}-{self.provider_id}"
        )

        self.logger.info("Getting existing scripts")
        existing_scripts = self.__send_request(
            "script.get",
            {"output": ["scriptid", "name"]},
        )

        self.logger.info("Got existing scripts")
        scripts = [
            mt for mt in existing_scripts.get("result", []) if mt["name"] == script_name
        ]

        parameters = [
            {"name": "keepApiKey", "value": api_key},
            {"name": "keepApiUrl", "value": keep_api_url},
            {"name": "id", "value": "{EVENT.ID}"},
            {"name": "triggerId", "value": "{TRIGGER.ID}"},
            {"name": "lastReceived", "value": "{DATE} {TIME}"},
            {"name": "message", "value": "{ALERT.MESSAGE}"},
            {"name": "name", "value": "{EVENT.NAME}"},
            {"name": "service", "value": "{HOST.HOST}"},
            {"name": "severity", "value": "{EVENT.SEVERITY}"},
            {"name": "status", "value": "{EVENT.STATUS}"},
            {"name": "tags", "value": "{EVENT.TAGSJSON}"},
            {"name": "description", "value": "{TRIGGER.DESCRIPTION}"},
            {"name": "time", "value": "{EVENT.TIME}"},
            {"name": "value", "value": "{EVENT.VALUE}"},
            {"name": "host_ip", "value": "{HOST.IP}"},
            {"name": "host_name", "value": "{HOST.NAME}"},
            {"name": "url", "value": "{$ZABBIX.URL}"},
            {"name": "update_action", "value": "{EVENT.UPDATE.ACTION}"},
            {"name": "event_ack", "value": "{EVENT.ACK.STATUS}"},
        ]

        if scripts:
            existing_script = scripts[0]
            self.logger.info("Updating existing script")
            script_id = str(existing_script["scriptid"])
            self.__send_request(
                "script.update",
                {
                    "scriptid": script_id,
                    "command": script,
                    "type": "5",
                    "timeout": "30s",
                    "parameters": parameters,
                    "scope": "1",
                    "description": "Keep Zabbix Webhook",
                },
            )
            self.logger.info("Updated script")
        else:
            self.logger.info("Creating script")
            params = {
                "name": script_name,
                "parameters": parameters,
                "command": script,
                "type": "5",
                "timeout": "30s",
                "scope": "1",
                "description": "Keep Zabbix Webhook",
            }
            response_json = self.__send_request("script.create", params)
            script_id = str(response_json.get("result", {}).get("scriptids", [])[0])
            self.logger.info("Created script")

        action_name = f"keep-{self.provider_id}"
        existing_actions = self.__send_request(
            "action.get",
            {"output": ["name"]},
        )
        action_exists = any(
            [
                action
                for action in existing_actions.get("result", [])
                if action["name"] == action_name
            ]
        )
        if not action_exists:
            self.logger.info("Creating action")
            payload = {
                "eventsource": "0",
                "name": action_name,
                "status": "0",
                "esc_period": "1h",
                "operations": {
                    "0": {
                        "operationtype": "1",
                        "opcommand_hst": {"0": {"hostid": "0"}},
                        "opcommand": {"scriptid": script_id},
                    }
                },
                "recovery_operations": {
                    "0": {
                        "operationtype": "1",
                        "opcommand_hst": {"0": {"hostid": "0"}},
                        "opcommand": {"scriptid": script_id},
                    }
                },
                "update_operations": {
                    "0": {
                        "operationtype": "1",
                        "opcommand_hst": {"0": {"hostid": "0"}},
                        "opcommand": {"scriptid": script_id},
                    }
                },
                "pause_symptoms": "1",
                "pause_suppressed": "1",
                "notify_if_canceled": "1",
            }
            try:
                action_response = self.__send_request(
                    "action.create",
                    payload,
                )
            except Exception:
                payload.pop("pause_symptoms", None)
                action_response = self.__send_request(
                    "action.create",
                    payload,
                )
            self.logger.info(
                "Created action", extra={"action_response": action_response}
            )
        else:
            self.logger.info("Action already exists")

        self.logger.info("Finished installing webhook")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        environment = "unknown"
        tags_raw = event.pop("tags", "[]")
        try:
            tags = {tag.get("tag"): tag.get("value") for tag in json.loads(tags_raw)}
        except json.JSONDecodeError:
            logger.error("Failed to extract Zabbix tags", extra={"tags_raw": tags_raw})
            # We failed to extract tags for some reason.
            tags = {}
        if isinstance(tags, dict):
            environment = tags.pop("environment", "unknown")
            # environment exists in tags but is None
            if environment is None:
                environment = "unknown"
        event_id = event.get("id")
        trigger_id = event.get("triggerId")
        zabbix_url = event.pop("url", None)
        hostname = event.pop("service", None) or event.get("hostName")
        ip_address = event.get("hostIp")

        if zabbix_url == "{$ZABBIX.URL}":
            # This means user did not configure $ZABBIX.URL in Zabbix probably
            zabbix_url = None

        url = None
        if event_id and trigger_id and zabbix_url:
            url = (
                f"{zabbix_url}/tr_events.php?triggerid={trigger_id}&eventid={event_id}"
            )

        severity = ZabbixProvider._convert_severity(event.pop("severity", 1))

        status = event.pop("status", "").lower()
        status = ZabbixProvider.STATUS_MAP.get(status, AlertStatus.FIRING)

        last_received = event.pop(
            "lastReceived", datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        )
        if last_received == "{DATE} {TIME}":
            # This means it's a test message, just override.
            last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        else:
            last_received = datetime.datetime.strptime(
                last_received, "%Y.%m.%d %H:%M:%S"
            ).isoformat()

        update_action = event.get("update_action", "")
        if update_action == "acknowledged":
            status = AlertStatus.ACKNOWLEDGED
        elif "suppressed" in update_action:
            status = AlertStatus.SUPPRESSED

        return AlertDto(
            **event,
            environment=environment,
            pushed=True,
            source=["zabbix"],
            severity=severity,
            status=status,
            url=url,
            lastReceived=last_received,
            tags=tags,
            hostname=hostname,
            service=hostname,
            ip_address=ip_address,
        )


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

    auth_token = os.environ.get("ZABBIX_AUTH_TOKEN")

    provider_config = {
        "authentication": {
            "auth_token": auth_token,
            "zabbix_frontend_url": "http://localhost",
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="zabbix",
        provider_type="zabbix",
        provider_config=provider_config,
    )
    provider.setup_webhook(
        "e1faa321-35df-486b-8fa8-3601ee714011", "http://localhost:8080", "abc"
    )
