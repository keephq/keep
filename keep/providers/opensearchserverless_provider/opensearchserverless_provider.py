"""
OpensearchProvider is a class that provides a way to read/add data from AWS Opensearch.
"""

import dataclasses
from typing import List
from urllib.parse import urljoin, urlencode

import boto3
import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from requests_aws4auth import AWS4Auth


@pydantic.dataclasses.dataclass
class OpensearchserverlessProviderAuthConfig:
    domain_endpoint: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Domain endpoint",
            "senstive": False,
        },
    )
    region: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS region",
            "senstive": False,
        },
    )
    access_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": True,
            "description": "AWS access key",
            "sensitive": True,
        },
    )
    access_key_secret: str = dataclasses.field(
        default=None,
        metadata={
            "required": True,
            "description": "AWS access key secret",
            "sensitive": True,
        },
    )


class OpensearchserverlessProvider(BaseProvider, ProviderHealthMixin):
    """Push alarms from AWS Opensearch to Keep."""

    PROVIDER_DISPLAY_NAME = "Opensearch Serverless"
    PROVIDER_CATEGORY = ["Database", "Observability"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="iam:SimulatePrincipalPolicy",
            description="Required to check if we have access to AOSS API.",
            mandatory=True,
            alias="Needed to test the access for next 3 scopes.",
        ),
        ProviderScope(
            name="aoss:APIAccessAll",
            description="Required to make API calls to OpenSearch Serverless. (Add from IAM console)",
            mandatory=True,
            alias="Access to make API calls to serverless",
        ),
        ProviderScope(
            name="aoss:ListAccessPolicies",
            description="Required to access all Data Access Policies. (Add from IAM console)",
            mandatory=True,
            alias="Needed to list all Data Access Policies.",
        ),
        ProviderScope(
            name="aoss:GetAccessPolicy",
            description="Required to check each policy for read and write scope. (Add from IAM console)",
            mandatory=True,
            alias="Policy read access",
        ),
        ProviderScope(
            name="aoss:ReadDocument",
            description="Required to query.",
            documentation_url="https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-genref.html#serverless-operations",
            mandatory=True,
            alias="Read Access",
        ),
        ProviderScope(
            name="aoss:WriteDocument",
            description="Required to save documents.",
            documentation_url="https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-genref.html#serverless-operations",
            mandatory=True,
            alias="Write Access",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        self.auth = None
        self.client = None
        super().__init__(context_manager, provider_id, config)

    def __get_url(self, paths: List[str] = [], query_params: dict = None, **kwargs):
        """
        Helper method to build the url for Opensearch api requests.
        """
        host = self.authentication_config.domain_endpoint.rstrip("/").rstrip()
        self.logger.info(f"Building URL with host: {host}")
        url = urljoin(
            host,
            "/".join(str(path) for path in paths),
        )

        # add query params
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        return url

    def __generate_client(self, aws_client_type: str):
        client = boto3.client(
            aws_client_type,
            aws_access_key_id=self.authentication_config.access_key,
            aws_secret_access_key=self.authentication_config.access_key_secret,
            region_name=self.authentication_config.region,
        )
        return client

    def validate_scopes(self):
        scopes = {
            scope.name: "Access needed to all previous scopes to continue"
            for scope in self.PROVIDER_SCOPES
        }
        actions = scopes.keys()
        try:
            sts_client = self.__generate_client("sts")
            identity = sts_client.get_caller_identity()["Arn"]
            iam_client = self.__generate_client("iam")
            results = iam_client.simulate_principal_policy(
                PolicySourceArn=identity,
                ActionNames=[
                    "aoss:APIAccessAll",
                    "aoss:ListAccessPolicies",
                    "aoss:GetAccessPolicy",
                ],
            )
            scopes["iam:SimulatePrincipalPolicy"] = True
        except Exception as e:
            self.logger.error(e)
            scopes = {s: str(e) for s in scopes.keys()}
            return scopes

        all_allowed = True
        for res in results["EvaluationResults"]:
            if res["EvalActionName"] in actions:
                all_allowed &= res["EvalDecision"] == "allowed"
                scopes[res["EvalActionName"]] = (
                    True
                    if res["EvalDecision"] == "allowed"
                    else f'{res["EvalActionName"]} is not allowed'
                )

        if not all_allowed:
            self.logger.error(
                "We don't have access to scopes needed to validate the rest"
            )
            return scopes

        left_to_validate = ["aoss:ReadDocument", "aoss:WriteDocument"]
        try:
            aoss_client = self.__generate_client("opensearchserverless")
            all_policies = aoss_client.list_access_policies(type="data")
            for policy in all_policies["accessPolicySummaries"]:
                curr_policy = aoss_client.get_access_policy(
                    type="data", name=policy["name"]
                )["accessPolicyDetail"]
                for pol in curr_policy["policy"]:
                    if identity in pol["Principal"]:
                        for rule in pol["Rules"]:
                            if rule["ResourceType"] == "index":
                                for left in left_to_validate:
                                    if left in rule["Permission"]:
                                        scopes[left] = True
                                    else:
                                        scopes[left] = "No Access"

        except Exception as e:
            for left in left_to_validate:
                scopes[left] = str(e)
            return scopes

        return scopes

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = OpensearchserverlessProviderAuthConfig(
            **self.config.authentication
        )

    @property
    def __get_headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @property
    def __get_auth(self):
        if self.auth is None:
            self.auth = AWS4Auth(
                self.authentication_config.access_key,
                self.authentication_config.access_key_secret,
                self.authentication_config.region,
                "aoss",
            )
        return self.auth

    def __get_doc(self, index, doc_id):
        url = self.__get_url([index, "_doc", doc_id])
        try:
            response = requests.get(
                url, headers=self.__get_headers, auth=self.__get_auth
            )
            return response
        except Exception as e:
            self.logger.error(
                "Error while getting document", extra={"exception": str(e)}
            )
            raise

    def __create_doc(self, index, doc_id, doc):
        url = self.__get_url([index, "_doc", doc_id])
        try:
            response = requests.put(
                url, headers=self.__get_headers, auth=self.__get_auth, json=doc
            )
            return response
        except Exception as e:
            self.logger.error(
                "Error while creating document", extra={"exception": str(e)}
            )
            raise

    def __delete_doc(self, index, doc_id):
        url = self.__get_url([index, "_doc", doc_id])
        try:
            response = requests.delete(
                url, headers=self.__get_headers, auth=self.__get_auth
            )
            return response
        except Exception as e:
            self.logger.error(
                "Error while deleting document", extra={"exception": str(e)}
            )
            raise

    def _query(self, query: dict, index: str):
        try:
            response = requests.get(
                self.__get_url([index, "_search"]),
                json=query,
                headers=self.__get_headers,
                auth=self.__get_auth,
            )
            if response.status_code != 200:
                raise Exception(response.text)
            x = response.json()
            return x
        except Exception as e:
            self.logger.error("Error while querying index", extra={"exception": str(e)})
            raise e

    def _notify(self, index: str, document: dict, doc_id: str):
        try:
            res = self.__create_doc(index, doc_id, document)
            if res.status_code not in [200, 201]:
                raise Exception(
                    f"Failed to notify. Status: {res.status_code}, Response: {res.text}"
                )
            self.logger.info("Notification document sent to OpenSearch successfully.")
            return res.json()
        except Exception as e:
            self.logger.error(
                "Error while sending notification to OpenSearch",
                extra={"exception": str(e)},
            )
            raise
