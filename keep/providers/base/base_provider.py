"""
Base class for all providers.
"""
import abc
import logging

from pydantic.dataclasses import dataclass

from keep.providers.models.provider_config import ProviderConfig


@dataclass
class BaseProvider(metaclass=abc.ABCMeta):
    provider_id: str
    config: ProviderConfig

    def __post_init__(self):
        """
        Initialize a provider.

        Args:
            provider_id (str): The provider id.
            **kwargs: Provider configuration loaded from the provider yaml file.
        """
        # Initalize logger for every provider
        self.logger = logging.getLogger(self.__class__.__name__)
        self.validate_config()
        self.logger.debug(
            "Base provider initalized", extra={"provider": self.__class__.__name__}
        )

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

    def expose(self):
        """Expose parameters that were calculated during query time.

        Each provider can expose parameters that were calculated during query time.
        E.g. parameters that were supplied by the user and were rendered by the provider.

        A concrete example is the "_from" and "to" of the Datadog Provider which are calculated during execution.
        """
        # TODO - implement dynamically using decorators and
        return {}
