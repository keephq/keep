"""
The providers factory module.
"""
import importlib
import inspect
import logging
import os
from dataclasses import fields

from keep.api.core.db import get_installed_providers
from keep.api.models.provider import Provider
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

logger = logging.getLogger(__name__)


class ProviderConfigurationException(Exception):
    pass


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
        context_manager: ContextManager,
        provider_id: str,
        provider_type: str,
        provider_config: dict,
        **kwargs,
    ) -> BaseProvider:
        """
        Get the instantiated provider class according to the provider type.

        Args:
            provider (dict): The provider configuration.

        Returns:
            BaseProvider: The provider class.
        """
        provider_class = ProvidersFactory.get_provider_class(provider_type)
        # backward compatibility issues
        # when providers.yaml could have 'type' too
        if "type" in provider_config:
            del provider_config["type"]
        provider_config = ProviderConfig(**provider_config)

        try:
            provider = provider_class(
                context_manager=context_manager,
                provider_id=provider_id,
                config=provider_config,
            )
            return provider
        except TypeError as exc:
            error_message = f"Configuration problem while trying to initialize the provider {provider_id}. Probably missing provider config, please check the provider configuration."
            logging.getLogger(__name__).error(error_message)
            raise ProviderConfigurationException(exc)
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
    def get_all_providers() -> list[Provider]:
        """
        Get all the providers.

        Returns:
            list: All the providers.
        """
        providers = []
        blacklisted_providers = ["base_provider", "mock_provider", "file_provider"]

        for provider_directory in os.listdir(
            os.path.dirname(os.path.abspath(__file__))
        ):
            # skip files that aren't providers
            if not provider_directory.endswith("_provider"):
                continue
            elif provider_directory in blacklisted_providers:
                continue
            # import it
            try:
                module = importlib.import_module(
                    f"keep.providers.{provider_directory}.{provider_directory}"
                )
                provider_auth_config_class = getattr(
                    module,
                    provider_directory.title().replace("_", "") + "AuthConfig",
                    None,
                )
                provider_type = provider_directory.replace("_provider", "")
                provider_class = ProvidersFactory.get_provider_class(provider_type)
                can_setup_webhook = (
                    issubclass(provider_class, BaseProvider)
                    and provider_class.__dict__.get("setup_webhook") is not None
                )
                supports_webhook = (
                    issubclass(provider_class, BaseProvider)
                    and provider_class.__dict__.get("format_alert") is not None
                    and provider_class.__dict__.get("webhook_template") is not None
                )
                can_notify = (
                    issubclass(provider_class, BaseProvider)
                    and provider_class.__dict__.get("_notify") is not None
                )
                notify_params = (
                    None
                    if not can_notify
                    else list(
                        dict(
                            inspect.signature(
                                provider_class.__dict__.get("_notify")
                            ).parameters
                        ).keys()
                    )[1:]
                )
                can_query = (
                    issubclass(provider_class, BaseProvider)
                    and provider_class.__dict__.get("_query") is not None
                )
                query_params = (
                    None
                    if not can_query
                    else list(
                        dict(
                            inspect.signature(
                                provider_class.__dict__.get("_query")
                            ).parameters
                        ).keys()
                    )[1:]
                )
                config = (
                    {
                        field.name: dict(field.metadata)
                        for field in fields(provider_auth_config_class)
                    }
                    if provider_auth_config_class
                    else {}
                )
                provider_description = provider_class.__dict__.get(
                    "provider_description"
                )
                oauth2_url = provider_class.__dict__.get("OAUTH2_URL")
                providers.append(
                    Provider(
                        type=provider_type,
                        config=config,
                        can_notify=can_notify,
                        can_query=can_query,
                        notify_params=notify_params,
                        query_params=query_params,
                        can_setup_webhook=can_setup_webhook,
                        supports_webhook=supports_webhook,
                        provider_description=provider_description,
                        oauth2_url=oauth2_url,
                    )
                )
            except ModuleNotFoundError:
                logger.exception(f"Cannot import provider {provider_directory}")
                continue
        return providers

    @staticmethod
    def get_installed_providers(
        tenant_id: str,
        all_providers: list[Provider] | None = None,
        include_details: bool = True,
    ) -> list[Provider]:
        if all_providers is None:
            all_providers = ProvidersFactory.get_all_providers()

        installed_providers = get_installed_providers(tenant_id)
        providers = []
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        for p in installed_providers:
            provider = next(
                filter(
                    lambda provider: provider.type == p.type,
                    all_providers,
                ),
                None,
            )
            if not provider:
                logger.warning(f"Installed provider {p.type} does not exist anymore?")
                continue
            provider_copy = provider.copy()
            provider_copy.id = p.id
            provider_copy.installed_by = p.installed_by
            provider_copy.installation_time = p.installation_time
            try:
                provider_auth = (
                    secret_manager.read_secret(
                        secret_name=f"{tenant_id}_{p.type}_{p.id}", is_json=True
                    )
                    if include_details
                    else {"name": p.name}
                )
            # Somehow the provider is installed but the secret is missing, probably bug in deletion
            # TODO: solve its root cause
            except Exception:
                logger.exception(
                    f"Could not get provider {provider_copy.id} auth config from secret manager"
                )
                continue
            provider_copy.details = provider_auth
            providers.append(provider_copy)
        return providers
