import dataclasses
import datetime
import json

import pydantic
import requests
from asteval import Interpreter

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
            "description": "LinearB API Token",
            "sensitive": True,
        }
    )


class LinearbProvider(BaseProvider):
    """LinearB provider."""

    PROVIDER_DISPLAY_NAME = "LinearB"
    LINEARB_API = "https://public-api.linearb.io"
    PROVIDER_CATEGORY = ["Developer Tools"]
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
        result = requests.get(
            f"{self.LINEARB_API}/api/v1/health", headers=headers, timeout=10
        )
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
        incident_id: str,
        http_url: str = "",
        title: str = "",
        teams="",
        repository_urls="",
        services="",
        started_at="",
        ended_at="",
        git_ref="",
        should_delete="",
        issued_at="",
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
                    f"{self.LINEARB_API}/api/v1/incidents/{incident_id}",
                    headers=headers,
                    timeout=10,
                )
                if result.ok:
                    self.logger.info("Deleted incident successfully")
                else:
                    r = result.json()
                    # don't override message
                    if "message" in r:
                        r["message_from_linearb"] = r.pop("message")
                    self.logger.warning("Failed to delete incident", extra={**r})
                    raise Exception(f"Failed to notify linearB {result.text}")
                return result.text

            # Try to get the incident
            incident_response = requests.get(
                f"{self.LINEARB_API}/api/v1/incidents/{incident_id}",
                headers=headers,
                timeout=10,
            )
            if incident_response.ok:
                incident = incident_response.json()
                self.logger.info("Found LinearB Incident", extra={"incident": incident})

                payload = {**incident}

                if "teams" in payload:
                    self.logger.info(
                        "Handling teams", extra={"teams": payload["teams"]}
                    )
                    team_names = [team["name"] for team in payload["teams"]]
                    if teams and isinstance(teams, str):
                        try:
                            teams = json.loads(teams)
                            for team in teams:
                                if team not in team_names:
                                    team_names.append(team)
                        except json.JSONDecodeError:
                            self.logger.warning("Failed to parse teams to JSON")
                    payload["teams"] = team_names
                    self.logger.info("Updated teams", extra={"teams": payload["teams"]})

                if repository_urls:
                    self.logger.info(
                        "Handling repository_urls",
                        extra={"repository_urls": repository_urls},
                    )
                    if isinstance(repository_urls, str):
                        try:
                            repository_urls = json.loads(repository_urls)
                        except json.JSONDecodeError:
                            self.logger.warning(
                                "Failed to parse repository_urls to JSON"
                            )
                    payload["repository_urls"] = repository_urls
                    self.logger.info(
                        "Updated repository_urls",
                        extra={"repository_urls": payload["repository_urls"]},
                    )
                else:
                    # Might received repository_urls as a key in the payload
                    payload.pop("repository_urls", None)

                if services:
                    self.logger.info(
                        "Got services from workflow", extra={"services": services}
                    )
                    if isinstance(services, str):
                        aeval = Interpreter()
                        services: list = aeval(services)
                    if len(services) > 0 and isinstance(services[0], dict):
                        services = [service["name"] for service in services]
                    payload["services"] = services
                    self.logger.info(
                        "Updated services", extra={"services": payload["services"]}
                    )
                elif "services" in payload:
                    service_names = [service["name"] for service in payload["services"]]
                    payload["services"] = service_names

                if started_at:
                    payload["started_at"] = started_at
                if ended_at:
                    payload["ended_at"] = ended_at
                if git_ref:
                    payload["git_ref"] = git_ref
                result = requests.patch(
                    f"{self.LINEARB_API}/api/v1/incidents/{incident_id}",
                    json=payload,
                    headers=headers,
                    timeout=10,
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

                issued_at = issued_at or datetime.datetime.now().isoformat()

                payload = {
                    "provider_id": incident_id,
                    "http_url": http_url,
                    "title": title,
                    "issued_at": issued_at,
                    "teams": teams,
                }

                if repository_urls:
                    if isinstance(repository_urls, str):
                        repository_urls = json.loads(repository_urls)
                    payload["repository_urls"] = repository_urls

                if services:
                    if isinstance(services, str):
                        services = json.loads(services)
                    payload["services"] = services

                result = requests.post(
                    f"{self.LINEARB_API}/api/v1/incidents",
                    json=payload,
                    headers=headers,
                    timeout=10,
                )

            if result.ok:
                self.logger.info(
                    "Notified LinearB successfully", extra={"payload": payload}
                )
            else:
                # don't override message
                r = result.json()
                if "message" in r:
                    r["message_from_linearb"] = r.pop("message")
                self.logger.warning(
                    "Failed to notify linearB",
                    extra={**r, "payload": payload},
                )
                raise Exception(f"Failed to notify linearB {result.text}")

            return result.text
        except Exception as e:
            self.logger.exception("Failed to notify LinearB")
            raise ProviderException(f"Failed to notify LinearB: {e}")


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
        incident_id="linear",
        http_url="https://www.google.com",
        title="Test",
        teams='["All Contributors"]',
        repository_urls='["https://www.keephq.dev"]',
        started_at=datetime.datetime.now().isoformat(),
        should_delete="true",
    )
