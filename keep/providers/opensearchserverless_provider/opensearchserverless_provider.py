"""
OpensearchProvider is a class that provides a way to read data from AWS Opensearch.
"""

import dataclasses
import datetime
import hashlib
import json
import logging
import os
import time
import typing
from typing import List
from urllib.parse import urlparse, urljoin, urlencode

import boto3
import pydantic
import requests

from keep.api.core.config import config as keep_config
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
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
            name="aoss:ReadDocument",
            description="Required to retrieve information about alarms.",
            documentation_url="https://docs.aws.amazon.com/Amazonopensearch/latest/APIReference/API_DescribeAlarms.html",
            mandatory=True,
            alias="Describe Alarms",
        ),
        ProviderScope(
            name="aoss:WriteDocument",
            description="Required to retrieve information about alarms.",
            documentation_url="https://docs.aws.amazon.com/Amazonopensearch/latest/APIReference/API_DescribeAlarms.html",
            mandatory=True,
            alias="Describe Alarms",
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

    def validate_scopes(self):
        scopes = {scope.name: False for scope in self.PROVIDER_SCOPES}
        test_index = "keep-validation-index"
        test_doc_id = "keep-test-doc"
        test_doc = {"message": "Keep test doc"}

        # Validate Write
        try:
            res = self.__create_doc(test_index, test_doc_id, test_doc)
            if res.status_code in [200, 201]:
                scopes["aoss:WriteDocument"] = True
                self.logger.info("Write permission validated successfully.")

                # Clean up
                delete_res = self.__delete_doc(test_index, test_doc_id)
                if delete_res.status_code not in [200, 202]:
                    self.logger.error(f"Failed to delete test doc: {delete_res.status_code} - {delete_res.text}")
            elif res.status_code == 403:
                self.logger.error("No permission for aoss:WriteDocument")
            else:
                self.logger.error(f"Unexpected response while testing write: {res.status_code}, {res.text}")
        except Exception as e:
            self.logger.error("Error while testing aoss:WriteDocument", extra={"exception": str(e)})

        # Validate Read
        try:
            res = self.__get_doc(test_index, test_doc_id)
            if res.status_code == 403:
                self.logger.error("No permission for aoss:ReadDocument")
            else:
                scopes["aoss:ReadDocument"] = True
                self.logger.info("Read permission validated successfully.")
        except Exception as e:
            self.logger.error("Error while testing aoss:ReadDocument", extra={"exception": str(e)})

        return scopes

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = OpensearchProviderAuthConfig(
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
            response = requests.get(url, headers=self.__get_headers, auth=self.__get_auth)
            return response
        except Exception as e:
            self.logger.error("Error while getting document", extra={"exception": str(e)})
            raise

    def __create_doc(self, index, doc_id, doc):
        url = self.__get_url([index, "_doc", doc_id])
        try:
            response = requests.put(url, headers=self.__get_headers, auth=self.__get_auth, json=doc)
            return response
        except Exception as e:
            self.logger.error("Error while creating document", extra={"exception": str(e)})
            raise

    def __delete_doc(self, index, doc_id):
        url = self.__get_url([index, "_doc", doc_id])
        try:
            response = requests.delete(url, headers=self.__get_headers, auth=self.__get_auth)
            return response
        except Exception as e:
            self.logger.error("Error while deleting document", extra={"exception": str(e)})
            raise

    def _query(self, query: dict, index: str):
        try:
            response = requests.get(self.__get_url([index, "_search"]), json=query, headers=self.__get_headers, auth=self.__get_auth)
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
                raise Exception(f"Failed to notify. Status: {res.status_code}, Response: {res.text}")
            self.logger.info("Notification document sent to OpenSearch successfully.")
            return res.json()
        except Exception as e:
            self.logger.error("Error while sending notification to OpenSearch", extra={"exception": str(e)})
            raise
