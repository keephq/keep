"""
Argocd Provider is a class that allows to get Applications and ApplicationSets from ArgoCD and map them to keep services and aplications respectively.
"""

import dataclasses
import uuid
from typing import List
from urllib.parse import urlencode, urljoin

import pydantic
import requests

from keep.api.models.db.topology import TopologyServiceInDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseTopologyProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class ArgocdProviderAuthConfig:
    """
    Argocd authentication configuration.
    """

    argocd_access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Argocd Access Token",
            "hint": "Argocd Access Token ",
            "sensitive": True,
        },
    )
    deployment_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Deployment Url",
            "hint": "Example: https://loaclhost:8080",
            "validation": "any_http_url",
        },
    )


class ArgocdProvider(BaseTopologyProvider):
    """Install Webhooks and receive alerts from Argocd."""

    PROVIDER_CATEGORY = ["Cloud Infrastructure"]

    PROVIDER_DISPLAY_NAME = "ArgoCD"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authorized",
            mandatory=True,
            mandatory_for_webhook=True,
            alias="Authenticated",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._host = None

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Argocd provider.
        """
        self.logger.debug("Validating configuration for Argocd provider")
        self.authentication_config = ArgocdProviderAuthConfig(
            **self.config.authentication
        )

    @property
    def argocd_host(self):
        self.logger.debug("Fetching Argocd host")
        if self._host:
            self.logger.debug("Returning cached Argocd host")
            return self._host

        # Handle host determination logic with logging
        if self.authentication_config.deployment_url.startswith(
            "http://"
        ) or self.authentication_config.deployment_url.startswith("https://"):
            self.logger.info("Using supplied Argocd host with protocol")
            self._host = self.authentication_config.deployment_url
            return self._host

        # Otherwise, attempt to use https
        try:
            self.logger.debug(
                f"Trying HTTPS for {self.authentication_config.deployment_url}"
            )
            requests.get(
                f"https://{self.authentication_config.deployment_url}",
                verify=False,
            )
            self.logger.info("HTTPS protocol confirmed")
            self._host = f"https://{self.authentication_config.deployment_url}"
        except requests.exceptions.SSLError:
            self.logger.warning("SSL error encountered, falling back to HTTP")
            self._host = f"http://{self.authentication_config.deployment_url}"
        except Exception as e:
            self.logger.error(
                "Failed to determine Argocd host", extra={"exception": str(e)}
            )
            self._host = self.authentication_config.deployment_url.rstrip("/")

        return self._host

    @property
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.authentication_config.argocd_access_token}",
        }

    def __get_url(self, paths: List[str] = [], query_params: dict = None, **kwargs):
        """
        Helper method to build the url for Argocd api requests.
        """
        host = self.argocd_host.rstrip("/").rstrip() + "/api/v1/"
        self.logger.info(f"Building URL with host: {host}")
        url = urljoin(
            host,
            "/".join(str(path) for path in paths),
        )

        # add query params
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        self.logger.debug(f"Constructed URL: {url}")
        return url

    def validate_scopes(self) -> dict[str, bool | str]:
        self.logger.info("Validating user scopes for Argocd provider")
        authenticated = True
        try:
            self.__pull_applications()
        except Exception as e:
            self.logger.error(
                "Error while validating scope for ArgoCD", extra={"exception": str(e)}
            )
            authenticated = str(e)
        return {
            "authenticated": authenticated,
        }

    def __pull_applications(self):
        self.logger.info("Pulling applications from Argocd...")
        try:
            response = requests.get(
                url=self.__get_url(paths=["applications"]),
                headers=self._headers,
                verify=False,
                timeout=10,
            )
            if response.status_code != 200:
                raise Exception(response.text)
            self.logger.info("Successfully pulled all ArgoCD applications")
            return response.json()["items"]

        except Exception as e:
            self.logger.error(
                "Error while getting applications from ArgoCD",
                extra={"exception": str(e)},
            )
            raise e

    def __get_relation(self, name: str, namespace: str):
        try:
            response = requests.get(
                url=self.__get_url(
                    paths=["applications", name, "resource-tree"],
                    query_params={"appNamespace": namespace},
                ),
                headers=self._headers,
                verify=False,
                timeout=10,
            )
            if response.status_code != 200:
                raise Exception(response.text)
            return response.json()["nodes"]
        except Exception as e:
            self.logger.error(
                "Error while getting resource-tree from ArgoCD",
                extra={"exception": str(e)},
            )

    def pull_topology(self):
        applications = self.__pull_applications()
        service_topology = {}
        for application in applications:
            namespace = application["metadata"]["namespace"]
            name = application["metadata"]["name"]
            nodes = self.__get_relation(name, namespace)
            if nodes is None:
                nodes = []
            metadata = application["metadata"]
            applicationSets = metadata.get("ownerReferences", None)
            spec = application["spec"]
            service_topology[metadata["uid"]] = TopologyServiceInDto(
                source_provider_id=self.provider_id,
                service=metadata["uid"],
                display_name=metadata["name"],
                repository=self.__get_repository_urls(spec),
            )
            applications = {}
            if applicationSets:
                for application_set in applicationSets:
                    if application_set["kind"] == "ApplicationSet":
                        application_name: str = (
                            application_set["name"] + "::" + application_set["uid"]
                        )
                        applications[uuid.UUID(application_set["uid"])] = (
                            application_name
                        )

                if len(applications) > 0:
                    service_topology[metadata["uid"]].application_relations = (
                        applications
                    )

            for node in nodes:
                if node["kind"] == "Application":
                    service_topology[metadata["uid"]].dependencies[
                        node["uid"]
                    ] = "unknown"

        return list(service_topology.values()), {}

    def __get_repository_urls(self, spec: dict) -> str:
        """
        Extract repository URLs from application spec, handling both single and multiple sources.
        Returns a comma-separated string of repository URLs.
        """
        repos = []
        if "sources" in spec:
            # Handle multiple sources
            repos.extend(source.get("repoURL") for source in spec["sources"] if source.get("repoURL"))
        elif "source" in spec and spec["source"].get("repoURL"):
            # Handle single source
            repos.append(spec["source"]["repoURL"])
        
        return ", ".join(repos) if repos else None
