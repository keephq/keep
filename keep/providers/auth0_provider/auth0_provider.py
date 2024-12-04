"""
Auth0 provider.
"""

import dataclasses
import datetime
import os

import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@dataclasses.dataclass
class Auth0ProviderAuthConfig:
    """
    Auth0 authentication configuration.
    """

    domain: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Auth0 Domain",
            "hint": "https://tenantname.us.auth0.com",
            "validation": "https_url",
        },
    )

    token: str = dataclasses.field(
        metadata={
            "required": True,
            "sensitive": True,
            "description": "Auth0 API Token",
            "hint": "https://manage.auth0.com/dashboard/us/YOUR_ACCOUNT/apis/management/explorer",
        },
    )


class Auth0Provider(BaseProvider):
    """Enrich alerts with data from Auth0."""

    PROVIDER_DISPLAY_NAME = "Auth0"
    PROVIDER_CATEGORY = ["Identity and Access Management"]

    provider_id: str
    config: ProviderConfig

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Auth0 provider.
        """
        self.authentication_config = Auth0ProviderAuthConfig(
            **self.config.authentication
        )

    def _query(self, log_type: str, from_: str = None, **kwargs: dict):
        """
        Query Auth0 logs.

        Args:
            log_type (str): The log type: https://auth0.com/docs/deploy-monitor/logs/log-event-type-codes
            from_ (str, optional): 2023-09-10T11:43:34.213Z for example. Defaults to None.

        Raises:
            Exception: _description_

        Returns:
            _type_: _description_
        """
        url = f"{self.authentication_config.domain}/api/v2/logs"
        headers = {
            "content-type": "application/json",
            "Authorization": f"Bearer {self.authentication_config.token}",
        }
        if not log_type:
            raise Exception("log_type is required")
        params = {
            "q": f"type:{log_type}",  # Lucene query syntax to search for logs with type 's' (Success Signup)
            "per_page": 100,  # specify the number of entries per page
        }
        if from_:
            params["q"] = (
                f"({params['q']}) AND (date:[{from_} TO {datetime.datetime.now().isoformat()}])"
            )
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        logs = response.json()
        return logs

    def dispose(self):
        pass


class Auth0LogsProvider(Auth0Provider):
    def _query(self, log_type: str, previous_users: list, **kargs: dict):
        logs = super().query(log_type=log_type, **kargs)

        self.logger.debug(f"Previous users: {previous_users}")
        previous_users_count = len(previous_users)
        users_count = len(logs)
        self.logger.debug(f"New users: {users_count - int(previous_users_count)}")
        new_users = []
        for log in logs:
            if log["user_id"] not in previous_users:
                self.logger.debug(f"New user: {log['user_id']}")
                new_users.append(log)
        return {
            "users": [log["user_id"] for log in logs],
            "new_users": new_users,
            "new_users_count": len(new_users),
        }


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # If you want to use application default credentials, you can omit the authentication config
    config = {
        "authentication": {
            "token": os.environ.get("AUTH0_TOKEN"),
            "domain": os.environ.get("AUTH0_PROVIDER_DOMAIN"),
        },
    }
    # Create the provider
    provider = Auth0Provider(
        context_manager, provider_id="auth0-provider", config=ProviderConfig(**config)
    )

    logs = provider.query(log_type="f", from_="2023-09-10T11:43:34.213Z")
    print(logs)
