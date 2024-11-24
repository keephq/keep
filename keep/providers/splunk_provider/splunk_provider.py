import dataclasses
import datetime
import json
import logging
from xml.etree.ElementTree import ParseError

import pydantic
from splunklib.binding import AuthenticationError, HTTPError
from splunklib.client import connect

from keep.api.models.alert import AlertDto, AlertSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory
from keep.validation.fields import NoSchemeUrl, UrlPort


@pydantic.dataclasses.dataclass
class SplunkProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Splunk API Key",
            "sensitive": True,
        }
    )

    host: NoSchemeUrl = dataclasses.field(
        metadata={
            "description": "Splunk Host (default is localhost)",
            "validation": "no_scheme_url"
        },
        default="localhost",
    )
    port: UrlPort = dataclasses.field(
        metadata={
            "description": "Splunk Port (default is 8089)",
            "validation": "port"
        },
        default=8089,
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Enable SSL verification",
            "hint": "An `https` protocol will be used if enabled.",
            "type": "switch"
        },
        default=True,
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
    PROVIDER_CATEGORY = ["Monitoring"]
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
            import requests
            from splunklib.client import PATH_USERS

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
        self.logger.info("Validating scopes for Splunk provider")

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
                scheme='https' if self.authentication_config.verify else 'http',
                verify=self.authentication_config.verify
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
                if response is not None:
                    self.logger.debug(
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
        self.logger.info("Setting up Splunk webhook for all saved searches")
        webhook_url = f"{keep_api_url}&api_key={api_key}"
        webhook_kwargs = {
            "actions": "webhook",
            "action.webhook": "1",
            "action.webhook.param.url": webhook_url,
        }
        service = connect(
            token=self.authentication_config.api_key,
            host=self.authentication_config.host,
            port=self.authentication_config.port,
            scheme='https' if self.authentication_config.verify else 'http',
            verify=self.authentication_config.verify
        )
        for saved_search in service.saved_searches:
            existing_webhook_url = saved_search["_state"]["content"].get(
                "action.webhook.param.url", None
            )
            if existing_webhook_url and existing_webhook_url == webhook_url:
                self.logger.info(
                    f"Webhook already set for saved search {saved_search.name}",
                    extra={
                        "webhook_url": webhook_url,
                    },
                )
                continue
            self.logger.info(
                f"Updating saved search with webhook {saved_search.name}",
                extra={
                    "webhook_url": webhook_url,
                },
            )
            saved_search.update(**webhook_kwargs).refresh()

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
