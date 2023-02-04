"""
Base class for input providers.
"""
import abc

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class BaseInputProvider(BaseProvider, metaclass=abc.ABCMeta):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.logger.info(
            "Provider initialized",
            extra={"provider": self.__class__.__name__},
        )

    @abc.abstractmethod
    def query(self, query: str, **context: dict):
        """
        Query the provider using the given query

        Args:
            query (str): _description_

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("output() method not implemented")
