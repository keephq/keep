import dataclasses
import traceback

import openshift_client as oc
import pydantic
from openshift_client import Context, OpenShiftPythonException

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class OpenshiftProviderAuthConfig:
    """Openshift authentication configuration."""

    api_server: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "name": "api_server",
            "description": "The openshift api server url",
            "required": True,
            "sensitive": False,
            "validation": "any_http_url"
        },
    )
    token: str = dataclasses.field(
        metadata={
            "name": "token",
            "description": "The openshift token",
            "required": True,
            "sensitive": True,
        },
    )
    insecure: bool = dataclasses.field(
        default=False,
        metadata={
            "name": "insecure",
            "description": "Skip TLS verification",
            "required": False,
            "sensitive": False,
            "type": "switch"
        },
    )


class OpenshiftProvider(BaseProvider):
    """Perform rollout restart actions on Openshift."""

    provider_id: str
    PROVIDER_DISPLAY_NAME = "Openshift"
    PROVIDER_CATEGORY = ["Cloud Infrastructure"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connect_to_openshift",
            description="Check if the provided token can connect to the openshift server",
            mandatory=True,
            alias="Connect to the openshift",
        )
    ]

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.authentication_config = None
        self.validate_config()

    def dispose(self):
        """Dispose the provider."""
        pass

    def validate_config(self):
        """
        Validates required configuration for Openshift provider.
        """

        if self.config.authentication is None:
            self.config.authentication = {}
        self.authentication_config = OpenshiftProviderAuthConfig(
            **self.config.authentication
        )

    def __get_ocp_client(self):
        """Get the Openshift client."""
        oc_context = Context()
        oc_context.api_server = self.authentication_config.api_server
        oc_context.token = self.authentication_config.token
        oc_context.insecure = self.authentication_config.insecure
        return oc_context

    def validate_scopes(self):
        """
        Validates that the provided token has the required scopes to use the provider.
        """
        try:
            client = self.__get_ocp_client()
            with oc.timeout(60 * 30), oc.tracking() as t, client:
                if oc.get_config_context() is None:
                    try:
                        oc.invoke("login")
                    except OpenShiftPythonException:
                        traceback.print_exc()
                        self.logger.error(
                            f"Tracking:\n{t.get_result().as_json(redact_streams=False)}\n\n"
                        )
                        self.logger.error("Error logging into the API server")
                        raise Exception("Error logging into the API server")
            scopes = {
                "connect_to_openshift": True,
            }
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {
                "connect_to_openshift": str(e),
            }
        return scopes

    def _notify(self, kind: str, name: str, project_name: str):
        """Rollout restart the specified kind."""
        client = self.__get_ocp_client()
        client.project_name = project_name
        self.logger.info(
            f"Performing rollout restart for {kind} {name} using openshift provider"
        )
        with oc.timeout(60 * 30), oc.tracking() as t, client:
            if oc.get_config_context() is None:
                self.logger.error(
                    f"Current context not set! Logging into API server: {client.api_server}\n"
                )
                try:
                    oc.invoke("login")
                except OpenShiftPythonException:
                    self.logger.error("error occurred logging into API Server")
                    traceback.print_exc()
                    self.logger.error(
                        f"Tracking:\n{t.get_result().as_json(redact_streams=False)}\n\n"
                    )
                    raise Exception("Error logging into the API server")
            try:
                oc.invoke("rollout", ["restart", kind, name])
            except OpenShiftPythonException:
                self.logger.error(f"Error restarting {kind} {name}")
                raise Exception(f"Error restarting {kind} {name}")

        self.logger.info(f"Restarted {kind} {name}")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    url = os.environ.get("OPENSHIFT_URL")
    token = os.environ.get("OPENSHIFT_TOKEN")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = ProviderConfig(
        authentication={
            "api_server": url,
            "token": token,
        }
    )
    openshift_provider = OpenshiftProvider(context_manager, "openshift-keephq", config)

    restart = openshift_provider.notify("deployment", "nginx")
    print(restart)
