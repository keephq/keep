"""
Auth0 provider.
"""
import dataclasses
import os
from typing import Optional

import requests
from pydantic.dataclasses import dataclass

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@dataclasses.dataclass
class Auth0ProviderAuthConfig:
    """
    Auth0 authentication configuration.
    """

    token: str = dataclasses.field(
        default=None,
        metadata={
            "required": True,
            "description": "Auth0 api token",
            "hint": "https://manage.auth0.com/dashboard/us/YOUR TENANT/apis/management/explorer",
        },
    )
    domain: str = dataclasses.field(
        default=None,
        metadata={
            "required": True,
            "description": "Auth0 domain",
        },
    )


class Auth0Provider(BaseProvider):
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
        if self.config.authentication is None:
            self.config.authentication = {}
        self.authentication_config = Auth0ProviderAuthConfig(
            **self.config.authentication
        )

    def notify(self, **kwargs):
        pass  # Define how to notify about any alerts or issues

    def dispose(self):
        pass


class Auth0LogsProvider(Auth0Provider):
    def _query(self, **kargs: dict):
        url = f"https://{self.authentication_config.domain}/api/v2/logs"
        headers = {
            "content-type": "application/json",
            "Authorization": f"Bearer {self.authentication_config.token}",
        }
        log_type = kargs.get("log_type")
        previous_users = kargs.get("previous_users", [])
        if not log_type:
            raise Exception("log_type is required")
        # types: https://auth0.com/docs/deploy-monitor/logs/log-event-type-codes
        params = {
            "q": f"type:{log_type}",  # Lucene query syntax to search for logs with type 's' (Success Signup)
            "per_page": 100,  # specify the number of entries per page
        }
        response = requests.get(url, headers=headers, params=params)
        logs = []
        if response.status_code == 200:
            logs = response.json()
            if isinstance(logs, list):
                logs = logs
            else:
                print(
                    f"Expected a list but got {type(logs)}. Here is the response: {logs}"
                )
        else:
            print(
                f"Failed to get logs. Status code: {response.status_code}, message: {response.text}"
            )

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

    def get_alerts(self, alert_id: Optional[str] = None):
        pass  # Define how to get alerts from BigQuery if applicable

    def deploy_alert(self, alert: dict, alert_id: Optional[str] = None):
        pass  # Define how to deploy an alert to BigQuery if applicable

    @staticmethod
    def get_alert_schema() -> dict:
        pass  # Return alert schema specific to BigQuery

    def get_logs(self, limit: int = 5) -> list:
        pass  # Define how to get logs from BigQuery if applicable

    def expose(self):
        return {}  # Define any parameters to expose


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
    provider = Auth0LogsProvider(
        context_manager, provider_id="auth0-provider", config=ProviderConfig(**config)
    )

    users = provider.query(log_type="ss")
    previous_users = users.get("users")
    users = provider.query(log_type="ss", previous_users=previous_users)
    print(users)
