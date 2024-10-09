import dataclasses
import datetime
import json

import pydantic
from splunklib.client import connect
from splunklib.binding import AuthenticationError, HTTPError
from xml.etree.ElementTree import ParseError

from keep.api.models.alert import AlertDto, AlertSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class SplunkProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Splunk API Key",
            "sensitive": True,
        }
    )

    host: str = dataclasses.field(
        metadata={
            "description": "Splunk Host (default is localhost)",
        },
        default="localhost",
    )
    port: int = dataclasses.field(
        metadata={
            "description": "Splunk Port (default is 8089)",
        },
        default=8089,
    )


class SplunkProvider(BaseProvider):
    """Pull alerts and query incidents from Splunk."""

    PROVIDER_DISPLAY_NAME = "Splunk"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="list_all_objects",
            description="The user can get all the alerts",
            mandatory=True,
            alias="List all Alerts",
        ),
        ProviderScope(
            name="edit_own_objects",
            description="The user can edit and add webhook to saved_searches",
            mandatory=True,
            alias="Needed to connect to webhook",
        ),
    ]
    FINGERPRINT_FIELDS = ["exception", "logger", "service"]

    SEVERITIES_MAP = {
        "LOW": AlertSeverity.LOW,
        "INFO": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "ERROR": AlertSeverity.HIGH,
        "CRITICAL": AlertSeverity.CRITICAL,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def __debug_fetch_users_response(self):
        try:
            from splunklib.client import PATH_USERS
            import requests

            response = requests.get(
                f"https://{self.authentication_config.host}:{self.authentication_config.port}/services/{PATH_USERS}",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}"
                },
                verify=False,
            )
            return response
        except Exception as e:
            self.logger.exception("Error getting debug users", extra={"error": str(e)})
            return None

    def validate_scopes(self) -> dict[str, bool | str]:
        self.logger.debug("Validating scopes for Splunk provider")

        validated_scopes = {}

        try:
            self.logger.debug(
                "Connecting to Splunk",
                extra={"auth_config": self.authentication_config},
            )
            service = connect(
                token=self.authentication_config.api_key,
                host=self.authentication_config.host,
                port=self.authentication_config.port,
            )
            self.logger.debug("Connected to Splunk", extra={"service": service})

            if len(service.users) > 1:
                self.logger.warning(
                    "Splunk provider has more than one user",
                    extra={
                        "users_count": len(service.users),
                        "users": [user.content for user in service.users],
                    },
                )

            all_permissions = set()
            for user in service.users:
                user_roles = user.content["roles"]
                for role_name in user_roles:
                    perms = self.__get_role_capabilities(
                        role_name=role_name, service=service
                    )
                    all_permissions.update(perms)

            for scope in self.PROVIDER_SCOPES:
                if scope.name in all_permissions:
                    validated_scopes[scope.name] = True
                else:
                    validated_scopes[scope.name] = "NOT_FOUND"
        except AuthenticationError:
            self.logger.exception("Error authenticating to Splunk")
            validated_scopes = dict(
                [[scope.name, "AUTHENTICATION_ERROR"] for scope in self.PROVIDER_SCOPES]
            )
        except HTTPError as e:
            self.logger.exception(
                "Error connecting to Splunk",
            )
            self.logger.debug(
                "Splunk error response",
                extra={"body": e.body, "status": e.status, "headers": e.headers},
            )
            validated_scopes = dict(
                [
                    [scope.name, "HTTP_ERROR ({status})".format(status=e.status)]
                    for scope in self.PROVIDER_SCOPES
                ]
            )
        except ConnectionRefusedError:
            self.logger.exception(
                "Error connecting to Splunk",
            )
            validated_scopes = dict(
                [[scope.name, "CONNECTION_REFUSED"] for scope in self.PROVIDER_SCOPES]
            )
        except ParseError as e:
            self.logger.exception(
                "Error parsing XML",
                extra={
                    "error": str(e),
                },
            )
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                response = self.__debug_fetch_users_response()
                self.logger.exception(
                    "Raw users response",
                    extra={
                        "url": response.url,
                        "status": response.status_code,
                        "text": response.text,
                    },
                )
            validated_scopes = dict(
                [[scope.name, "PARSE_ERROR"] for scope in self.PROVIDER_SCOPES]
            )
        except Exception as e:
            self.logger.exception("Error validating scopes", extra={"error": str(e)})
            validated_scopes = dict(
                [[scope.name, "UNKNOWN_ERROR"] for scope in self.PROVIDER_SCOPES]
            )

        return validated_scopes

    def validate_config(self):
        self.authentication_config = SplunkProviderAuthConfig(
            **self.config.authentication
        )

    def __get_role_capabilities(self, role_name, service):
        role = service.roles[role_name]
        return role.content["capabilities"] + role.content["imported_capabilities"]

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        self.logger.info("Setting up Splunk webhook on all Alerts")
        creation_updation_kwargs = {
            "actions": "webhook",
            "action.webhook": "1",
            "action.webhook.param.url": keep_api_url,
        }
        service = connect(
            token=self.authentication_config.api_key,
            host=self.authentication_config.host,
            port=self.authentication_config.port,
        )
        for saved_search in service.saved_searches:
            existing_webhook_url = saved_search["_state"]["content"].get(
                "action.webhook.param.url", None
            )
            if existing_webhook_url is None or existing_webhook_url != keep_api_url:
                saved_search.update(**creation_updation_kwargs).refresh()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        result: dict = event.get("result", event.get("_result", {}))

        try:
            raw: str = result.get("_raw", "{}")
            raw_dict: dict = json.loads(raw)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(
                "Error parsing _raw attribute from event",
                extra={"err": e, "_raw": event.get("_raw")},
            )
            raw_dict = {}

        # export k8s specifics
        kubernetes = {}
        for key in result:
            if key.startswith("kubernetes"):
                kubernetes[key.replace("kubernetes.", "")] = result[key]

        message = result.get("message")
        name = message or raw_dict.get("message", event["search_name"])
        service = result.get("service")
        environment = result.get("environment", result.get("env", "undefined"))
        exception = event.get(
            "exception",
            result.get(
                "exception",
                result.get("exception_class"),
            ),
        ) or raw_dict.get("exception_class", "")
        result["exception_class"] = exception

        # override stacktrace with _raw stacktrace if it doesnt exist in result
        stacktrace = result.get("stacktrace", raw_dict.get("stacktrace", ""))
        result["stacktrace"] = stacktrace

        severity = result.get("log_level", raw_dict.get("log_level", "INFO"))
        logger = event.get("logger", result.get("logger"))
        alert = AlertDto(
            id=event["sid"],
            name=name,
            source=["splunk"],
            url=event["results_link"],
            lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            severity=SplunkProvider.SEVERITIES_MAP.get(severity),
            status="firing",
            message=message,
            service=service,
            environment=environment,
            exception=exception,
            logger=logger,
            kubernetes=kubernetes,
            **event,
        )
        alert.fingerprint = SplunkProvider.get_alert_fingerprint(
            alert,
            (
                SplunkProvider.FINGERPRINT_FIELDS
                if (exception is not None or logger is not None)
                else ["name"]
            ),
        )
        return alert


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

    api_key = os.environ.get("SPLUNK_API_KEY")

    provider_config = {
        "authentication": {"api_key": api_key},
    }
    provider = ProvidersFactory.get_provider(
        context_manager=context_manager,
        provider_id="keep-pd",
        provider_type="splunk",
        provider_config=provider_config,
    )
    results = provider.setup_webhook(
        "keep",
        "https://eb8a-77-137-44-66.ngrok-free.app/alerts/event/splunk?provider_id=keep-pd",
        "just-a-test",
        True,
    )
