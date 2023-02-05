"""
SshProvider is a class that provides a way to execute SSH commands and get the output.
"""
import io

from paramiko import AutoAddPolicy, RSAKey, SSHClient

from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


class SshProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.client = self.__generate_client()

    def __generate_client(self) -> SSHClient:
        """
        Generates a paramiko SSH connection.

        Returns:
            SSHClient: The connection to the SSH server.
        """
        ssh_client = SSHClient()
        ssh_client.set_missing_host_key_policy(AutoAddPolicy())

        host = self.config.authentication.get("host")
        port = self.config.authentication.get("port", 22)
        user = self.config.authentication.get("user")

        private_key = self.config.authentication.get("pkey")
        if private_key:
            # Connect using private key
            private_key_file = io.StringIO(private_key)
            private_key_file.seek(0)
            key = RSAKey.from_private_key(
                private_key_file, self.config.authentication.get("pkey_passphrase")
            )
            ssh_client.connect(host, port, user, pk=key)
        else:
            # Connect using password
            ssh_client.connect(
                host,
                port,
                user,
                self.config.authentication.get("password"),
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

        Raises:
            ProviderConfigException: host is missing in authentication.
            ProviderConfigException: user is missing in authentication.
            ProviderConfigException: private key or password is missing in authentication.
        """
        if "host" not in self.config.authentication:
            raise ProviderConfigException("Missing host in authentication")
        if "user" not in self.config.authentication:
            raise ProviderConfigException("Missing user in authentication")
        if (
            "pkey" not in self.config.authentication
            and "password" not in self.config.authentication
        ):
            raise ProviderConfigException(
                "Missing private key or password in authentication"
            )

    def query(self, query: str, **kwargs: dict):
        """
        Query snowflake using the given query

        Args:
            query (str): command to execute

        Returns:
            list: of the results for the executed command.
        """
        stdin, stdout, stderr = self.client.exec_command(query.format(**kwargs))
        stdout.channel.set_combine_stderr(True)
        return stdout.readlines()


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    user = os.environ.get("SSH_USERNAME")
    password = os.environ.get("SSH_PASSWORD")
    host = os.environ.get("SSH_HOST")

    config = {
        "id": "ssh-demo",
        "authentication": {
            "user": user,
            "password": password,
            "host": host,
        },
    }
    provider = ProvidersFactory.get_provider(
        provider_type="ssh", provider_config=config
    )
    result = provider.query("df -h")
    print(result)
