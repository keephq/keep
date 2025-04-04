import hashlib
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import redis
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from keep.api.alert_deduplicator.deduplication_rules_provisioning import (
    provision_deduplication_rules,
)
from keep.api.consts import REDIS, REDIS_DB, REDIS_HOST, REDIS_PORT
from keep.api.core.config import config
from keep.api.core.db import (
    engine,
    get_all_provisioned_providers,
    get_provider_by_name,
    get_provider_logs,
)
from keep.api.models.db.provider import Provider, ProviderExecutionLog
from keep.api.models.provider import Provider as ProviderModel
from keep.contextmanager.contextmanager import ContextManager
from keep.event_subscriber.event_subscriber import EventSubscriber
from keep.functions import cyaml
from keep.providers.base.base_provider import BaseProvider
from keep.providers.providers_factory import ProvidersFactory
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

DEFAULT_PROVIDER_HASH_STATE_FILE = "/state/{tenant_id}_providers_hash.txt"


logger = logging.getLogger(__name__)


class ProvidersService:
    @staticmethod
    def get_all_providers() -> List[ProviderModel]:
        return ProvidersFactory.get_all_providers()

    @staticmethod
    def get_installed_providers(
        tenant_id: str, include_details: bool = True
    ) -> List[ProviderModel]:
        all_providers = ProvidersService.get_all_providers()
        return ProvidersFactory.get_installed_providers(
            tenant_id, all_providers, include_details
        )

    @staticmethod
    def get_linked_providers(tenant_id: str) -> List[ProviderModel]:
        return ProvidersFactory.get_linked_providers(tenant_id)

    @staticmethod
    def validate_scopes(
        provider: BaseProvider, validate_mandatory=True
    ) -> dict[str, bool | str]:
        logger.info("Validating provider scopes")
        try:
            validated_scopes = provider.validate_scopes()
        except Exception as e:
            logger.exception("Failed to validate provider scopes")
            raise HTTPException(
                status_code=412,
                detail=str(e),
            )
        if validate_mandatory:
            mandatory_scopes_validated = True
            if provider.PROVIDER_SCOPES and validated_scopes:
                # All of the mandatory scopes must be validated
                for scope in provider.PROVIDER_SCOPES:
                    if scope.mandatory and (
                        scope.name not in validated_scopes
                        or validated_scopes[scope.name] is not True
                    ):
                        mandatory_scopes_validated = False
                        break
            # Otherwise we fail the installation
            if not mandatory_scopes_validated:
                logger.warning(
                    "Failed to validate mandatory provider scopes",
                    extra={"validated_scopes": validated_scopes},
                )
                raise HTTPException(
                    status_code=412,
                    detail=validated_scopes,
                )
        logger.info(
            "Validated provider scopes", extra={"validated_scopes": validated_scopes}
        )
        return validated_scopes

    @staticmethod
    def prepare_provider(
        provider_id: str,
        provider_name: str,
        provider_type: str,
        provider_config: Dict[str, Any],
        validate_scopes: bool = True,
    ) -> Dict[str, Any]:
        provider_unique_id = uuid.uuid4().hex
        logger.info(
            "Installing provider",
            extra={
                "provider_id": provider_id,
                "provider_type": provider_type,
            },
        )

        config = {
            "authentication": provider_config,
            "name": provider_name,
        }
        tenant_id = None
        context_manager = ContextManager(tenant_id=tenant_id)
        try:
            provider = ProvidersFactory.get_provider(
                context_manager, provider_id, provider_type, config
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        if validate_scopes:
            ProvidersService.validate_scopes(provider)

        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        secret_name = f"{tenant_id}_{provider_type}_{provider_unique_id}"
        secret_manager.write_secret(
            secret_name=secret_name,
            secret_value=json.dumps(config),
        )

        try:
            secret_manager.delete_secret(
                secret_name=secret_name,
            )
            logger.warning("Secret deleted")
        except Exception:
            logger.exception("Failed to delete the secret")
            pass

        return provider

    @staticmethod
    def install_provider(
        tenant_id: str,
        installed_by: str,
        provider_id: str,
        provider_name: str,
        provider_type: str,
        provider_config: Dict[str, Any],
        provisioned: bool = False,
        validate_scopes: bool = True,
        pulling_enabled: bool = True,
        session: Optional[Session] = None,
        commit: bool = True,
    ) -> Dict[str, Any]:
        provider_unique_id = uuid.uuid4().hex
        logger.info(
            "Installing provider",
            extra={
                "provider_id": provider_id,
                "provider_type": provider_type,
                "tenant_id": tenant_id,
            },
        )

        config = {
            "authentication": provider_config,
            "name": provider_name,
        }

        context_manager = ContextManager(tenant_id=tenant_id)
        try:
            provider = ProvidersFactory.get_provider(
                context_manager, provider_id, provider_type, config
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        if validate_scopes:
            validated_scopes = ProvidersService.validate_scopes(provider)
        else:
            validated_scopes = {}

        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        secret_name = f"{tenant_id}_{provider_type}_{provider_unique_id}"
        secret_manager.write_secret(
            secret_name=secret_name,
            secret_value=json.dumps(config),
        )

        session_managed = False
        if not session:
            session = Session(engine)
            session_managed = True

        provider_model = Provider(
            id=provider_unique_id,
            tenant_id=tenant_id,
            name=provider_name,
            type=provider_type,
            installed_by=installed_by,
            installation_time=time.time(),
            configuration_key=secret_name,
            validatedScopes=validated_scopes,
            consumer=provider.is_consumer,
            provisioned=provisioned,
            pulling_enabled=pulling_enabled,
        )
        try:
            session.add(provider_model)
            if commit:
                session.commit()
        except IntegrityError as e:
            if "FOREIGN KEY constraint" in str(e):
                raise
            try:
                # if the provider is already installed, delete the secret
                logger.warning(
                    "Provider already installed, deleting secret",
                    extra={"error": str(e)},
                )
                secret_manager.delete_secret(
                    secret_name=secret_name,
                )
                logger.warning("Secret deleted")
            except Exception:
                logger.exception("Failed to delete the secret")
                pass
            raise HTTPException(status_code=409, detail="Provider already installed")
        finally:
            if session_managed:
                session.close()

        if provider_model.consumer:
            try:
                event_subscriber = EventSubscriber.get_instance()
                event_subscriber.add_consumer(provider)
            except Exception:
                logger.exception("Failed to register provider as a consumer")

        return {
            "provider": provider_model,
            "type": provider_type,
            "id": provider_unique_id,
            "details": config,
            "validatedScopes": validated_scopes,
        }

    @staticmethod
    def update_provider(
        tenant_id: str,
        provider_id: str,
        provider_info: Dict[str, Any],
        updated_by: str,
        session: Session,
    ) -> Dict[str, Any]:
        provider = session.exec(
            select(Provider).where(
                (Provider.tenant_id == tenant_id) & (Provider.id == provider_id)
            )
        ).one_or_none()

        if not provider:
            raise HTTPException(404, detail="Provider not found")

        if provider.provisioned:
            raise HTTPException(403, detail="Cannot update a provisioned provider")

        pulling_enabled = provider_info.pop("pulling_enabled", True)

        # if pulling_enabled is "true" or "false" cast it to boolean
        if isinstance(pulling_enabled, str):
            pulling_enabled = pulling_enabled.lower() == "true"

        provider_config = {
            "authentication": provider_info,
            "name": provider.name,
        }

        context_manager = ContextManager(tenant_id=tenant_id)
        try:
            provider_instance = ProvidersFactory.get_provider(
                context_manager, provider_id, provider.type, provider_config
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        validated_scopes = provider_instance.validate_scopes()

        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        secret_manager.write_secret(
            secret_name=provider.configuration_key,
            secret_value=json.dumps(provider_config),
        )

        provider.installed_by = updated_by
        provider.validatedScopes = validated_scopes
        provider.pulling_enabled = pulling_enabled
        session.commit()

        return {
            "details": provider_config,
            "validatedScopes": validated_scopes,
        }

    @staticmethod
    def delete_provider(
        tenant_id: str,
        provider_id: str,
        session: Session,
        allow_provisioned=False,
        commit: bool = True,
    ):
        provider_model: Provider = session.exec(
            select(Provider).where(
                (Provider.tenant_id == tenant_id) & (Provider.id == provider_id)
            )
        ).one_or_none()

        if not provider_model:
            raise HTTPException(404, detail="Provider not found")

        if provider_model.provisioned and not allow_provisioned:
            raise HTTPException(403, detail="Cannot delete a provisioned provider")

        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        config = secret_manager.read_secret(
            provider_model.configuration_key, is_json=True
        )

        try:
            secret_manager.delete_secret(provider_model.configuration_key)
        except Exception:
            logger.exception("Failed to delete the provider secret")

        if provider_model.consumer:
            try:
                event_subscriber = EventSubscriber.get_instance()
                event_subscriber.remove_consumer(provider_model)
            except Exception:
                logger.exception("Failed to unregister provider as a consumer")

        try:
            provider = ProvidersFactory.get_provider(
                context_manager, provider_model.id, provider_model.type, config
            )
            provider.clean_up()
        except NotImplementedError:
            logger.info(
                "Being deleted provider of type %s does not have a clean_up method",
                provider_model.type,
            )
        except Exception:
            logger.exception(msg="Provider deleted but failed to clean up provider")

        session.delete(provider_model)
        if commit:
            session.commit()

    @staticmethod
    def validate_provider_scopes(
        tenant_id: str, provider_id: str, session: Session
    ) -> Dict[str, bool | str]:
        provider = session.exec(
            select(Provider).where(
                (Provider.tenant_id == tenant_id) & (Provider.id == provider_id)
            )
        ).one_or_none()

        if not provider:
            raise HTTPException(404, detail="Provider not found")

        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        provider_config = secret_manager.read_secret(
            provider.configuration_key, is_json=True
        )
        provider_instance = ProvidersFactory.get_provider(
            context_manager, provider_id, provider.type, provider_config
        )
        validated_scopes = provider_instance.validate_scopes()

        if validated_scopes != provider.validatedScopes:
            provider.validatedScopes = validated_scopes
            session.commit()

        return validated_scopes

    @staticmethod
    def is_provider_installed(tenant_id: str, provider_name: str) -> bool:
        provider = get_provider_by_name(tenant_id, provider_name)
        return provider is not None

    @staticmethod
    def provision_provider_deduplication_rules(
        tenant_id: str,
        provider: Provider,
        deduplication_rules: Dict[str, Dict[str, Any]],
    ):
        """
        Provision deduplication rules for a provider.

        Args:
            tenant_id (str): The tenant ID.
            provider (Provider): The provider to provision the deduplication rules for.
            deduplication_rules (Dict[str, Dict[str, Any]]): The deduplication rules to provision.
        """

        # Provision the deduplication rules
        deduplication_rules_dict: dict[str, dict] = {}
        for rule_name, rule_config in deduplication_rules.items():
            logger.info(f"Provisioning deduplication rule {rule_name}")
            rule_config["name"] = rule_name
            rule_config["provider_name"] = provider.name
            rule_config["provider_type"] = provider.type
            deduplication_rules_dict[rule_name] = rule_config

        # Provision deduplication rules
        provision_deduplication_rules(
            deduplication_rules=deduplication_rules_dict,
            tenant_id=tenant_id,
            provider=provider,
        )

    @staticmethod
    def write_provisioned_hash(tenant_id: str, hash_value: str):
        """
        Write the provisioned hash to Redis or file.

        Args:
            tenant_id (str): The tenant ID.
            hash_value (str): The hash value to write.
        """
        if REDIS:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
            r.set(f"{tenant_id}_providers_hash", hash_value)
            logger.info(f"Provisioned hash for tenant {tenant_id} written to Redis!")
        else:
            with open(
                DEFAULT_PROVIDER_HASH_STATE_FILE.format(tenant_id=tenant_id), "w"
            ) as f:
                f.write(hash_value)
                logger.info(f"Provisioned hash for tenant {tenant_id} written to file!")

    @staticmethod
    def get_provisioned_hash(tenant_id: str) -> Optional[str]:
        """
        Get the provisioned hash from Redis or file.

        Args:
            tenant_id (str): The tenant ID.

        Returns:
            Optional[str]: The provisioned hash, or None if not found.
        """
        previous_hash = None
        if REDIS:
            try:
                with redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB) as r:
                    previous_hash = r.get(f"{tenant_id}_providers_hash")
                    if isinstance(previous_hash, bytes):
                        previous_hash = previous_hash.decode("utf-8").strip()
                logger.info(
                    f"Provisioned hash for tenant {tenant_id}: {previous_hash or 'Not found'}"
                )
            except redis.RedisError as e:
                logger.warning(f"Redis error for tenant {tenant_id}: {e}")

        if previous_hash is None:
            try:
                with open(
                    DEFAULT_PROVIDER_HASH_STATE_FILE.format(tenant_id=tenant_id),
                    "r",
                    encoding="utf-8",
                ) as f:
                    previous_hash = f.read().strip()
                logger.info(f"Provisioned hash for tenant {tenant_id} read from file.")
            except FileNotFoundError:
                logger.info(f"Provisioned hash file for tenant {tenant_id} not found.")
            except Exception as e:
                logger.warning(
                    f"Failed to read hash from file for tenant {tenant_id}: {e}"
                )

        return previous_hash if previous_hash else None

    @staticmethod
    def calculate_provider_hash(
        provisioned_providers_dir: Optional[str] = None,
        provisioned_providers_json: Optional[str] = None,
    ) -> str:
        """
        Calculate the hash of the provider configurations.

        Args:
            provisioned_providers_dir (Optional[str]): Directory containing provider YAML files.
            provisioned_providers_json (Optional[str]): JSON string of provider configurations.

        Returns:
            str: SHA256 hash of the provider configurations.
        """
        if provisioned_providers_json:
            providers_data = provisioned_providers_json
        elif provisioned_providers_dir:
            providers_data = []
            for file in os.listdir(provisioned_providers_dir):
                if file.endswith((".yaml", ".yml")):
                    provider_path = os.path.join(provisioned_providers_dir, file)
                    with open(provider_path, "r") as yaml_file:
                        providers_data.append(yaml_file.read())
        else:
            providers_data = ""  # No providers to provision

        return hashlib.sha256(json.dumps(providers_data).encode("utf-8")).hexdigest()

    @staticmethod
    def provision_providers(tenant_id: str):
        """
        Provision providers from a directory or env variable.

        Args:
            tenant_id (str): The tenant ID.
        """
        logger = logging.getLogger(__name__)

        provisioned_providers_dir = os.environ.get("KEEP_PROVIDERS_DIRECTORY")
        provisioned_providers_json = os.environ.get("KEEP_PROVIDERS")

        if (
            provisioned_providers_dir is not None
            and provisioned_providers_json is not None
        ):
            raise Exception(
                "Providers provisioned via env var and directory at the same time. Please choose one."
            )

        if provisioned_providers_dir is not None and not os.path.isdir(
            provisioned_providers_dir
        ):
            raise FileNotFoundError(
                f"Directory {provisioned_providers_dir} does not exist"
            )

        # Get all existing provisioned providers
        provisioned_providers = get_all_provisioned_providers(tenant_id)

        if not (provisioned_providers_dir or provisioned_providers_json):
            if provisioned_providers:
                logger.info(
                    "No providers for provisioning found. Deleting all provisioned providers."
                )
            else:
                logger.info("No providers for provisioning found. Nothing to do.")
                return

        # Calculate the hash of the provider configurations
        providers_hash = ProvidersService.calculate_provider_hash(
            provisioned_providers_dir, provisioned_providers_json
        )

        # Get the previous hash from Redis or file
        previous_hash = ProvidersService.get_provisioned_hash(tenant_id)
        if providers_hash == previous_hash:
            logger.info(
                "Provider configurations have not changed. Skipping provisioning."
            )
            return
        else:
            logger.info("Provider configurations have changed. Provisioning providers.")

        # Do all the provisioning within a transaction
        session = Session(engine)
        try:
            with session.begin():
                ### We do delete all the provisioned providers and begin provisioning from the beginning.
                logger.info(
                    f"Deleting all provisioned providers for tenant {tenant_id}"
                )
                for provisioned_provider in provisioned_providers:
                    try:
                        logger.info(f"Deleting provider {provisioned_provider.name}")
                        ProvidersService.delete_provider(
                            tenant_id,
                            provisioned_provider.id,
                            session,
                            allow_provisioned=True,
                            commit=False,
                        )
                        logger.info(f"Provider {provisioned_provider.name} deleted")
                    except Exception as e:
                        logger.exception(
                            "Failed to delete provisioned provider",
                            extra={"exception": e},
                        )
                        continue

                # Flush the session to ensure all deletions are committed
                session.flush()

                ### Provisioning from env var
                if provisioned_providers_json is not None:
                    # Avoid circular import
                    from keep.parser.parser import Parser

                    parser = Parser()
                    context_manager = ContextManager(tenant_id=tenant_id)
                    parser._parse_providers_from_env(context_manager)
                    env_providers = context_manager.providers_context

                    for provider_name, provider_config in env_providers.items():
                        # We skip checking if the provider is already installed, as it will skip the new configurations
                        # and we want to update the provisioned provider with the new configuration
                        logger.info(f"Provisioning provider {provider_name}")
                        try:
                            installed_provider_info = ProvidersService.install_provider(
                                tenant_id=tenant_id,
                                installed_by="system",
                                provider_id=provider_config["type"],
                                provider_name=provider_name,
                                provider_type=provider_config["type"],
                                provider_config=provider_config["authentication"],
                                provisioned=True,
                                validate_scopes=False,
                                session=session,
                                commit=False,
                            )
                            provider = installed_provider_info["provider"]
                            logger.info(
                                f"Provider {provider_name} provisioned successfully"
                            )
                        except Exception as e:
                            logger.error(
                                "Error provisioning provider from env var",
                                extra={"exception": e},
                            )

                        # Flush the provider so that we can provision its deduplication rules
                        session.flush()

                        # Configure deduplication rules
                        deduplication_rules = provider_config.get(
                            "deduplication_rules", {}
                        )
                        if deduplication_rules:
                            logger.info(
                                f"Provisioning deduplication rules for provider {provider_name}"
                            )
                            ProvidersService.provision_provider_deduplication_rules(
                                tenant_id=tenant_id,
                                provider=provider,
                                deduplication_rules=deduplication_rules,
                            )

                ### Provisioning from the directory
                if provisioned_providers_dir is not None:
                    for file in os.listdir(provisioned_providers_dir):
                        if file.endswith((".yaml", ".yml")):
                            logger.info(f"Provisioning provider from {file}")
                            provider_path = os.path.join(
                                provisioned_providers_dir, file
                            )

                            try:
                                with open(provider_path, "r") as yaml_file:
                                    provider_yaml = cyaml.safe_load(yaml_file.read())
                                    provider_name = provider_yaml["name"]
                                    provider_type = provider_yaml["type"]
                                    provider_config = provider_yaml.get(
                                        "authentication", {}
                                    )

                                    # We skip checking if the provider is already installed, as it will skip the new configurations
                                    # and we want to update the provisioned provider with the new configuration
                                    logger.info(f"Installing provider {provider_name}")
                                    installed_provider_info = (
                                        ProvidersService.install_provider(
                                            tenant_id=tenant_id,
                                            installed_by="system",
                                            provider_id=provider_type,
                                            provider_name=provider_name,
                                            provider_type=provider_type,
                                            provider_config=provider_config,
                                            provisioned=True,
                                            validate_scopes=False,
                                            session=session,
                                            commit=False,
                                        )
                                    )
                                    provider = installed_provider_info["provider"]
                                    logger.info(
                                        f"Provider {provider_name} provisioned successfully"
                                    )

                                    # Flush the provider so that we can provision its deduplication rules
                                    session.flush()

                                    # Configure deduplication rules
                                    deduplication_rules = provider_yaml.get(
                                        "deduplication_rules", {}
                                    )
                                    if deduplication_rules:
                                        logger.info(
                                            f"Provisioning deduplication rules for provider {provider_name}"
                                        )
                                        ProvidersService.provision_provider_deduplication_rules(
                                            tenant_id=tenant_id,
                                            provider=provider,
                                            deduplication_rules=deduplication_rules,
                                        )
                            except Exception as e:
                                logger.error(
                                    "Error provisioning provider from directory",
                                    extra={"exception": e},
                                )
                                continue
        except Exception as e:
            logger.error("Provisioning failed, rolling back", extra={"exception": e})
            session.rollback()
        finally:
            # Store the hash in Redis or file
            try:
                ProvidersService.write_provisioned_hash(tenant_id, providers_hash)
            except Exception as e:
                logger.warning(f"Failed to store hash: {e}")
            session.close()

    @staticmethod
    def get_provider_logs(
        tenant_id: str, provider_id: str
    ) -> List[ProviderExecutionLog]:
        if not config("KEEP_STORE_PROVIDER_LOGS", cast=bool, default=False):
            raise HTTPException(404, detail="Provider logs are not enabled")

        return get_provider_logs(tenant_id, provider_id)
