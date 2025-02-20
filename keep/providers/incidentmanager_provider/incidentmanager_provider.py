"""
IncidentManagerProvider is a class that provides a way to read data from AWS Incident Manager.
"""

import dataclasses
import logging
import os
from urllib.parse import urlparse
from uuid import uuid4

import boto3
import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class IncidentmanagerProviderAuthConfig:
    access_key: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "AWS access key (Leave empty if using IAM role at EC2)",
            "sensitive": True,
        }
    )
    access_key_secret: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "AWS access key secret (Leave empty if using IAM role at EC2)",
            "sensitive": True,
        }
    )
    region: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS region",
            "senstive": False,
        },
    )
    response_plan_arn: str = dataclasses.field(
        default=None,
        metadata={
            "required": True,
            "description": "AWS Response Plan's arn",
            "hint": "Default response plan arn to use when interacting with incidents, if not provided, we won't be able to register web hook for the incidents",
            "sensitive": False,
        },
    )

    sns_topic_arn: str = dataclasses.field(
        default=None,
        metadata={
            "required": True,
            "description": "AWS SNS Topic arn you want to be used/using in response plan",
            "hint": "Default sns topic to use when creating incidents, if not provided, we won't be able to register web hook for the incidents",
            "sensitive": False,
        },
    )


class IncidentmanagerProvider(BaseProvider):
    """Push incidents from AWS IncidentManager to Keep."""

    PROVIDER_CATEGORY = ["Incident Management"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="ssm-incidents:ListIncidentRecords",
            description="Required to retrieve incidents.",
            documentation_url="https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm-incidents.html",
            mandatory=True,
            alias="Describe Incidents",
        ),
        # this is not needed until we figure out how to override dismiss call
        # ProviderScope(
        #     name="ssm-incidents:UpdateIncidentRecord",
        #     description="Required to update incidents, when you resolve them for example.",
        #     documentation_url="https://docs.aws.amazon.com/incident-manager/latest/userguide/what-is-incident-manager.html#features",
        #     mandatory=False,
        #     alias="Update Incident Records",
        # ),
        ProviderScope(
            name="ssm-incidents:GetResponsePlan",
            description="Required to get response plan and register keep as webhook",
            documentation_url="https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm-incidents.html",
            mandatory=False,
            alias="Update Response Plan",
        ),
        ProviderScope(
            name="ssm-incidents:UpdateResponsePlan",
            description="Required to update response plan and register keep as webhook",
            documentation_url="https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm-incidents.html",
            mandatory=False,
            alias="Update Response Plan",
        ),
        ProviderScope(
            name="iam:SimulatePrincipalPolicy",
            description="Allow Keep to test the scopes of the current user/role without modifying any resource.",
            documentation_url="https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm-incidents.html",
            mandatory=False,
            alias="Simulate IAM Policy",
        ),
        ProviderScope(
            name="sns:ListSubscriptionsByTopic",
            description="Required to list all subscriptions of a topic, so Keep will be able to add itself as a subscription.",
            documentation_url="https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm-incidents.html",
            mandatory=False,
            alias="List Subscriptions",
        ),
    ]
    PROVIDER_DISPLAY_NAME = "Incident Manager"

    STATUS_MAP = {
        "OPEN": AlertStatus.FIRING,
        "RESOLVED": AlertStatus.RESOLVED,
    }

    SEVERITIES_MAP = {
        1: AlertSeverity.CRITICAL,
        2: AlertSeverity.HIGH,
        3: AlertSeverity.LOW,
        4: AlertSeverity.WARNING,
        5: AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.aws_client_type = None
        self._client = None

    def validate_scopes(self):
        # init the scopes as False
        scopes = {scope.name: False for scope in self.PROVIDER_SCOPES}
        # the scope name is the action
        actions = scopes.keys()
        # fetch the results

        try:
            sts_client = self.__generate_client("sts")
            identity = sts_client.get_caller_identity()["Arn"]
            iam_client = self.__generate_client("iam")
        except Exception as e:
            self.logger.exception("Error validating AWS IAM scopes")
            scopes = {s: str(e) for s in scopes.keys()}
            return scopes

        # 0. try to validate all scopes using simulate_principal_policy
        #    if the user/role have permissions to simulate_principal_policy, we can validate the scopes easily
        try:
            iam_resp = iam_client.simulate_principal_policy(
                PolicySourceArn=identity, ActionNames=list(actions)
            )
            scopes = {
                res.get("EvalActionName"): res.get("EvalDecision") == "allowed"
                for res in iam_resp.get("EvaluationResults")
            }
            scopes["iam:SimulatePrincipalPolicy"] = True
            if all(scopes.values()):
                self.logger.info(
                    "All AWS IAM scopes are granted!", extra={"scopes": scopes}
                )
                return scopes
            # if not all the scopes are granted, we need to test them one by one
            else:
                self.logger.warning(
                    "Some of the AWS IAM scopes are not granted, testing them one by one...",
                    extra={"scopes": scopes},
                )
        # otherwise, we need to test them one by one
        except Exception:
            self.logger.info("Error validating AWS IAM scopes")
            scopes["iam:SimulatePrincipalPolicy"] = (
                "No permissions to simulate_principal_policy (but its cool, its not a must)"
            )

        self.logger.info("Validating aws incident manager scopes")
        # 1. validate list incident records
        ssm_incident_client = self.__generate_client("ssm-incidents")
        results = None
        try:
            results = ssm_incident_client.list_incident_records()[
                "incidentRecordSummaries"
            ]
            scopes["ssm-incidents:ListIncidentRecords"] = True
        except Exception:
            self.logger.exception(
                "Error starting AWS incident manager list_incident_records query - add ssm-incidents:ListIncidentRecords permissions",
            )
            raise

        if results:
            if len(results) <= 0:
                scopes["ssm-incidents:UpdateIncidentRecord"] = (
                    "We need atleast on incident to test the update scope. Please create an incident manually and try again."
                )
                raise
            try:
                # here using impact , because if we use status it won't be able to be updated again incase of resolved.
                ssm_incident_client.update_incident_record(
                    arn=results[0]["arn"], impact=1
                )

                # restoring impact
                ssm_incident_client.update_incident_record(
                    arn=results[0]["arn"], impact=results[0]["impact"]
                )

                scopes["ssm-incidents:UpdateIncidentRecord"] = True
            except Exception:
                scopes["ssm-incidents:UpdateIncidentRecord"] = (
                    "No permissions to update incidents it seems"
                )
                raise
        # 2 validate if we are already getting user's sns topic and able to fetch sns from aws, not mandatory though
        try:
            sns_topic = self.authentication_config.sns_topic_arn
            if not sns_topic.startswith("arn:aws:sns"):
                account_id = self._get_account_id()
                sns_topic = f"arn:aws:sns:{self.authentication_config.region}:{account_id}:{self.authentication_config.sns_topic_arn}"

            scopes["sns:ListSubscriptionsByTopic"] = True
        except Exception as e:
            self.logger.exception(
                "Error validating AWS sns:ListSubscriptionsByTopic scope"
            )
            scopes["sns:ListSubscriptionsByTopic"] = str(e)

        # 3 validate get response plan
        response_plan = None
        try:
            response_plan = ssm_incident_client.get_response_plan(
                arn=self.authentication_config.response_plan_arn
            )
            scopes["ssm-incidents:GetResponsePlan"] = True
        except Exception:
            scopes["ssm-incidents:GetResponsePlan"] = (
                "No permissions to get response plan"
            )
            raise

        # 4 validate update response plan
        try:
            if not response_plan:
                raise Exception("No response plan found")
            ssm_incident_client.update_response_plan(
                arn=self.authentication_config.response_plan_arn, displayName="test"
            )
            ssm_incident_client.update_response_plan(
                arn=self.authentication_config.response_plan_arn,
                displayName=response_plan["displayName"],
            )
            scopes["ssm-incidents:UpdateResponsePlan"] = True
        except Exception:
            scopes["ssm-incidents:UpdateResponsePlan"] = (
                "No permissions to update response plan"
            )
            raise

        return scopes

    @property
    def client(self):
        if self._client is None:
            self.client = self.__generate_client(self.aws_client_type)
        return self._client

    def _get_alerts(self) -> list[AlertDto]:
        all_alerts = []
        for alert in self._query():
            all_alerts.append(self._format_alert(alert, self))
        return all_alerts

    def _query(self, **kwargs: dict) -> dict:

        ssm_incident_client = self.__generate_client("ssm-incidents")
        all_records = []
        try:
            all_records.extend(
                ssm_incident_client.list_incident_records()["incidentRecordSummaries"]
            )
        except Exception:
            self.logger.exception(
                "Error starting AWS incident manager query - add logs:StartQuery permissions",
                extra={"kwargs": kwargs},
            )
            raise
        return all_records

    def _get_account_id(self):
        sts_client = self.__generate_client("sts")
        identity = sts_client.get_caller_identity()
        return identity["Account"]

    def __generate_client(self, aws_client_type: str):
        client = boto3.client(
            aws_client_type,
            aws_access_key_id=self.authentication_config.access_key,
            aws_secret_access_key=self.authentication_config.access_key_secret,
            region_name=self.authentication_config.region,
        )
        return client

    def dispose(self):
        try:
            self.client.close()
        except Exception:
            self.logger.exception("Error closing boto3 connection")

    def validate_config(self):
        self.authentication_config = IncidentmanagerProviderAuthConfig(
            **self.config.authentication
        )

    def add_hook_to_topic(self, topic: str, keep_api_url: str, api_key: str):

        sns_client = self.__generate_client("sns")

        subscriptions = []
        try:
            subscriptions = sns_client.list_subscriptions_by_topic(TopicArn=topic).get(
                "Subscriptions", []
            )

        except Exception:
            self.logger.exception(
                "Error fetching subscriptions for the topic",
                extra={"topic": topic},
            )
            return False

        hostname = urlparse(keep_api_url).hostname
        already_subscribed = any(
            hostname in sub["Endpoint"]
            and not sub["SubscriptionArn"] == "PendingConfirmation"
            for sub in subscriptions
        )

        if already_subscribed:
            self.logger.info("Already subscribed to topic %s", topic)
            return True

        url_with_api_key = keep_api_url.replace(
            "https://", f"https://api_key:{api_key}@"
        )
        # print(url_with_api_key)
        self.logger.info("Subscribing to topic %s...", topic)
        sns_client.subscribe(
            TopicArn=topic,
            Protocol="https",
            Endpoint=url_with_api_key,
        )
        self.logger.info("Subscribed to topic %s!", topic)
        return True

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        """
        Steps:
            1. Query the response plan
            2. Add/Update given sns topic to add keep's webhook
        """

        if not self.authentication_config.response_plan_arn:
            self.logger.warning(
                "No default response plan name provided, skipping webhook setup"
            )
            return

        ssm_incident_client = self.__generate_client("ssm-incidents")

        response_plan = ssm_incident_client.get_response_plan(
            arn=self.authentication_config.response_plan_arn
        )
        # print(response_plan)

        if self.authentication_config.sns_topic_arn:
            sns_topic = self.authentication_config.sns_topic_arn

            if not self.authentication_config.sns_topic_arn.startswith("arn:aws:sns"):
                account_id = self._get_account_id()
                sns_topic = f"arn:aws:sns:{self.authentication_config.region}:{account_id}:{self.authentication_config.sns_topic_arn}"

            if "notificationTargets" not in response_plan["incidentTemplate"]:
                ssm_incident_client.update_response_plan(
                    arn=self.authentication_config.response_plan_arn,
                    chatChannel={
                        "chatbotSns": [sns_topic],
                    },
                    incidentTemplateNotificationTargets=[
                        {"snsTopicArn": sns_topic},
                    ],
                )
                response_plan = ssm_incident_client.get_response_plan(
                    arn=self.authentication_config.response_plan_arn
                )

            notification_targets = response_plan["incidentTemplate"][
                "notificationTargets"
            ]
            for topic in notification_targets:
                # print(topic)
                if topic["snsTopicArn"] == sns_topic:
                    result = self.add_hook_to_topic(
                        topic=sns_topic,
                        keep_api_url=keep_api_url,
                        api_key=api_key,
                    )
                    if result:
                        break

        self.logger.info("Webhook setup completed!")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        logger = logging.getLogger(__name__)
        # if its confirmation event, we need to confirm the subscription
        if event.get("Type") == "SubscriptionConfirmation":
            logger.info("Confirming subscription...")
            subscribe_url = event.get("SubscribeURL")
            requests.get(subscribe_url)
            logger.info("Subscription confirmed!")
            # Done
            return

        alert = event

        # Map the status to Keep status
        status = IncidentmanagerProvider.STATUS_MAP.get(
            alert.get("status"), AlertStatus.FIRING
        )
        del alert["status"]
        severity = IncidentmanagerProvider.SEVERITIES_MAP.get(alert.get("IMPACT"), 5)

        return AlertDto(
            id=alert.get("arn", str(uuid4())),
            name=alert.get("title", alert.get("alertname")),
            status=status,
            severity=severity,
            lastReceived=str(alert.get("creationTime")),
            description=alert.get("summary"),
            url=alert.pop("url", alert.get("generatorURL")),
            source=["incidentmanager"],
            **alert,
        )


if __name__ == "__main__":
    config = ProviderConfig(
        authentication={
            "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
            "access_key_secret": os.environ.get("AWS_SECRET_ACCESS_KEY"),
            "region": os.environ.get("AWS_REGION"),
            "response_plan_arn": "arn:aws:ssm-incidents::085059502819:response-plan/ResponseEmail",
            "sns_topic_arn": "arn:aws:sns:ap-south-1:085059502819:Keep",
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    provider = IncidentmanagerProvider(context_manager, "asdasd", config)

    results = provider.validate_scopes()
    print(results)

    # provider.setup_webhook(
    #     tenant_id="keep",
    #     keep_api_url="https://1064-2401-4900-1c0f-ae0f-dbba-8aae-8a51-8d29.ngrok-free.app/alerts/event/incidentmanager",
    #     api_key="localhost",
    # )
    # results = provider.get_alerts()
# print(results)
