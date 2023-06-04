"""
Base class for all providers.
"""
import abc
import logging
from typing import Optional

from pydantic.dataclasses import dataclass

from keep.contextmanager.contextmanager import ContextManager
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
        self.context_manager = ContextManager.get_instance()
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

    def _query(self, **kwargs: dict):
        """
        Query the provider using the given query

        Args:
            kwargs (dict): The provider context (with statement)

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("query() method not implemented")

    def query(self, **kwargs: dict):
        # just run the query
        results = self._query(**kwargs)
        # now add the type of the results to the global context
        if results and type(results) == list:
            self.context_manager.dependencies.add(results[0].__class__)
        elif results:
            self.context_manager.dependencies.add(results.__class__)
        # and return the results
        return results

    def get_alerts(self, alert_id: Optional[str] = None):
        """
        Get alerts from the provider.

        Args:
            alert_id (Optional[str], optional): If given, gets a specific alert by id. Defaults to None.
        """
        # todo: we'd want to have a common alert model for all providers (also for consistent output from GPT)
        raise NotImplementedError("get_alerts() method not implemented")

    def deploy_alert(self, alert: dict, alert_id: Optional[str] = None):
        """
        Deploy an alert to the provider.

        Args:
            alert (dict): The alert to deploy.
            alert_id (Optional[str], optional): If given, deploys a specific alert by id. Defaults to None.
        """
        raise NotImplementedError("deploy_alert() method not implemented")

    @staticmethod
    def get_alert_schema() -> dict:
        """
        Get the alert schema description for the provider.
            e.g. How to define an alert for the provider that can be pushed via the API.

        Returns:
            str: The alert format description.
        """
        raise NotImplementedError(
            "get_alert_format_description() method not implemented"
        )

    def get_logs(self, limit: int = 5) -> list:
        """
        Get logs from the provider.

        Args:
            limit (int): The number of logs to get.
        """
        raise NotImplementedError("get_logs() method not implemented")

    def expose(self):
        """Expose parameters that were calculated during query time.

        Each provider can expose parameters that were calculated during query time.
        E.g. parameters that were supplied by the user and were rendered by the provider.

        A concrete example is the "_from" and "to" of the Datadog Provider which are calculated during execution.
        """
        # TODO - implement dynamically using decorators and
        return {}
