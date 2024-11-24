"""
NewrelicProvider is a provider that provides a way to interact with New Relic.
"""

import dataclasses
import json
import logging
from datetime import datetime

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NewrelicProviderAuthConfig:
    """
    Destinations can be only be created through ADMIN User key.

    reference: https://api.newrelic.com/docs/#/Deprecation%20Notice%20-%20Alerts%20Channels/post_alerts_channels_json
    not mentioned in GraphQL docs though, got to know after trying this out.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "New Relic User key. To receive webhooks, use `User key` of an admin account",
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
    """Get alerts from New Relic into Keep."""

    PROVIDER_CATEGORY = ["Monitoring"]
    NEWRELIC_WEBHOOK_NAME = "keep-webhook"
    PROVIDER_DISPLAY_NAME = "New Relic"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="ai.issues:read",
            description="Required to read issues and related information",
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
            alias="Rules Writer",
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
            alias="Rules Writer",
        ),
    ]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "open": AlertStatus.FIRING,
        "closed": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
    }

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
            ProviderConfigException: new_relic_api_url must start with https
        """
        self.newrelic_config = NewrelicProviderAuthConfig(**self.config.authentication)
        if (
            self.newrelic_config.new_relic_api_url
            and not self.newrelic_config.new_relic_api_url.startswith("https")
        ):
            raise ProviderConfigException(
                "New Relic API URL must start with https", self.provider_id
            )

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

    def __make_delete_webhook_destination_query(self, destination_id: str):
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
                headers=self.__headers,
                json=query,
            )
            content = response.content.decode("utf-8")
            if "errors" in content:
                raise

            for read_scope in read_scopes:
                scopes[read_scope] = True
        except Exception:
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
            not mentioned in GraphQL docs though, got to know after trying this out.
            """

            query = self.__make_add_webhook_destination_query(
                url="https://api.localhost.com", name="keep-webhook-test"
            )  # tried to do with localhost and port, didn't worked
            response = requests.post(
                self.new_relic_graphql_url,
                headers=self.__headers,
                json=query,
            )
            content = response.content.decode("utf-8")

            # delete created destination
            id = response.json()["data"]["aiNotificationsCreateDestination"][
                "destination"
            ]["id"]
            query = self.__make_delete_webhook_destination_query(id)
            response = requests.post(
                self.new_relic_graphql_url,
                headers=self.__headers,
                json=query,
            )
            content = response.content.decode("utf-8")

            if "errors" in content:
                raise

            for write_scope in write_scopes:
                scopes[write_scope] = True
        except Exception:
            self.logger.exception(
                "Error while trying to validate write scopes from new relic"
            )

        return scopes

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

        query = f'{{actor {{account(id: {self.newrelic_config.account_id}) {{nrql(query: "{nrql}") {{results}}}}'
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

    @property
    def __headers(self):
        return {
            "Api-Key": self.newrelic_config.api_key,
            "Content-Type": "application/json",
        }

    def get_alerts(self) -> list[AlertDto]:
        formatted_alerts = []

        headers = self.__headers
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
                lastReceived = datetime.fromtimestamp(lastReceived / 1000).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            alert = AlertDto(
                id=issue["issueId"],
                name=(
                    issue["title"][0] if issue["title"] else None
                ),  # Assuming the first title in the list
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

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """We are already registering template same as generic AlertDTO"""
        logger = logging.getLogger(__name__)
        logger.info("Got event from New Relic")
        lastReceived = event.pop("lastReceived", None)
        # from Keep policy
        if lastReceived:
            if isinstance(lastReceived, int):
                lastReceived = datetime.utcfromtimestamp(
                    lastReceived / 1000
                ).isoformat()
            else:
                # WTF?
                logger.error("lastReceived is not int")
                pass
        else:
            lastReceived = datetime.utcfromtimestamp(
                event.get("updatedAt", 0) / 1000
            ).isoformat()

        # format status and severity to Keep format
        status = event.pop("status", "") or event.pop("state", "")
        status = NewrelicProvider.STATUS_MAP.get(status.lower(), AlertStatus.FIRING)

        severity = event.pop("severity", "") or event.pop("priority", "")
        severity = NewrelicProvider.SEVERITIES_MAP.get(
            severity.lower(), AlertSeverity.INFO
        )

        name = event.pop("name", "")
        if not name:
            name = event.get("title", "")

        logger.info("Formatted event from New Relic")
        # TypeError: keep.api.models.alert.AlertDto() got multiple values for keyword argument 'source'"
        if "source" in event:
            newrelic_source = event.pop("source")

        return AlertDto(
            source=["newrelic"],
            name=name,
            lastReceived=lastReceived,
            status=status,
            severity=severity,
            newrelic_source=newrelic_source,
            **event,
        )

    def __get_all_policy_ids(
        self,
    ) -> list[str]:
        try:
            query = {
                "query": f"""
                        {{
                            actor {{
                                account(id: {self.newrelic_config.account_id}) {{
                                    alerts {{
                                        policiesSearch {{
                                            policies {{
                                                id
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                        }}
                        """
            }
            response = requests.post(
                self.new_relic_graphql_url, headers=self.__headers, json=query
            )
            content = response.content.decode("utf-8")

            if "errors" in content:
                raise
            all_objects = response.json()["data"]["actor"]["account"]["alerts"][
                "policiesSearch"
            ]["policies"]
            return [obj["id"] for obj in all_objects]
        except Exception as e:
            self.logger.error(f"Error while fetching ploicies: {e}")

        return []

    def __get_webhook_destination_id_by_name_and_url(
        self, name: str, url: str
    ) -> str | None:
        try:
            query = {
                "query": f"""
                    {{
                        actor {{
                            account(id: {self.newrelic_config.account_id}) {{
                                aiNotifications {{
                                    destinations(filters: {{
                                        name: "{name}",
                                        type: WEBHOOK,
                                        property: {{ key: "url", value: "{url}" }}
                                    }}) {{
                                        entities {{
                                            id
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                """
            }

            response = requests.post(
                self.new_relic_graphql_url, headers=self.__headers, json=query
            )
            id_list = response.json()["data"]["actor"]["account"]["aiNotifications"][
                "destinations"
            ]["entities"]
            return id_list[0]["id"]
        except Exception:
            self.logger.error("Error getting destination id")

    def __add_webhook_destination(self, name: str, url: str) -> str | None:
        try:
            query = self.__make_add_webhook_destination_query(name=name, url=url)
            response = requests.post(
                self.new_relic_graphql_url, headers=self.__headers, json=query
            )

            new_id = response.json()["data"]["aiNotificationsCreateDestination"][
                "destination"
            ]["id"]
            return new_id
        except Exception:
            self.logger.exception("Error creating destination for webhook")

    def __get_channel_id_by_destination_and_name(self, destination_id: str, name: str):
        try:
            query = {
                "query": f"""
                    {{
                        actor {{
                            account(id: {self.newrelic_config.account_id}) {{
                                aiNotifications {{
                                    channels(filters: {{
                                        destinationId: "{destination_id}",
                                        name: "{name}"
                                    }}) {{
                                        entities {{
                                            id
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                """
            }

            response = requests.post(
                self.new_relic_graphql_url, headers=self.__headers, json=query
            )
            id_list = response.json()["data"]["actor"]["account"]["aiNotifications"][
                "channels"
            ]["entities"]

            return id_list[0]["id"]

        except Exception:
            self.logger.error("Exception fetching channel id")

    def __add_new_channel(
        self, destination_id: str, name: str, api_key: str
    ) -> str | None:
        try:
            """
            To update the payload template
            Go to new relic -> Alerts & Ai ->  workflows -> create the new channel int (Notfy section).
            Here set the template you want
            once set query channels with sort in descending order by CREATED_AT, maek sure to choose pay key and value in enteties.
            copy the string value of format
            change:
                { to {{,
                } to }},
                \n to \\n,
                \t to \\t,
                " to \"
            """

            mutation_query = """
            mutation {{
                aiNotificationsCreateChannel(
                    accountId: {account_id},
                    channel: {{
                        name: "{name}",
                        product: IINT,
                        type: WEBHOOK,
                        destinationId: "{destination_id}",
                        properties: [
                            {{
                                key: "headers",
                                value: "{{ \\\"X-API-KEY\\\":\\\"{api_key}\\\"}}"
                            }},
                            {{
                                key: "payload",
                                value: "{{\\n\\t\\\"id\\\": {{{{ json issueId }}}},\\n\\t\\\"issueUrl\\\": {{{{ json issuePageUrl }}}},\\n\\t\\\"name\\\": {{{{ json annotations.title.[0] }}}},\\n\\t\\\"severity\\\": {{{{ json priority }}}},\\n\\t\\\"impactedEntities\\\": {{{{ json entitiesData.names }}}},\\n\\t\\\"totalIncidents\\\": {{{{ json totalIncidents }}}},\\n\\t\\\"status\\\": {{{{ json state }}}},\\n\\t\\\"trigger\\\": {{{{ json triggerEvent }}}},\\n\\t\\\"isCorrelated\\\": {{{{ json isCorrelated }}}},\\n\\t\\\"createdAt\\\": {{{{ createdAt }}}},\\n\\t\\\"updatedAt\\\": {{{{ updatedAt }}}},\\n\\t\\\"lastReceived\\\": {{{{ updatedAt }}}},\\n\\t\\\"source\\\": {{{{ json accumulations.source }}}},\\n\\t\\\"alertPolicyNames\\\": {{{{ json accumulations.policyName }}}},\\n\\t\\\"alertConditionNames\\\": {{{{ json accumulations.conditionName }}}},\\n\\t\\\"workflowName\\\": {{{{ json workflowName }}}}\\n}}"
                            }}
                        ]
                    }}
                ) {{
                    channel {{
                        id
                    }}
                }}
            }}
            """.format(
                account_id=self.newrelic_config.account_id,
                destination_id=destination_id,
                name=name,
                api_key=api_key,
            )

            query = {"query": mutation_query}
            # print(query)
            response = requests.post(
                self.new_relic_graphql_url, headers=self.__headers, json=query
            )
            # print(response.json())
            new_id = response.json()["data"]["aiNotificationsCreateChannel"]["channel"][
                "id"
            ]
            return new_id
        except Exception:
            self.logger.exception("Error creating channel for webhook")

    def __get_workflow_by_name_and_channel(
        self, name: str, channel_id: str
    ) -> str | None:
        try:
            query = {
                "query": f"""{{
                            actor {{
                                account(id: {self.newrelic_config.account_id}) {{
                                    aiWorkflows {{
                                        workflows(
                                            filters: {{name: "{name}", channelId: "{channel_id}"}}
                                        ) {{
                                            entities {{
                                                id
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                        }}
                """
            }

            response = requests.post(
                self.new_relic_graphql_url, headers=self.__headers, json=query
            )

            id_list = response.json()["data"]["actor"]["account"]["aiWorkflows"][
                "workflows"
            ]["entities"]
            # print(id_list)
            return id_list[0]["id"]
        except Exception:
            self.logger.error("Error getting workflow by name and channel")

    def __add_new_worflow(
        self, channel_id: str, policy_ids: list, name: str
    ) -> str | None:
        try:
            query = {
                "query": f"""
                mutation {{
                    aiWorkflowsCreateWorkflow(
                        accountId: {self.newrelic_config.account_id}
                        createWorkflowData: {{
                            destinationConfigurations: {{
                                channelId: "{channel_id}",
                                notificationTriggers: [ACTIVATED, ACKNOWLEDGED, CLOSED, PRIORITY_CHANGED, OTHER_UPDATES]
                            }},
                            issuesFilter: {{
                                predicates: [
                                    {{
                                        attribute: "labels.policyIds",
                                        operator: EXACTLY_MATCHES,
                                        values: {json.dumps(policy_ids)}
                                    }}
                                ],
                                type: FILTER
                            }},
                            workflowEnabled: true,
                            destinationsEnabled: true,
                            mutingRulesHandling: DONT_NOTIFY_FULLY_MUTED_ISSUES
                            name: "{name}",
                        }}
                    ) {{
                        workflow {{
                            id
                        }}
                    }}
                }}
                """
            }

            response = requests.post(
                self.new_relic_graphql_url, headers=self.__headers, json=query
            )
            # print(response.content.decode("utf-8"))
            return response.json()["data"]["aiWorkflowsCreateWorkflow"]["workflow"][
                "id"
            ]
        except Exception:
            self.logger.exception("Error creating channel for webhook")

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        """
        -> Fetch all policy ids

        -> Get/Create destination to keep webhook api url and get the created id

        -> Get/Create channel adding all policies to given destination id

        -> Get/Create workflow on a given channel
        """

        self.logger.info("Setting up webhook to new relic")
        webhook_name = self.NEWRELIC_WEBHOOK_NAME + "-" + tenant_id

        policy_ids = []
        self.logger.info("Fetching policies")
        policy_ids = self.__get_all_policy_ids()
        if not policy_ids:
            raise Exception("Not able to get policies")

        destination_id = self.__get_webhook_destination_id_by_name_and_url(
            name=webhook_name, url=keep_api_url
        )
        if not destination_id:
            destination_id = self.__add_webhook_destination(
                name=webhook_name, url=keep_api_url
            )
        if not destination_id:
            raise Exception("Not able to get webhook destination")

        channel_id = self.__get_channel_id_by_destination_and_name(
            destination_id, webhook_name
        )
        if not channel_id:
            channel_id = self.__add_new_channel(
                name=webhook_name, destination_id=destination_id, api_key=api_key
            )
        if not channel_id:
            raise Exception("Not able to get channels")

        worflow_id = self.__get_workflow_by_name_and_channel(
            name=webhook_name, channel_id=channel_id
        )

        if not worflow_id:
            worflow_id = self.__add_new_worflow(
                name=webhook_name, channel_id=channel_id, policy_ids=policy_ids
            )
        if not worflow_id:
            raise Exception("Not able to add worflow")

        self.logger.info(f"New relic webhook successfuly setup {worflow_id}")


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

    scopes = provider.validate_scopes()
    # print(scopes)

    alerts = provider.get_alerts()
    # print(alerts)

    created = provider.setup_webhook(
        tenant_id="test-v2",
        keep_api_url="https://6fd6-2401-4900-1cb0-3b5f-6d04-474-81c5-30c7.ngrok-free.app/alerts/event",
        setup_alerts=True,
    )
    # print(created)
