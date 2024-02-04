import dataclasses
import datetime
import json

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class LinearbProviderAuthConfig:
    """LinearB authentication configuration."""

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Linear API Token",
            "sensitive": True,
        }
    )


class LinearbProvider(BaseProvider):
    """LinearB provider."""

    LINEARB_API = "https://public-api.linearb.io"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="any", description="A way to validate the provider", mandatory=True
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_scopes(self) -> dict[str, bool | str]:
        headers = {
            "x-api-key": self.authentication_config.api_token,
        }
        result = requests.get(f"{self.LINEARB_API}/api/v1/health", headers=headers)
        if not result.ok:
            return {"any": "Failed to validate the API token"}
        return {"any": True}

    def validate_config(self):
        self.authentication_config = LinearbProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything.
        """
        pass

    def _notify(
        self,
        provider_id: str,
        http_url: str = "",
        title: str = "",
        teams="[]",
        respository_urls="[]",
        services="[]",
        started_at="",
        ended_at="",
        git_ref="",
        should_delete="",
        **kwargs: dict,
    ):
        """
        Notify linear by creating/updating an incident.
        """
        try:
            self.logger.info("Notifying LinearB...")

            headers = {
                "x-api-key": self.authentication_config.api_token,
            }

            # If should_delete is true (any string that is not false), delete the incident and return.
            if should_delete and should_delete != "false":
                result = requests.delete(
                    f"{self.LINEARB_API}/api/v1/incidents/{provider_id}",
                    headers=headers,
                )
                if result.ok:
                    self.logger.info("Deleted incident successfully")
                else:
                    self.logger.warning(
                        "Failed to delete incident", extra={**result.json()}
                    )
                return result.json()

            # Try to get the incident
            incident_response = requests.get(
                f"{self.LINEARB_API}/api/v1/incidents/{provider_id}", headers=headers
            )
            if incident_response.ok:
                incident = incident_response.json()

                payload = {**incident}

                if respository_urls and isinstance(respository_urls, str):
                    respository_urls = json.loads(respository_urls)
                    payload["respository_urls"] = respository_urls

                if services and isinstance(services, str):
                    services = json.loads(services)
                    payload["services"] = services

                if started_at:
                    payload["started_at"] = started_at
                if ended_at:
                    payload["ended_at"] = ended_at
                if git_ref:
                    payload["git_ref"] = git_ref
                result = requests.put(
                    f"{self.LINEARB_API}/api/v1/incidents/{provider_id}",
                    json=payload,
                    headers=headers,
                )
            else:
                if not http_url or not title:
                    raise ProviderException(
                        "http_url and title are required for creating an incident"
                    )

                if teams and isinstance(teams, str):
                    teams = json.loads(teams)

                if not teams:
                    raise ProviderException(
                        "At least 1 team is required for creating an incident"
                    )

                issued_at = datetime.datetime.now().isoformat()

                payload = {
                    "provider_id": provider_id,
                    "http_url": http_url,
                    "title": title,
                    "issued_at": issued_at,
                    "teams": teams,
                }

                result = requests.post(
                    f"{self.LINEARB_API}/api/v1/incidents",
                    json=payload,
                    headers=headers,
                )

            if result.ok:
                self.logger.info("Notified LinearB successfully")
            else:
                self.logger.warning("Failed to notify linearB", extra={**result.json()})

            return result.json()
        except Exception as e:
            raise ProviderException(f"Failed to notify linear: {e}")


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

    linearb_api_token = os.environ.get("LINEARB_API_TOKEN")

    # Initialize the provider and provider config
    config = ProviderConfig(
        description="Linear Input Provider",
        authentication={
            "api_token": linearb_api_token,
        },
    )
    provider = LinearbProvider(context_manager, provider_id="linear", config=config)
    provider.notify(
        provider_id="linear",
        http_url="https://www.google.com",
        title="Test",
    )
