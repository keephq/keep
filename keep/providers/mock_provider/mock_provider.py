"""
MockProvider is a class that implements the BaseOutputProvider interface for Mock messages.
"""
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class MockProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def validate_config(self):
        pass

    def _query(self, **kwargs):
        """This is mock provider that just return the command output.

        Returns:
            _type_: _description_
        """
        return kwargs.get("command_output")

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass
