"""
The providers factory module.
"""
import importlib
import logging
import os
from dataclasses import fields

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class ProvidersFactory:
    @staticmethod
    def get_provider_class(provider_type: str) -> BaseProvider:
        provider_type_split = provider_type.split(
            "."
        )  # e.g. "cloudwatch.logs" or "cloudwatch.metrics"
        actual_provider_type = provider_type_split[
            0
        ]  # provider type is always the first part

        module = importlib.import_module(
            f"keep.providers.{actual_provider_type}_provider.{actual_provider_type}_provider"
        )

        # If the provider type doesn't include a sub-type, e.g. "cloudwatch.logs"
        if len(provider_type_split) == 1:
            provider_class = getattr(
                module, actual_provider_type.title().replace("_", "") + "Provider"
            )
        # If the provider type includes a sub-type, e.g. "cloudwatch.metrics"
        else:
            provider_class = getattr(
                module,
                actual_provider_type.title().replace("_", "")
                + provider_type_split[1].title().replace("_", "")
                + "Provider",
            )
        return provider_class

    @staticmethod
    def get_provider(
        provider_id: str, provider_type: str, provider_config: dict, **kwargs
    ) -> BaseProvider:
        """
        Get the instantiated provider class according to the provider type.

        Args:
            provider (dict): The provider configuration.

        Returns:
            BaseProvider: The provider class.
        """
        provider_class = ProvidersFactory.get_provider_class(provider_type)
        provider_config = ProviderConfig(**provider_config)

        try:
            return provider_class(provider_id=provider_id, config=provider_config)
        except TypeError as exc:
            error_message = f"Configuration problem while trying to initialize the provider {provider_id}. Probably missing provider config, please check the provider configuration."
            logging.getLogger(__name__).error(error_message)
            raise exc
        except Exception as exc:
            raise exc

    @staticmethod
    def get_provider_required_config(provider_type: str) -> dict:
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

    @staticmethod
    def get_all_providers() -> list:
        """
        Get all the providers.

        Returns:
            list: All the providers.
        """
        providers = {}
        blacklisted_providers = ["base_provider", "mock_provider", "file_provider"]
        for provider in os.listdir("keep/providers"):
            # skip files that aren't providers
            if not provider.endswith("_provider"):
                continue
            elif provider in blacklisted_providers:
                continue
            # import it
            module = importlib.import_module(f"keep.providers.{provider}.{provider}")
            try:
                provider_auth_config_class = getattr(
                    module, provider.title().replace("_", "") + "AuthConfig"
                )
                providers[provider] = {
                    "config": {
                        field.name: dict(field.metadata)
                        for field in fields(provider_auth_config_class)
                    },
                }
            except (ImportError, AttributeError):
                logging.getLogger(__name__).warning(
                    f"Provider {provider} does not have a provider auth config class"
                )
                # continue to the next provider
                providers[provider] = {"config": None}
        return providers
