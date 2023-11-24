"""
CloudwatchProvider is a class that provides a way to read data from AWS Cloudwatch.
"""

import dataclasses
import datetime
import hashlib
import json
import logging
import os
import random
import time
from urllib.parse import urlparse

import boto3
import pydantic
import requests

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class CloudwatchProviderAuthConfig:
    access_key: str = dataclasses.field(
        metadata={"required": True, "description": "AWS access key", "sensitive": True}
    )
    access_key_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS access key secret",
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
    session_token: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS Session Token",
            "hint": "For temporary credentials. Note that if you connect CloudWatch with temporary credentials, the initial connection will succeed, but when the credentials expired alarms won't be sent to Keep.",
            "sensitive": True,
        },
    )
    cloudwatch_sns_topic: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS Cloudwatch SNS Topic [ARN or name]",
            "hint": "Default SNS Topic to send notifications (Optional since if your alarms already sends notifications to SNS topic, Keep will use the exists SNS topic)",
            "sensitive": False,
        },
    )


class CloudwatchProvider(BaseProvider):
    """Push alarms from AWS Cloudwatch to Keep."""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="cloudwatch:DescribeAlarms",
            description="Required to retrieve information about alarms.",
            documentation_url="https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_DescribeAlarms.html",
            mandatory=True,
            alias="Describe Alarms",
        ),
        ProviderScope(
            name="cloudwatch:PutMetricAlarm",
            description="Required to update information about alarms. This mainly use to add Keep as an SNS action to the alarm.",
            documentation_url="https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_PutMetricAlarm.html",
            mandatory=False,
            alias="Update Alarms",
        ),
        ProviderScope(
            name="sns:ListSubscriptionsByTopic",
            description="Required to list all subscriptions of a topic, so Keep will be able to add itself as a subscription.",
            documentation_url="https://docs.aws.amazon.com/sns/latest/dg/sns-access-policy-language-api-permissions-reference.html",
            mandatory=False,
            alias="List Subscriptions",
        ),
        ProviderScope(
            name="logs:GetQueryResults",
            description="Part of CloudWatchLogsReadOnlyAccess role. Required to retrieve the results of CloudWatch Logs Insights queries.",
            documentation_url="https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_GetQueryResults.html",
            mandatory=False,
            alias="Read Query results",
        ),
        ProviderScope(
            name="logs:StartQuery",
            description="Part of CloudWatchLogsReadOnlyAccess role. Required to start CloudWatch Logs Insights queries.",
            documentation_url="https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_StartQuery.html",
            mandatory=False,
            alias="Start Logs Query",
        ),
        ProviderScope(
            name="iam:SimulatePrincipalPolicy",
            description="Allow Keep to test the scopes of the current user/role without modifying any resource.",
            documentation_url="https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulatePrincipalPolicy.html",
            mandatory=False,
            alias="Simulate IAM Policy",
        ),
    ]

    VALID_ALARM_KEYS = {
        "AlarmName",
        "AlarmDescription",
        "ActionsEnabled",
        "OKActions",
        "AlarmActions",
        "InsufficientDataActions",
        "MetricName",
        "Namespace",
        "Statistic",
        "ExtendedStatistic",
        "Dimensions",
        "Period",
        "Unit",
        "EvaluationPeriods",
        "DatapointsToAlarm",
        "Threshold",
        "ComparisonOperator",
        "TreatMissingData",
        "EvaluateLowSampleCountPercentile",
        "Metrics",
        "Tags",
        "ThresholdMetricId",
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
            return scopes
        # otherwise, we need to test them one by one
        except Exception:
            self.logger.info("Error validating AWS IAM scopes")
            scopes[
                "iam:SimulatePrincipalPolicy"
            ] = "No permissions to simulate_principal_policy (but its cool, its not a must)"

        self.logger.info("Validating aws cloudwatch scopes")
        # 1. validate describe alarms
        cloudwatch_client = self.__generate_client("cloudwatch")
        resp = None
        try:
            resp = cloudwatch_client.describe_alarms()
            scopes["cloudwatch:DescribeAlarms"] = True
        except Exception as e:
            self.logger.exception(
                "Error validating AWS cloudwatch:DescribeAlarms scope"
            )
            scopes["cloudwatch:DescribeAlarms"] = str(e)
        # if we got the response, we can validate the other scopes
        if resp:
            # 2. validate put metric alarm
            try:
                alarms = resp.get("MetricAlarms", [])
                alarm = alarms[0]
                filtered_alarm = {
                    k: v
                    for k, v in alarm.items()
                    if k in CloudwatchProvider.VALID_ALARM_KEYS
                }
                cloudwatch_client.put_metric_alarm(**filtered_alarm)
                scopes["cloudwatch:PutMetricAlarm"] = True
            except Exception as e:
                self.logger.exception(
                    "Error validating AWS cloudwatch:PutMetricAlarm scope"
                )
                scopes["cloudwatch:PutMetricAlarm"] = str(e)
        else:
            scopes[
                "cloudwatch:PutMetricAlarm"
            ] = "cloudwatch:DescribeAlarms scope is not granted, so we cannot validate cloudwatch:PutMetricAlarm scope"
        # 3. validate list subscriptions by topic
        if self.authentication_config.cloudwatch_sns_topic:
            try:
                sns_client = self.__generate_client("sns")
                sns_topic = self.authentication_config.cloudwatch_sns_topic
                if not sns_topic.startswith("arn:aws:sns"):
                    account_id = self._get_account_id()
                    sns_topic = f"arn:aws:sns:{self.authentication_config.region}:{account_id}:{self.authentication_config.cloudwatch_sns_topic}"
                sns_client.list_subscriptions_by_topic(TopicArn=sns_topic)
                scopes["sns:ListSubscriptionsByTopic"] = True
            except Exception as e:
                self.logger.exception(
                    "Error validating AWS sns:ListSubscriptionsByTopic scope"
                )
                scopes["sns:ListSubscriptionsByTopic"] = str(e)
        else:
            scopes[
                "sns:ListSubscriptionsByTopic"
            ] = "cloudwatch_sns_topic is not set, so we cannot validate sns:ListSubscriptionsByTopic scope"

        # 4. validate start query
        logs_client = self.__generate_client("logs")
        try:
            logs_client.start_query(
                logGroupName="keepTest",
                queryString="keepTest",
                startTime=int(
                    (
                        datetime.datetime.today() - datetime.timedelta(hours=24)
                    ).timestamp()
                ),
                endTime=int(datetime.datetime.now().timestamp()),
            )
        except Exception as e:
            # that means that the user/role have the permissions but we've just made up the logGroupName which make sense
            if "ResourceNotFoundException" in str(e):
                self.logger.info("AWS logs:StartQuery scope is not required")
                scopes["logs:StartQuery"] = True
            # other/wise the scope is false
            else:
                self.logger.info("Error validating AWS logs:StartQuery scope")
                scopes["logs:StartQuery"] = str(e)

        # 5. validate get query results
        try:
            query_id = logs_client.describe_queries().get("queries")[0]["queryId"]
        except Exception:
            self.logger.exception("Error validating AWS logs:DescribeQueries scope")
            scopes[
                "logs:GetQueryResults"
            ] = "Could not validate logs:GetQueryResults scope without logs:DescribeQueries, so assuming the scope is not granted."

        if query_id:
            try:
                logs_client.get_query_results(queryId=query_id)
                scopes["logs:GetQueryResults"] = True
            except Exception as e:
                self.logger.exception("Error validating AWS logs:GetQueryResults scope")
                scopes["logs:GetQueryResults"] = str(e)
        # Finally
        return scopes

    @property
    def client(self):
        if self._client is None:
            self.client = self.__generate_client(self.aws_client_type)
        return self._client

    def _query(self, **kwargs: dict) -> dict:
        log_group = kwargs.get("log_group")
        query = kwargs.get("query")
        hours = kwargs.get("hours", 24)
        logs_client = self.__generate_client("logs")
        try:
            start_query_response = logs_client.start_query(
                logGroupName=log_group,
                queryString=query,
                startTime=int(
                    (
                        datetime.datetime.today() - datetime.timedelta(hours=hours)
                    ).timestamp()
                ),
                endTime=int(datetime.datetime.now().timestamp()),
            )
        except Exception:
            self.logger.exception(
                "Error starting AWS cloudwatch query - add logs:StartQuery permissions",
                extra={"kwargs": kwargs},
            )
            raise

        query_id = start_query_response["queryId"]
        response = None

        while response is None or response["status"] == "Running":
            self.logger.debug("Waiting for AWS cloudwatch query to complete...")
            time.sleep(1)
            try:
                response = logs_client.get_query_results(queryId=query_id)
            except Exception:
                # probably no permissions
                self.logger.exception(
                    "Error getting AWS cloudwatch query results - add logs:GetQueryResults permissions",
                    extra={"kwargs": kwargs},
                )
                raise

        results = response.get("results")
        return results

    def _get_account_id(self):
        sts_client = self.__generate_client("sts")
        identity = sts_client.get_caller_identity()
        return identity["Account"]

    def __generate_client(self, aws_client_type: str):
        if self.authentication_config.session_token:
            self.logger.info("Using temporary credentials")
            client = boto3.client(
                aws_client_type,
                aws_access_key_id=self.authentication_config.access_key,
                aws_secret_access_key=self.authentication_config.access_key_secret,
                aws_session_token=self.authentication_config.session_token,
                region_name=self.authentication_config.region,
            )
        else:
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
        self.authentication_config = CloudwatchProviderAuthConfig(
            **self.config.authentication
        )

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        # first, list all Cloudwatch alarms
        self.logger.info("Setting up webhook with url %s", keep_api_url)
        cloudwatch_client = self.__generate_client("cloudwatch")
        sns_client = self.__generate_client("sns")
        resp = cloudwatch_client.describe_alarms()
        alarms = resp.get("MetricAlarms", [])
        alarms.extend(resp.get("CompositeAlarms"))
        subscribed_topics = []
        # for each alarm, we need to iterate the actions topics and subscribe to them
        for alarm in alarms:
            actions = alarm.get("AlarmActions", [])
            # extract only SNS actions
            topics = [action for action in actions if action.startswith("arn:aws:sns")]
            # if we got explicitly SNS topic, add is as an action
            if self.authentication_config.cloudwatch_sns_topic:
                self.logger.warning(
                    "Cannot hook alarm without SNS topic, trying to add SNS action..."
                )
                # add an action to the alarm
                if not self.authentication_config.cloudwatch_sns_topic.startswith(
                    "arn:aws:sns"
                ):
                    account_id = self._get_account_id()
                    sns_topic = f"arn:aws:sns:{self.authentication_config.region}:{account_id}:{self.authentication_config.cloudwatch_sns_topic}"
                else:
                    sns_topic = self.authentication_config.cloudwatch_sns_topic
                actions.append(sns_topic)
                try:
                    alarm["AlarmActions"] = actions
                    # filter out irrelevant files
                    filtered_alarm = {
                        k: v
                        for k, v in alarm.items()
                        if k in CloudwatchProvider.VALID_ALARM_KEYS
                    }
                    cloudwatch_client.put_metric_alarm(**filtered_alarm)
                    # now it should contain the SNS topic
                    topics = [sns_topic]
                except Exception:
                    self.logger.exception(
                        "Error adding SNS action to alarm %s", alarm.get("AlarmName")
                    )
                    continue
                self.logger.info(
                    "SNS action added to alarm %s!", alarm.get("AlarmName")
                )
            for topic in topics:
                # protection against adding ourself more than once to the same topic (can happen if different alarams send to the same topic)
                if topic in subscribed_topics:
                    self.logger.info(
                        "Already subscribed to topic %s in this transaction, skipping...",
                        topic,
                    )
                    continue
                self.logger.info("Checking topic %s...", topic)
                try:
                    subscriptions = sns_client.list_subscriptions_by_topic(
                        TopicArn=topic
                    ).get("Subscriptions", [])
                # this means someone deleted the topic that this alarm sends notification too
                except Exception as exc:
                    self.logger.warning(
                        "Topic %s not found, skipping...", topic, exc_info=exc
                    )
                    continue
                hostname = urlparse(keep_api_url).hostname
                already_subscribed = any(
                    hostname in sub["Endpoint"]
                    and not sub["SubscriptionArn"] == "PendingConfirmation"
                    for sub in subscriptions
                )
                if not already_subscribed:
                    url_with_api_key = keep_api_url.replace(
                        "https://", f"https://api_key:{api_key}@"
                    )
                    self.logger.info("Subscribing to topic %s...", topic)
                    sns_client.subscribe(
                        TopicArn=topic,
                        Protocol="https",
                        Endpoint=url_with_api_key,
                    )
                    self.logger.info("Subscribed to topic %s!", topic)
                    subscribed_topics.append(topic)
                    # we need to subscribe to only one SNS topic per alarm, o/w we will get many duplicates
                    break
                else:
                    self.logger.info(
                        "Already subscribed to topic %s, skipping...", topic
                    )
        self.logger.info("Webhook setup completed!")

    @staticmethod
    def format_alert(event: dict) -> AlertDto:
        logger = logging.getLogger(__name__)
        # if its confirmation event, we need to confirm the subscription
        if event.get("Type") == "SubscriptionConfirmation":
            # TODO - do we want to keep it in the db somehow?
            #        do we want to validate that the tenant id exist?
            logger.info("Confirming subscription...")
            subscribe_url = event.get("SubscribeURL")
            requests.get(subscribe_url)
            logger.info("Subscription confirmed!")
            # Done
            return
        # else, we need to parse the event and create an alert
        try:
            alert = json.loads(event.get("Message"))
        except Exception:
            logger.exception("Error parsing cloudwatch alert", extra={"event": event})
            return
        return AlertDto(
            # there is no unique id in the alarm so let's hash the alarm
            id=hashlib.sha256(event.get("Message").encode()).hexdigest(),
            name=alert.get("AlarmName"),
            status=alert.get("NewStateValue"),
            severity=None,  # AWS Cloudwatch doesn't have severity
            lastReceived=str(
                datetime.datetime.fromisoformat(alert.get("StateChangeTime"))
            ),
            fatigueMeter=random.randint(0, 100),
            description=alert.get("AlarmDescription"),
            source=["cloudwatch"],
            **alert,
        )


if __name__ == "__main__":
    config = ProviderConfig(
        authentication={
            "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
            "access_key_secret": os.environ.get("AWS_SECRET_ACCESS_KEY"),
            "region": os.environ.get("AWS_REGION"),
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    cloudwatch_provider = CloudwatchProvider(context_manager, "cloudwatch", config)

    scopes = cloudwatch_provider.validate_scopes()
    print(scopes)
    results = cloudwatch_provider.query(
        query="fields @timestamp, @message, @logStream, @log | sort @timestamp desc | limit 20",
        log_group="/aws/lambda/helloWorld",
    )
    print(results)
