"""
Base class for all providers.
"""
import abc
import logging

from keep.providers.models.provider_config import ProviderConfig


class BaseProvider(metaclass=abc.ABCMeta):
    def __init__(self, provider_id: str, config: ProviderConfig):
        """
        Initialize a provider.

        Args:
            provider_id (str): The provider id.
            **kwargs: Provider configuration loaded from the provider yaml file.
        """
        # Initalize logger for every provider
        self.logger = logging.getLogger(self.__class__.__name__)
        self.id = provider_id
        self.config = config
        self.validate_config()
        self.logger.debug(
            "Base provider initalized", extra={"provider": self.__class__.__name__}
        )

    @property
    def provider_id(self) -> str:
        """
        Get the provider id.

        Returns:
            str: The provider id.
        """
        return self.id

    @abc.abstractmethod
    def dispose(self):
        """
        Dispose of the provider.
        """
        raise NotImplementedError("dispose() method not implemented")

    @abc.abstractmethod
    def validate_config():
        """
        Validate provider configuration.
        """
        raise NotImplementedError("validate_config() method not implemented")

    def notify(self, **kwargs):
        """
        Output alert message.

        Args:
            **kwargs (dict): The provider context (with statement)
        """
        raise NotImplementedError("notify() method not implemented")

    def query(self, **kwargs: dict):
        """
        Query the provider using the given query

        Args:
            kwargs (dict): The provider context (with statement)

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("query() method not implemented")
