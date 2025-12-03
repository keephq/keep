import dataclasses
import json
import typing

import pydantic
from opensearchpy import OpenSearch

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_connection_failed import ProviderConnectionFailed
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class OpensearchProviderAuthConfig:
    host: str = dataclasses.field(
        default=None,
        metadata={
            "required": True,
            "description": "OpenSearch host",
            "sensitive": False,
        },
    )
    port: str = dataclasses.field(
        default=9200,
        metadata={
            "required": True,
            "description": "OpenSearch port",
            "sensitive": False,
        },
    )
    username: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "description": "OpenSearch username",
            "config_sub_group": "username_password",
            "config_main_group": "authentication",
            "sensitive": False,
        },
    )
    password: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "description": "OpenSearch password",
            "config_sub_group": "username_password",
            "config_main_group": "authentication",
            "sensitive": True,
        },
    )
    use_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "description": "Enable SSL",
            "type": "switch",
            "config_main_group": "authentication",
        },
    )
    verify_certs: bool = dataclasses.field(
        default=True,
        metadata={
            "description": "Enable SSL certificate verification",
            "type": "switch",
            "config_main_group": "authentication",
        },
    )
    ca_certs: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "description": "CA bundle path (PEM) for HTTPS connections",
            "config_main_group": "authentication",
            "config_sub_group": "ssl",
            "placeholder": "/path/to/ca.pem",
        },
    )


class OpensearchProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "OpenSearch"
    PROVIDER_CATEGORY = ["Database", "Observability"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connect_to_server",
            description="The user can connect to the server",
            mandatory=True,
            alias="Connect to the server",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._client: OpenSearch | None = None

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = OpensearchProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        try:
            self.client.ping()
            scopes = {
                "connect_to_server": True,
            }
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {
                "connect_to_server": str(e),
            }
        return scopes

    @property
    def client(self) -> OpenSearch:
        if not self._client:
            self._client = self.__initialize_client()
        return self._client

    def __initialize_client(self) -> OpenSearch:
        scheme = "https" if self.authentication_config.use_ssl else "http"
        auth = None
        if self.authentication_config.username:
            auth = (
                self.authentication_config.username,
                self.authentication_config.password,
            )
        client = OpenSearch(
            hosts=[
                {
                    "host": self.authentication_config.host,
                    "port": self.authentication_config.port,
                    "scheme": scheme,
                }
            ],
            http_auth=auth,
            use_ssl=self.authentication_config.use_ssl,
            verify_certs=self.authentication_config.verify_certs,
            ca_certs=self.authentication_config.ca_certs,
        )
        try:
            client.info()
        except Exception as e:
            raise ProviderConnectionFailed(f"Failed to connect to OpenSearch: {str(e)}")
        return client

    def _query(self, query: dict | str, index: str, size: int | None = None, **kwargs):
        if not index:
            raise ProviderException("Missing index for OpenSearch query")
        body = query
        if isinstance(body, str):
            body = json.loads(body)
        if size is not None:
            if not isinstance(body, dict):
                raise ProviderException("Query must be an object when specifying size")
            body = dict(body)
            body["size"] = size
        response = self.client.search(index=index, body=body)
        hits = response.get("hits", {}).get("hits")
        return hits or []

    def _notify(
        self,
        index: str,
        document: dict | str,
        doc_id: str | None = None,
        refresh: bool | str | None = None,
        **kwargs,
    ):
        if not index:
            raise ProviderException("Missing index for OpenSearch document")
        if document is None:
            raise ProviderException("Missing document for OpenSearch")
        body = document
        if isinstance(body, str):
            body = json.loads(body)
        params: dict[str, typing.Any] = {
            "index": index,
            "body": body,
        }
        if doc_id:
            params["id"] = doc_id
        if refresh is not None:
            params["refresh"] = refresh
        return self.client.index(**params)

    def get_provider_metadata(self) -> dict:
        try:
            info = self.client.info()
            version = info.get("version", {}).get("number")
            return {"version": version} if version else {"version": "unknown"}
        except Exception:
            self.logger.exception("Failed to get OpenSearch metadata")
            return {}
