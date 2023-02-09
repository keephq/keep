"""
The providers factory module.
"""
import importlib
import logging

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class ProvidersFactory:
    @staticmethod
    def get_provider(
        provider_type: str, provider_config: dict, **kwargs
    ) -> BaseProvider:
        """
        Get the instantiated provider class according to the provider type.

        Args:
            provider (dict): The provider configuration.

        Returns:
            BaseProvider: The provider class.
        """
        provider_config = ProviderConfig(**provider_config)
        module = importlib.import_module(
            f"keep.providers.{provider_type}_provider.{provider_type}_provider"
        )
        provider_class = getattr(
            module, provider_type.title().replace("_", "") + "Provider"
        )
        return provider_class(config=provider_config)
