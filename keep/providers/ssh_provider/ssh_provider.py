"""
SshProvider is a class that provides a way to execute SSH commands and get the output.
"""

import dataclasses
import io
import typing

import pydantic
from paramiko import AutoAddPolicy, RSAKey, SSHClient

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory
from keep.validation.fields import NoSchemeUrl, UrlPort


@pydantic.dataclasses.dataclass
class SshProviderAuthConfig:
    """SSH authentication configuration."""

    host: NoSchemeUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SSH hostname",
            "validation": "no_scheme_url",
        }
    )
    user: str = dataclasses.field(
        metadata={"required": True, "description": "SSH user"}
    )
    port: UrlPort = dataclasses.field(
        default=22,
        metadata={"required": False, "description": "SSH port", "validation": "port"},
    )
    pkey: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "description": "SSH private key",
            "sensitive": True,
            "type": "file",
            "name": "pkey",
            "file_type": "text/plain, application/x-pem-file, application/x-putty-private-key, "
            + "application/x-ed25519-key, application/pkcs8, application/octet-stream",
            "config_sub_group": "private_key",
            "config_main_group": "authentication",
        },
    )
    password: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "description": "SSH password",
            "sensitive": True,
            "config_sub_group": "password",
            "config_main_group": "authentication",
        },
    )

    @pydantic.root_validator
    def check_password_or_pkey(cls, values):
        password, pkey = values.get("password"), values.get("pkey")
        if password is None and pkey is None:
            raise ValueError("either password or private key must be provided")
        return values


class SshProvider(BaseProvider):
    """Enrich alerts with data from SSH."""

    PROVIDER_DISPLAY_NAME = "SSH"
    PROVIDER_CATEGORY = ["Cloud Infrastructure", "Developer Tools"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="ssh_access",
            description="The provided credentials grant access to the SSH server",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = self.__generate_client()
        return self._client

    def __generate_client(self) -> SSHClient:
        """
        Generates a paramiko SSH connection.

        Returns:
            SSHClient: The connection to the SSH server.
        """
        ssh_client = SSHClient()
        ssh_client.set_missing_host_key_policy(AutoAddPolicy())

        host = self.authentication_config.host
        port = self.authentication_config.port
        user = self.authentication_config.user

        private_key = self.authentication_config.pkey
        if private_key:
            # Connect using private key
            private_key_file = io.StringIO(private_key)
            private_key_file.seek(0)
            key = RSAKey.from_private_key(
                private_key_file, self.config.authentication.get("pkey_passphrase")
            )
            ssh_client.connect(host, port, user, pkey=key)
        else:
            # Connect using password
            ssh_client.connect(
                host,
                port,
                user,
                self.authentication_config.password,
            )

        return ssh_client

    def dispose(self):
        """
        Closes the SSH connection.
        """
        try:
            self.client.close()
        except Exception as e:
            self.logger.error("Error closing SSH connection", extra={"error": str(e)})

    def validate_config(self):
        """
        Validates required configuration for SSH provider.

        """
        self.authentication_config = SshProviderAuthConfig(**self.config.authentication)

    def validate_scopes(self):
        """
        Validate the scopes of the provider
        """
        try:
            if self.client.get_transport().is_authenticated():
                return {"ssh_access": True}
        except Exception:
            self.logger.exception("Error validating scopes")
        return {"ssh_access": "Authentication failed"}

    def _query(self, command: str, **kwargs: dict):
        """
        Query snowflake using the given query

        Args:
            query (str): command to execute

        Returns:
            list: of the results for the executed command.
        """
        stdin, stdout, stderr = self.client.exec_command(command.format(**kwargs))
        stdout.channel.set_combine_stderr(True)
        return stdout.readlines()


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

    user = os.environ.get("SSH_USERNAME") or "root"
    password = os.environ.get("SSH_PASSWORD")
    host = os.environ.get("SSH_HOST") or "1.1.1.1"
    pkey = os.environ.get("SSH_PRIVATE_KEY")
    config = {
        "authentication": {
            "user": user,
            "pkey": pkey,
            "host": host,
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager, provider_id="ssh", provider_type="ssh", provider_config=config
    )
    result = provider.query(command="df -h")
    print(result)
