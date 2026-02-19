import dataclasses
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import urlparse

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod


@pydantic.dataclasses.dataclass
class PosthogProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "PostHog API key",
            "hint": "https://posthog.com/docs/api/overview",
            "sensitive": True,
        },
    )

    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "PostHog project ID",
            "hint": "Found in your PostHog project settings",
        },
    )


class PosthogProvider(BaseProvider, ProviderHealthMixin):
    """Query data from PostHog analytics."""

    PROVIDER_DISPLAY_NAME = "PostHog"
    PROVIDER_CATEGORY = ["Analytics"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="session_recording:read",
            description="Read PostHog session recordings",
            mandatory=True,
            alias="Read session recordings",
        ),
        ProviderScope(
            name="session_recording_playlist:read",
            description="Read PostHog session recording playlists",
            mandatory=False,
            alias="Read recording playlists",
        ),
        ProviderScope(
            name="project:read",
            description="Read PostHog project data",
            mandatory=True,
            alias="Read project data",
        ),
    ]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="Get Session Recording Domains",
            func_name="get_session_recording_domains",
            scopes=["session_recording:read", "project:read"],
            description="Get a list of domains from session recordings within a time period",
            type="action",
        ),
        ProviderMethod(
            name="Get Session Recordings",
            func_name="get_session_recordings",
            scopes=["session_recording:read", "project:read"],
            description="Get session recordings within a time period",
            type="action",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.base_url = "https://app.posthog.com/api"
        self.headers = {
            "Authorization": f"Bearer {self.authentication_config.api_key}",
            "Content-Type": "application/json",
        }

    def validate_scopes(self):
        scopes = {}
        self.logger.info("Validating scopes")
        try:
            # Test project access
            project_url = (
                f"{self.base_url}/projects/{self.authentication_config.project_id}"
            )
            project_response = requests.get(project_url, headers=self.headers)

            if project_response.status_code == 200:
                scopes["project:read"] = True
            else:
                scopes["project:read"] = (
                    f"Failed to access project data: {project_response.status_code}"
                )

            # Test session recording access
            recordings_url = f"{self.base_url}/projects/{self.authentication_config.project_id}/session_recordings"
            params = {"limit": 1}
            recordings_response = requests.get(
                recordings_url, headers=self.headers, params=params
            )

            if recordings_response.status_code == 200:
                scopes["session_recording:read"] = True
            else:
                scopes["session_recording:read"] = (
                    f"Failed to access session recordings: {recordings_response.status_code}"
                )

            # Test session recording playlist access
            playlists_url = f"{self.base_url}/projects/{self.authentication_config.project_id}/session_recording_playlists"
            playlists_response = requests.get(playlists_url, headers=self.headers)

            if playlists_response.status_code == 200:
                scopes["session_recording_playlist:read"] = True
            else:
                scopes["session_recording_playlist:read"] = (
                    f"Failed to access recording playlists: {playlists_response.status_code}"
                )

        except Exception as e:
            self.logger.exception("Failed to validate PostHog scopes")
            for scope in [
                "project:read",
                "session_recording:read",
                "session_recording_playlist:read",
            ]:
                if scope not in scopes:
                    scopes[scope] = str(e)
        return scopes

    def validate_config(self):
        self.authentication_config = PosthogProviderAuthConfig(
            **self.config.authentication
        )

    def get_session_recording_domains(
        self,
        hours: int = 24,
        limit: int = 500,
    ):
        """
        Get a list of domains from session recordings within a specified time period.

        Args:
            hours (int): Number of hours to look back (default: 24)
            limit (int): Maximum number of recordings to fetch (default: 100)

        Returns:
            dict: Dictionary containing unique domains and their frequency
        """
        self.logger.info(
            f"Fetching session recording domains for the last {hours} hours"
        )

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        # Format timestamps for API
        start_timestamp = start_time.isoformat() + "Z"  # ISO format with Z for UTC
        end_timestamp = end_time.isoformat() + "Z"

        # API endpoint
        recordings_endpoint = f"{self.base_url}/projects/{self.authentication_config.project_id}/session_recordings"

        # API request parameters
        params = {
            "date_from": start_timestamp,
            "date_to": end_timestamp,
            "limit": limit,
        }

        # Make initial request
        response = requests.get(
            recordings_endpoint, params=params, headers=self.headers
        )

        if response.status_code != 200:
            self.logger.error(
                "Failed to fetch session recordings",
                extra={"status_code": response.status_code, "response": response.text},
            )
            raise Exception(
                f"API request failed with status code {response.status_code}: {response.text}"
            )

        # Parse response
        data = response.json()
        recordings = data.get("results", [])

        # Handle pagination if needed
        while data.get("next") and recordings and len(recordings) < limit:
            response = requests.get(data["next"], headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                recordings.extend(data.get("results", []))
            else:
                self.logger.error(
                    "Failed to fetch additional session recordings",
                    extra={"status_code": response.status_code},
                )
                break

        # Extract domains from each recording
        domains = set()

        for recording in recordings:
            # Get recording details to extract URLs
            recording_id = recording.get("id")
            parsed_url = urlparse(recording["start_url"])
            domain = parsed_url.netloc
            if domain:
                domains.add(domain)
            else:
                print(f"No domain found for recording ID {recording_id}")

        # Count domain frequencies
        domain_counter = Counter(domains)

        # Get unique domains
        unique_domains = list(domain_counter.keys())

        return {
            "unique_domains": unique_domains,
            "domain_counts": dict(domain_counter),
            "total_domains_found": len(domains),
            "unique_domains_count": len(unique_domains),
        }

    def get_session_recordings(
        self,
        hours: int = 24,
        limit: int = 100,
    ):
        """
        Get session recordings within a specified time period.

        Args:
            hours (int): Number of hours to look back (default: 24)
            limit (int): Maximum number of recordings to fetch (default: 100)

        Returns:
            dict: Dictionary containing session recordings data
        """
        self.logger.info(f"Fetching session recordings for the last {hours} hours")

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        # Format timestamps for API
        start_timestamp = start_time.isoformat() + "Z"  # ISO format with Z for UTC
        end_timestamp = end_time.isoformat() + "Z"

        # API endpoint
        recordings_endpoint = f"{self.base_url}/projects/{self.authentication_config.project_id}/session_recordings"

        # API request parameters
        params = {
            "date_from": start_timestamp,
            "date_to": end_timestamp,
            "limit": limit,
        }

        # Make initial request
        response = requests.get(
            recordings_endpoint, params=params, headers=self.headers
        )

        if response.status_code != 200:
            self.logger.error(
                "Failed to fetch session recordings",
                extra={"status_code": response.status_code, "response": response.text},
            )
            raise Exception(
                f"API request failed with status code {response.status_code}: {response.text}"
            )

        # Parse response
        data = response.json()
        recordings = data.get("results", [])

        # Handle pagination if needed
        while data.get("next") and recordings and len(recordings) < limit:
            response = requests.get(data["next"], headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                recordings.extend(data.get("results", []))
            else:
                self.logger.error(
                    "Failed to fetch additional session recordings",
                    extra={"status_code": response.status_code},
                )
                break

        # Summarize basic information for each recording
        recording_summaries = []
        for recording in recordings:
            recording_summaries.append(
                {
                    "id": recording.get("id"),
                    "start_time": recording.get("start_time"),
                    "end_time": recording.get("end_time"),
                    "duration": recording.get("duration"),
                    "person": recording.get("person"),
                    "start_url": recording.get("start_url"),
                }
            )

        return {
            "recordings": recording_summaries,
            "total_recordings": len(recording_summaries),
            "time_range": {"start": start_timestamp, "end": end_timestamp},
        }

    def _query(self, query_type="", hours=24, limit=100, **kwargs: dict):
        """
        Query PostHog data.

        Args:
            query_type (str): Type of query (e.g., "session_recording_domains", "session_recordings")
            hours (int): Number of hours to look back
            limit (int): Maximum number of items to fetch
            **kwargs: Additional arguments

        Returns:
            dict: Query results
        """
        if query_type == "session_recording_domains":
            return self.get_session_recording_domains(hours=hours, limit=limit)
        elif query_type == "session_recordings":
            return self.get_session_recordings(hours=hours, limit=limit)
        else:
            raise NotImplementedError(f"Query type {query_type} not implemented")

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass


if __name__ == "__main__":
    # Output debug messages
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Load environment variables
    posthog_api_key = os.environ.get("POSTHOG_API_KEY")
    posthog_project_id = os.environ.get("POSTHOG_PROJECT_ID")
    assert posthog_api_key
    assert posthog_project_id

    # Initialize the provider and provider config
    config = ProviderConfig(
        description="PostHog Provider",
        authentication={"api_key": posthog_api_key, "project_id": posthog_project_id},
    )
    provider = PosthogProvider(
        context_manager, provider_id="posthog-test", config=config
    )

    # Query session recording domains
    domains_result = provider.query(
        query_type="session_recording_domains", hours=24, limit=100
    )
    print(f"Found {len(domains_result['unique_domains'])} unique domains:")
    for domain, count in domains_result["domain_counts"].items():
        print(f"{domain}: {count} occurrences")
