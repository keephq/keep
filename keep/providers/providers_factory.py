"""
The providers factory module.
"""
import importlib
import inspect
import logging
import os
from dataclasses import fields
from typing import get_args

from keep.api.core.db import get_consumer_providers, get_installed_providers
from keep.api.models.provider import Provider
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.models.provider_method import ProviderMethodDTO, ProviderMethodParam
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
        # support for provider types with subtypes e.g. auth0.logs, github.stars
        # todo: if some day there will be different conf for auth0.logs and auth0.users, this will need to be revisited
        if "." in provider_type:
            provider_type = provider_type.split(".")[0]
        module = importlib.import_module(
            f"keep.providers.{provider_type}_provider.{provider_type}_provider"
        )
        try:
            provider_auth_config_class = getattr(
                module, provider_type.title().replace("_", "") + "ProviderAuthConfig"
            )
            return provider_auth_config_class
        except (ImportError, AttributeError):
            logging.getLogger(__name__).warning(
                f"Provider {provider_type} does not have a provider auth config class"
            )
            return {}

    def __get_methods(provider_class: BaseProvider) -> list[ProviderMethodDTO]:
        methods = []
        for method in provider_class.PROVIDER_METHODS:
            params = dict(
                inspect.signature(
                    provider_class.__dict__.get(method.func_name)
                ).parameters
            )
            func_params = []
            for param in params:
                if param == "self":
                    continue
                mandatory = True
                default = None
                if getattr(params[param].default, "__name__", None) != "_empty":
                    mandatory = False
                    default = str(params[param].default)
                expected_values = list(get_args(params[param].annotation))
                func_params.append(
                    ProviderMethodParam(
                        name=param,
                        type=params[param].annotation.__name__,
                        mandatory=mandatory,
                        default=default,
                        expected_values=expected_values,
                    )
                )
            methods.append(ProviderMethodDTO(**method.dict(), func_params=func_params))
        return methods

    @staticmethod
    def get_all_providers() -> list[Provider]:
        """
        Get all the providers.

        Returns:
            list: All the providers.
        """
        providers = []
        blacklisted_providers = [
            "base_provider",
            "mock_provider",
            "file_provider",
            "github_workflows_provider",
        ]

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
                scopes = (
                    provider_class.PROVIDER_SCOPES
                    if issubclass(provider_class, BaseProvider)
                    else []
                )
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
                docs = provider_class.__doc__

                provider_tags = []
                provider_tags.extend(provider_class.PROVIDER_TAGS)
                if can_query and "data" not in provider_tags:
                    provider_tags.append("data")
                if (
                    supports_webhook
                    or can_setup_webhook
                    and "alert" not in provider_tags
                ):
                    provider_tags.append("alert")
                if can_notify and "ticketing" not in provider_tags:
                    provider_tags.append("messaging")

                provider_methods = ProvidersFactory.__get_methods(provider_class)
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
                        scopes=scopes,
                        docs=docs,
                        methods=provider_methods,
                        tags=provider_tags,
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
            provider: Provider = next(
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
                provider_auth = {"name": p.name}
                if include_details:
                    provider_auth.update(
                        secret_manager.read_secret(
                            secret_name=f"{tenant_id}_{p.type}_{p.id}", is_json=True
                        )
                    )
            # Somehow the provider is installed but the secret is missing, probably bug in deletion
            # TODO: solve its root cause
            except Exception:
                logger.exception(
                    f"Could not get provider {provider_copy.id} auth config from secret manager"
                )
                continue
            provider_copy.details = provider_auth
            provider_copy.validatedScopes = p.validatedScopes
            providers.append(provider_copy)
        return providers

    @staticmethod
    def get_consumer_providers() -> list[Provider]:
        # get the list of all providers that consume events
        installed_consumer_providers = get_consumer_providers()
        initialized_consumer_providers = []
        for provider in installed_consumer_providers:
            try:
                context_manager = ContextManager(tenant_id=provider.tenant_id)
                secret_manager = SecretManagerFactory.get_secret_manager(
                    context_manager
                )
                provider_config = secret_manager.read_secret(
                    secret_name=f"{provider.tenant_id}_{provider.type}_{provider.id}",
                    is_json=True,
                )
                provider_class = ProvidersFactory.get_provider(
                    context_manager=context_manager,
                    provider_id=provider.id,
                    provider_type=provider.type,
                    provider_config=provider_config,
                )
                initialized_consumer_providers.append(provider_class)
            except Exception:
                logger.exception(
                    f"Could not get provider {provider.id} auth config from secret manager"
                )
                continue
        return initialized_consumer_providers
