"""
The providers factory module.
"""

import copy
import datetime
import importlib
import inspect
import json
import logging
import os
import types
import typing
from dataclasses import fields
from typing import get_args

from keep.api.core.config import config
from keep.api.core.db import (
    get_consumer_providers,
    get_installed_providers,
    get_linked_providers,
)
from keep.api.models.alert import DeduplicationRuleDto
from keep.api.models.provider import Provider
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import (
    BaseIncidentProvider,
    BaseProvider,
    BaseTopologyProvider,
)
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.models.provider_method import ProviderMethodDTO, ProviderMethodParam
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

PROVIDERS_CACHE_FILE = os.environ.get("PROVIDERS_CACHE_FILE", "providers_cache.json")
READ_ONLY_MODE = config("KEEP_READ_ONLY", default="false") == "true"

logger = logging.getLogger(__name__)


class ProviderConfigurationException(Exception):
    pass


class ProvidersFactory:
    _loaded_providers_cache = None
    _loaded_deduplication_rules_cache = None

    @staticmethod
    def get_provider_class(
        provider_type: str,
    ) -> BaseProvider | BaseTopologyProvider | BaseIncidentProvider:
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
    ) -> BaseProvider | BaseTopologyProvider | BaseIncidentProvider:
        """
        Get the instantiated provider class according to the provider type.

        Args:
            provider (dict): The provider configuration.

        Returns:
            BaseProvider: The provider class.
        """
        provider_class = ProvidersFactory.get_provider_class(provider_type)
        # we keep a copy of the auth config so we can check if the provider has changed it and we need to update it
        #   an example for that is the Datadog provider that uses OAuth and needs to save the fresh new refresh token.
        provider_config_copy = copy.deepcopy(provider_config)
        provider_config: ProviderConfig = ProviderConfig(**provider_config)

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
        finally:
            # if the provider has changed the auth config, we need to update it, even if the provider failed to initialize
            if (
                provider_config_copy.get("authentication")
                != provider_config.authentication
            ):
                provider_config_copy["authentication"] = provider_config.authentication
                secret_manager = SecretManagerFactory.get_secret_manager(
                    context_manager
                )
                secret_manager.write_secret(
                    secret_name=f"{context_manager.tenant_id}_{provider_type}_{provider_id}",
                    secret_value=json.dumps(provider_config_copy),
                )

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

    def _get_method_param_type(param: inspect.Parameter) -> str:
        """
        Get the type name from a function parameter annotation.
        Handles generic types like Union by returning the first non-NoneType arg.
        Falls back to 'str' if it can't determine the type.

        Args:
            param (inspect.Parameter): The parameter to get the type from.

        Returns:
            str: The type name.

        """
        annotation_type = param.annotation
        if annotation_type is inspect.Parameter.empty:
            # if no annotation, defaults to str
            return "str"

        if isinstance(annotation_type, type):
            # it's a simple type
            return annotation_type.__name__

        annotation_type_origin = typing.get_origin(annotation_type)
        annotation_type_args = typing.get_args(annotation_type)
        if annotation_type_args and annotation_type_origin in [
            typing.Union,
            types.UnionType,
        ]:
            # get the first annotation type argument which type is not NoneType
            arg_type = next(
                item.__name__
                for item in annotation_type_args
                if item.__name__ != "NoneType"
            )
            return arg_type
        else:
            # otherwise fallback to str
            return "str"

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
                        type=ProvidersFactory._get_method_param_type(params[param]),
                        mandatory=mandatory,
                        default=default,
                        expected_values=expected_values,
                    )
                )
            methods.append(ProviderMethodDTO(**method.dict(), func_params=func_params))
        return methods

    @staticmethod
    def get_all_providers(ignore_cache_file: bool = False) -> list[Provider]:
        """
        Get all the providers.

        Returns:
            list: All the providers.
        """
        logger = logging.getLogger(__name__)
        # use the cache if exists
        if ProvidersFactory._loaded_providers_cache:
            logger.debug("Using cached providers")
            return ProvidersFactory._loaded_providers_cache

        if os.path.exists(PROVIDERS_CACHE_FILE) and not ignore_cache_file:
            logger.info(
                "Loading providers from cache file",
                extra={"file": PROVIDERS_CACHE_FILE},
            )
            with open(PROVIDERS_CACHE_FILE, "r") as f:
                providers_cache = json.load(f)
                ProvidersFactory._loaded_providers_cache = [
                    Provider(**provider) for provider in providers_cache
                ]
            logger.info(
                "Providers loaded from cache file",
                extra={"file": PROVIDERS_CACHE_FILE},
            )
            return ProvidersFactory._loaded_providers_cache

        logger.info("Loading providers")
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
                ) or (
                    issubclass(provider_class, BaseIncidentProvider)
                    and provider_class.__dict__.get("setup_incident_webhook")
                    is not None
                )
                webhook_required = provider_class.WEBHOOK_INSTALLATION_REQUIRED
                supports_webhook = (
                    issubclass(provider_class, BaseProvider)
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
                config = {}
                if provider_auth_config_class:
                    for field in fields(provider_auth_config_class):
                        config[field.name] = dict(field.metadata)
                        if field.default is not None:
                            config[field.name]["default"] = field.default
                provider_description = provider_class.__dict__.get(
                    "provider_description"
                )
                oauth2_url = provider_class.__dict__.get("OAUTH2_URL")
                docs = provider_class.__doc__
                can_fetch_topology = issubclass(provider_class, BaseTopologyProvider)
                can_fetch_incidents = issubclass(provider_class, BaseIncidentProvider)

                provider_tags = set(provider_class.PROVIDER_TAGS)
                if can_fetch_topology:
                    provider_tags.add("topology")
                if can_query and "data" not in provider_tags:
                    provider_tags.add("data")
                if (
                    supports_webhook
                    or can_setup_webhook
                    and "alert" not in provider_tags
                ):
                    provider_tags.add("alert")
                if can_notify and "ticketing" not in provider_tags:
                    provider_tags.add("messaging")
                if can_fetch_incidents and "incident" not in provider_tags:
                    provider_tags.add("incident")
                provider_tags = list(provider_tags)

                provider_methods = ProvidersFactory.__get_methods(provider_class)
                # if the provider has a PROVIDER_DISPLAY_NAME, use it, otherwise use the provider type
                provider_display_name = getattr(
                    provider_class,
                    "PROVIDER_DISPLAY_NAME",
                    provider_type,
                )

                # Load alert examples if available
                try:
                    alert_example = provider_class.simulate_alert()
                # not all providers have this method (yet ^^)
                except Exception:
                    alert_example = None

                # Add default fingerprint fields if available
                if hasattr(provider_class, "FINGERPRINT_FIELDS"):
                    default_fingerprint_fields = provider_class.FINGERPRINT_FIELDS
                else:
                    default_fingerprint_fields = []

                providers.append(
                    Provider(
                        type=provider_type,
                        display_name=provider_display_name,
                        config=config,
                        can_notify=can_notify,
                        can_query=can_query,
                        notify_params=notify_params,
                        query_params=query_params,
                        can_setup_webhook=can_setup_webhook,
                        webhook_required=webhook_required,
                        supports_webhook=supports_webhook,
                        provider_description=provider_description,
                        oauth2_url=oauth2_url,
                        scopes=scopes,
                        docs=docs,
                        methods=provider_methods,
                        tags=provider_tags,
                        alertExample=alert_example,
                        default_fingerprint_fields=default_fingerprint_fields,
                        categories=provider_class.PROVIDER_CATEGORY,
                        coming_soon=provider_class.PROVIDER_COMING_SOON,
                    )
                )
            except ModuleNotFoundError:
                logger.error(
                    f"Cannot import provider {provider_directory}, module not found."
                )
                continue
            # for some providers that depends on grpc like cilium provider, this might fail on imports not from Keep (such as the docs script)
            except TypeError:
                logger.warning(
                    f"Cannot import provider {provider_directory}, unexpected error."
                )
                continue

        ProvidersFactory._loaded_providers_cache = providers
        return providers

    @staticmethod
    def get_installed_providers(
        tenant_id: str,
        all_providers: list[Provider] | None = None,
        include_details: bool = True,
        override_readonly: bool = False,
    ) -> list[Provider]:
        if all_providers is None:
            all_providers = ProvidersFactory.get_all_providers()

        installed_providers = get_installed_providers(tenant_id)
        providers = []
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        for p in installed_providers:
            provider: Provider | None = next(
                filter(
                    lambda provider: provider.type == p.type,
                    all_providers,
                ),
                None,
            )
            if provider is None:
                logger.warning(f"Installed provider {p.type} does not exist anymore?")
                continue
            provider_copy = provider.copy()
            provider_copy.id = p.id
            provider_copy.installed_by = p.installed_by
            provider_copy.installation_time = p.installation_time
            provider_copy.last_pull_time = p.last_pull_time
            provider_copy.provisioned = p.provisioned
            provider_copy.pulling_enabled = p.pulling_enabled
            provider_copy.installed = True
            try:
                provider_auth = {"name": p.name}
                if include_details:
                    provider_auth.update(
                        secret_manager.read_secret(
                            secret_name=f"{tenant_id}_{p.type}_{p.id}", is_json=True
                        )
                    )
                if READ_ONLY_MODE and not override_readonly:
                    if "authentication" in provider_auth:
                        provider_auth["authentication"] = {
                            key: "demo"
                            for key in provider_auth["authentication"]
                            if isinstance(provider_auth["authentication"][key], str)
                        }
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
                provider_class = ProvidersFactory.get_installed_provider(
                    tenant_id=provider.tenant_id,
                    provider_id=provider.id,
                    provider_type=provider.type,
                )
                initialized_consumer_providers.append(provider_class)
            except Exception:
                logger.exception(
                    f"Could not get provider {provider.id} auth config from secret manager"
                )
                continue
        return initialized_consumer_providers

    @staticmethod
    def get_provider_config(
        tenant_id: str,
        provider_id: str,
        provider_type: str,
        context_manager: ContextManager | None = None,
    ) -> dict:
        context_manager = context_manager or ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        return secret_manager.read_secret(
            secret_name=f"{tenant_id}_{provider_type}_{provider_id}",
            is_json=True,
        )

    @staticmethod
    def get_installed_provider(
        tenant_id: str, provider_id: str, provider_type: str
    ) -> BaseProvider:
        """
        Get the instantiated provider class according to the provider type.

        Args:
            tenant_id (str): The tenant id.
            provider_id (str): The provider id.
            provider_type (str): The provider type.

        Returns:
            BaseProvider: The instantiated provider class.
        """
        context_manager = ContextManager(tenant_id=tenant_id)
        provider_config = ProvidersFactory.get_provider_config(
            tenant_id=tenant_id,
            provider_id=provider_id,
            provider_type=provider_type,
            context_manager=context_manager,
        )
        provider_class = ProvidersFactory.get_provider(
            context_manager=context_manager,
            provider_id=provider_id,
            provider_type=provider_type,
            provider_config=provider_config,
        )
        return provider_class

    @staticmethod
    def get_linked_providers(tenant_id: str) -> list[Provider]:
        """
        Get the linked providers.

        Args:
            tenant_id (str): The tenant id.

        Returns:
            list: The linked providers.
        """
        linked_providers = get_linked_providers(tenant_id)
        available_providers = ProvidersFactory.get_all_providers()

        _linked_providers = []
        for p in linked_providers:
            provider_type, provider_id, last_alert_received = p[0], p[1], p[2]
            provider: Provider = next(
                filter(
                    lambda provider: provider.type == provider_type,
                    available_providers,
                ),
                None,
            )
            if not provider:
                # It means it's a custom provider
                provider = Provider(
                    display_name=provider_type,
                    type=provider_type,
                    can_notify=False,
                    can_query=False,
                    tags=["alert"],
                )
            provider = provider.copy()
            provider.linked = True
            provider.id = provider_id
            if last_alert_received:
                provider.last_alert_received = last_alert_received.replace(
                    tzinfo=datetime.timezone.utc
                ).isoformat()
            _linked_providers.append(provider)

        return _linked_providers

    @staticmethod
    def get_default_deduplication_rules() -> list[DeduplicationRuleDto]:
        """
        Get the default deduplications for all providers with FINGERPRINT_FIELDS.

        Returns:
            list: The default deduplications for each provider.
        """
        if ProvidersFactory._loaded_deduplication_rules_cache:
            return ProvidersFactory._loaded_deduplication_rules_cache

        default_deduplications = []
        all_providers = ProvidersFactory.get_all_providers()

        for provider in all_providers:
            if provider.default_fingerprint_fields:
                deduplication_dto = DeduplicationRuleDto(
                    name=f"{provider.type}_default",
                    description=f"{provider.display_name} default deduplication rule",
                    default=True,
                    distribution=[{"hour": i, "number": 0} for i in range(24)],
                    provider_type=provider.type,
                    last_updated="",
                    last_updated_by="",
                    created_at="",
                    created_by="",
                    ingested=0,
                    dedup_ratio=0.0,
                    enabled=True,
                    fingerprint_fields=provider.default_fingerprint_fields,
                    # default provider deduplication rules are not full deduplication
                    full_deduplication=False,
                    # not relevant for default deduplication rules
                    ignore_fields=[],
                    is_provisioned=False,
                )
                default_deduplications.append(deduplication_dto)

        ProvidersFactory._loaded_deduplication_rules_cache = default_deduplications
        return default_deduplications
