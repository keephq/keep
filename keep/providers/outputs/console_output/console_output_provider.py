"""
Simple Console Output Provider
"""
from keep.providers.base.base_output_provider import BaseOutputProvider
from keep.providers.models.provider_config import ProviderConfig


class ConsoleOutputProvider(BaseOutputProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)

    def validate_config():
        # No configuration to validate, so just do nothing.
        # For example, this could be the place where you validate that the expected keys are present in the configuration.
        # e.g. if "pagerduty_api_key" is not present in self.config.authentication
        pass

    def output(self, alert_message: str, **context: dict):
        """
        Output alert message simply using the print method.

        Args:
            alert_message (str): The alert message to be printed in to the console
        """
        self.logger.debug("Outputting alert message to console")
        print(alert_message.format(**context))
        self.logger.debug("Alert message outputted to console")


if __name__ == "__main__":
    config = ProviderConfig(
        id="console",
        provider_type="console",
        description="Console Output Provider",
        authentication={},
    )
    provider = ConsoleOutputProvider(config=config)
    provider.output("Simple alert showing context with name: {name}", name="John Doe")
