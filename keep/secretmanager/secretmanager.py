import abc
import logging

from keep.contextmanager.contextmanager import ContextManager


class BaseSecretManager(metaclass=abc.ABCMeta):
    def __init__(self, context_manager: ContextManager, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.context_manager = context_manager

    @abc.abstractmethod
    def read_secret(self, secret_name: str, is_json: bool = False) -> str | dict:
        """
        Read a secret from the secret manager.

        Args:
            secret_name (str): The name of the secret to read.
            is_json (bool): Whether to try and convert to python dictionary or not (json.loads)

        Returns:
            str: The secret value.
        """
        raise NotImplementedError(
            "read_secret() method not implemented"
            " for {}".format(self.__class__.__name__)
        )

    @abc.abstractmethod
    def write_secret(self, secret_name: str, secret_value: str) -> None:
        """
        Write a secret to the secret manager.

        Args:
            secret_name (str): The name of the secret to write.
            secret_value (str): The value of the secret to write.
        """

    @abc.abstractmethod
    def delete_secret(self, secret_name: str) -> None:
        """
        Delete a secret from the secret manager.

        Args:
            secret_name (str): The name of the secret to delete.
        """
        raise NotImplementedError("delete_secret() method not implemented")
