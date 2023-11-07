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
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NewrelicProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "New Relic API key (Use admin Admin API Key for auto webhook integration)",
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
    PROVIDER_SCOPES = [
        ProviderScope(
            name="ai.issues:read",
            description="Requried to read issues and related information",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://docs.newrelic.com/docs/accounts/accounts-billing/new-relic-one-user-management/user-management-concepts/",
            alias="Rules Reader",
        ),
        ProviderScope(
            name="ai.destinations:read",
            description="Required to read whether keep webhooks are registered",
            mandatory=False,
            mandatory_for_webhook=True,
            documentation_url="https://docs.newrelic.com/docs/accounts/accounts-billing/new-relic-one-user-management/user-management-concepts/",
            alias="Rules Reader",
        ),
        ProviderScope(
            name="ai.destinations:write",
            description="Required to register keep webhooks",
            mandatory=False,
            mandatory_for_webhook=True,
            documentation_url="https://docs.newrelic.com/docs/accounts/accounts-billing/new-relic-one-user-management/user-management-concepts/",
            alias="Rules Reader",
        ),
        ProviderScope(
            name="ai.channels:read",
            description="Required to know informations about notification channels.",
            mandatory=False,
            mandatory_for_webhook=True,
            documentation_url="https://docs.newrelic.com/docs/accounts/accounts-billing/new-relic-one-user-management/user-management-concepts/",
            alias="Rules Reader",
        ),
        ProviderScope(
            name="ai.channels:write",
            description="Required to create notification channel",
            mandatory=False,
            mandatory_for_webhook=True,
            documentation_url="https://docs.newrelic.com/docs/accounts/accounts-billing/new-relic-one-user-management/user-management-concepts/",
            alias="Rules Reader",
        ),
    ]

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

    def __make_add_webhook_destination_query(self, url: str, name: str) -> dict:
        query = f"""mutation {{
                        aiNotificationsCreateDestination(
                            accountId: {self.newrelic_config.account_id}
                            destination: {{
                                type: WEBHOOK, 
                                name: "{name}",
                                properties: [{{key: "url", value:"{url}"}}]}}
                        ) {{
                            destination {{
                                id
                                name
                            }}
                        }}
 
                    }}"""

        return {
            "query": query,
        }
    def __make_delete_webhook_destination_query(self,destination_id:str): 
        query = f"""mutation {{
                        aiNotificationsDeleteDestination(
                            accountId: {self.newrelic_config.account_id}
                            destinationId: "{destination_id}"
                        ) {{
                            ids
                        }}
 
                    }}"""

        return {
            "query": query,
        }   
    
    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {scope.name: False for scope in self.PROVIDER_SCOPES}
        read_scopes = [key for key in scopes.keys() if "read" in key]

        try:
            """
            try to check all read scopes
            """
            query = {
                "query": f"""
                    {{
                        actor {{
                            account(id: {self.newrelic_config.account_id}) {{
                            aiIssues {{
                                issues {{
                                issues {{
                                    acknowledgedAt
                                    acknowledgedBy
                                    activatedAt
                                    closedAt
                                    closedBy
                                    mergeReason
                                    mutingState
                                    parentMergeId
                                    unAcknowledgedAt
                                    unAcknowledgedBy
                                }}
                                }}
                            }}
                            aiNotifications {{
                                destinations {{
                                    entities {{name}}
                                }}
                                channels {{
                                    entities {{name}}
                                }}
                            }}
                            }}
                        }}
                        }}
               """
            }

            response = requests.post(
                self.new_relic_graphql_url,
                headers={"Api-Key": self.newrelic_config.api_key},
                json=query,
            )
            content = response.content.decode("utf-8")
            if "errors" in content:
                raise

            for read_scope in read_scopes:
                scopes[read_scope] = True
        except Exception as e:
            self.logger.exception(
                "Error while trying to validate read scopes from new relic"
            )
            return scopes

        write_scopes = [key for key in scopes.keys() if "write" in key]
        try:
            """
            Checking if destination can be created
            Delete at the end if created

            Destinations can be only be created through ADMIN User key,
            this means if this succeeds any write will succeed, including channels.

            
            reference: https://api.newrelic.com/docs/#/Deprecation%20Notice%20-%20Alerts%20Channels/post_alerts_channels_json
            not mentioned in GraphQL docs though
            """
            
            query = self.__make_add_webhook_destination_query(
                url="https://api.localhost.com", name="keep-webhook-test"
            ) # tried to do with localhost and port, didn't worked
            response = requests.post(
                self.new_relic_graphql_url,
                headers={"Api-Key": self.newrelic_config.api_key},
                json=query,
            )
            content = response.content.decode("utf-8")
            
            
            # delete created destination
            id = response.json()['data']['aiNotificationsCreateDestination']['destination']['id']
            query = self.__make_delete_webhook_destination_query(id)
            response = requests.post(
                self.new_relic_graphql_url,
                headers={"Api-Key": self.newrelic_config.api_key},
                json=query,
            )
            content = response.content.decode("utf-8")
            
            if 'errors' in content:
                raise 
            
            for write_scope in write_scopes:
                scopes[write_scope] = True
        except Exception as e:
            self.logger.exception(
                "Error while trying to validate write scopes from new relic"
            )

        return scopes

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        return super().setup_webhook(tenant_id, keep_api_url, api_key, setup_alerts)

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
                        account(id: {self.newrelic_config.account_id}) {{
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
                lastReceived = datetime.utcfromtimestamp(lastReceived / 1000).strftime(
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
    print(api_key, account_id)
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
    
    scopes = provider.validate_scopes()
    print(scopes)

    alerts = provider.get_alerts()
    print(alerts)
