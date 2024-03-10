"""
SshProvider is a class that provides a way to execute SSH commands and get the output.
"""
import dataclasses
import io

import pydantic
from paramiko import AutoAddPolicy, RSAKey, SSHClient

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class SshProviderAuthConfig:
    """SSH authentication configuration.

    Raises:
        ValueError: pkey and password are both empty

    """

    # TODO: validate hostname because it seems pydantic doesn't have a validator for it
    host: str = dataclasses.field(
        metadata={"required": True, "description": "SSH hostname"}
    )
    user: str = dataclasses.field(
        metadata={"required": True, "description": "SSH user"}
    )
    port: int = dataclasses.field(
        default=22, metadata={"required": False, "description": "SSH port"}
    )
    pkey: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SSH private key",
            "sensitive": True,
        },
    )
    password: str = dataclasses.field(
        default="",
        metadata={"required": False, "description": "SSH password", "sensitive": True},
    )

    @pydantic.root_validator
    def check_password_or_pkey(cls, values):
        password, pkey = values.get("password"), values.get("pkey")
        if password == "" and pkey == "":
            raise ValueError("either password or pkey must be provided")
        return values


class SshProvider(BaseProvider):
    """Enrich alerts with data from SSH."""

    PROVIDER_DISPLAY_NAME = "SSH"

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
    pkey = "-----BEGIN OPENSSH PRIVATE KEY-----\n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\nbAECAw==\n-----END OPENSSH PRIVATE KEY-----"

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
