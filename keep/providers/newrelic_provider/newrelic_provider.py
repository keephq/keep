"""
NewrelicProvider is a provider that provides a way to interact with New Relic.
"""

import dataclasses
from datetime import datetime

import pydantic
import requests

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class NewrelicProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "New Relic API key",
            "sensitive": True,
        }
    )
    account_id: str = dataclasses.field(
        metadata={"required": True, "description": "New Relic account ID"}
    )
    new_relic_api_url: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "New Relic API URL",
        },
        default="https://api.newrelic.com",
    )


class NewrelicProvider(BaseProvider):
    """Pull alerts from New Relic into Keep."""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Nothing to dispose here
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for New-Relic provider.

        Raises:
            ProviderConfigException: user or account is missing in authentication.
            ProviderConfigException: private key
        """
        self.newrelic_config = NewrelicProviderAuthConfig(**self.config.authentication)

    @property
    def new_relic_graphql_url(self):
        return f"{self.newrelic_config.new_relic_api_url}/graphql"

    @property
    def new_relic_alert_url(self):
        return f"{self.newrelic_config.new_relic_api_url}/v2/alerts_violations.json"

    def _query(self, nrql="", **kwargs: dict):
        """
        Query New Relic account using the given NRQL

        Args:
            query (str): query to execute

        Returns:
            list[tuple] | list[dict]: results of the query
        """
        if not nrql:
            raise ProviderConfigException(
                "Missing NRQL query", provider_id=self.provider_id
            )

        query = '{actor {account(id: %s) {nrql(query: "%s") {results}}}}'.format(
            self.newrelic_config.account_id, nrql
        )
        payload = {"query": query}

        response = requests.post(
            self.new_relic_graphql_url,
            headers={"Api-Key": self.newrelic_config.api_key},
            json=payload,
        )
        if not response.ok:
            self.logger.debug(
                "Failed to query New Relic",
                extra={"response": response.text, "query": query},
            )
            raise ProviderException(f"Failed to query New Relic: {response.text}")
        # results are in response.json()['data']['actor']['account']['nrql']['results'], should we return this?
        return response.json()

    def get_alerts(self) -> list[AlertDto]:
        formatted_alerts = []

        headers = {"Api-Key": self.newrelic_config.api_key}
        # GraphQL query for listing issues
        query = {
            "query": f"""
                {{
                    actor {{
                        account(id: 3810236) {{
                        aiIssues {{
                            issues {{
                            issues {{
                                account {{
                                id
                                name
                                }}
                                acknowledgedAt
                                acknowledgedBy
                                activatedAt
                                closedAt
                                closedBy
                                conditionFamilyId
                                conditionName
                                conditionProduct
                                correlationRuleDescriptions
                                correlationRuleIds
                                correlationRuleNames
                                createdAt
                                deepLinkUrl
                                description
                                entityGuids
                                entityNames
                                entityTypes
                                eventType
                                incidentIds
                                isCorrelated
                                isIdle
                                issueId
                                mergeReason
                                mutingState
                                origins
                                parentMergeId
                                policyIds
                                policyName
                                priority
                                sources
                                state
                                title
                                totalIncidents
                                unAcknowledgedBy
                                unAcknowledgedAt
                                updatedAt
                                wildcard
                            }}
                            }}
                        }}
                        }}
                    }}
                    }}
            """
        }

        response = requests.post(
            self.new_relic_graphql_url, headers=headers, json=query
        )
        response.raise_for_status()

        data = response.json()

        # Extract and format the issues
        issues_data = data["data"]["actor"]["account"]["aiIssues"]["issues"]["issues"]
        formatted_alerts = []

        for issue in issues_data:
            lastReceived = issue["updatedAt"] if "updatedAt" in issue else None
            # convert to date
            if lastReceived:
                lastReceived = datetime.fromtimestamp(lastReceived / 1000).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            alert = AlertDto(
                id=issue["issueId"],
                name=issue["title"][0]
                if issue["title"]
                else None,  # Assuming the first title in the list
                status=issue["state"],
                lastReceived=lastReceived,
                severity=issue["priority"],
                message=None,  # New Relic doesn't provide a direct "message" field
                description=issue["description"][0] if issue["description"] else None,
                source=["newrelic"],
                acknowledgedAt=issue["acknowledgedAt"],
                acknowledgedBy=issue["acknowledgedBy"],
                activatedAt=issue["activatedAt"],
                closedAt=issue["closedAt"],
                closedBy=issue["closedBy"],
                createdAt=issue["createdAt"],
            )
            formatted_alerts.append(alert)

        return formatted_alerts


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

    api_key = os.environ.get("NEWRELIC_API_KEY")
    account_id = os.environ.get("NEWRELIC_ACCOUNT_ID")

    provider_config = {
        "authentication": {"api_key": api_key, "account_id": account_id},
    }
    from keep.providers.providers_factory import ProvidersFactory

    provider = ProvidersFactory.get_provider(
        context_manager=context_manager,
        provider_id="newrelic-keephq",
        provider_type="newrelic",
        provider_config=provider_config,
    )

    alerts = provider.get_alerts()
    print(alerts)
