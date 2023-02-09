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

    @staticmethod
    def get_provider_neccessary_config(provider_type: str) -> dict:
        """
        Get the provider class from the provider type.

        Args:
            provider (dict): The provider configuration.

        Returns:
            BaseProvider: The provider class.
        """
        module = importlib.import_module(
            f"keep.providers.{provider_type}_provider.{provider_type}_provider"
        )
        try:
            provider_auth_config_class = getattr(
                module, provider_type.title().replace("_", "") + "ProviderAuthConfig"
            )
            return provider_auth_config_class
        except ImportError:
            logging.getLogger(__name__).warning(
                f"Provider {provider_type} does not have a provider auth config class"
            )
            return {}
