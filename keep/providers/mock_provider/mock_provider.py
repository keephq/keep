"""
SlackOutput is a class that implements the BaseOutputProvider interface for Slack messages.
"""
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class MockProvider(BaseProvider):
    def __init__(self, config: ProviderConfig, command: str, command_output: str):
        super().__init__(config)
        self.command = command
        self.command_output = command_output

    def validate_config(self):
        pass

    def query(self, context, **kwargs):
        """This is mock provider that just return the command output.

        Args:
            context (_type_): _description_

        Returns:
            _type_: _description_
        """
        return self.command_output
