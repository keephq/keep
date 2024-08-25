import json
import logging
import time
import uuid
from typing import Any, Dict, List

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from keep.api.core.db import engine, get_provider_by_name
from keep.api.models.db.provider import Provider
from keep.api.models.provider import Provider as ProviderModel
from keep.contextmanager.contextmanager import ContextManager
from keep.event_subscriber.event_subscriber import EventSubscriber
from keep.providers.providers_factory import ProvidersFactory
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

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
    def install_provider(
        tenant_id: str,
        installed_by: str,
        provider_id: str,
        provider_name: str,
        provider_type: str,
        provider_config: Dict[str, Any],
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

        validated_scopes = provider.validate_scopes()

        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        secret_name = f"{tenant_id}_{provider_type}_{provider_unique_id}"
        secret_manager.write_secret(
            secret_name=secret_name,
            secret_value=json.dumps(config),
        )

        with Session(engine) as session:
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
            )
            try:
                session.add(provider_model)
                session.commit()
            except IntegrityError:
                raise HTTPException(
                    status_code=409, detail="Provider already installed"
                )

            if provider_model.consumer:
                try:
                    event_subscriber = EventSubscriber.get_instance()
                    event_subscriber.add_consumer(provider)
                except Exception:
                    logger.exception("Failed to register provider as a consumer")

            return {
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
        session.commit()

        return {
            "details": provider_config,
            "validatedScopes": validated_scopes,
        }

    @staticmethod
    def delete_provider(tenant_id: str, provider_id: str, session: Session):
        provider = session.exec(
            select(Provider).where(
                (Provider.tenant_id == tenant_id) & (Provider.id == provider_id)
            )
        ).one_or_none()

        if not provider:
            raise HTTPException(404, detail="Provider not found")

        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)

        try:
            secret_manager.delete_secret(provider.configuration_key)
        except Exception:
            logger.exception("Failed to delete the provider secret")

        if provider.consumer:
            try:
                event_subscriber = EventSubscriber.get_instance()
                event_subscriber.remove_consumer(provider)
            except Exception:
                logger.exception("Failed to unregister provider as a consumer")

        session.delete(provider)
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
    def provision_providers_from_env(tenant_id: str):
        # avoid circular import
        from keep.parser.parser import Parser

        parser = Parser()
        context_manager = ContextManager(tenant_id=tenant_id)
        parser._parse_providers_from_env(context_manager)
        env_providers = context_manager.providers_context
        for provider_name, provider_config in env_providers.items():
            logger.info(f"Provisioning provider {provider_name}")
            # if its already installed, skip
            if ProvidersService.is_provider_installed(tenant_id, provider_name):
                logger.info(f"Provider {provider_name} already installed")
                continue
            logger.info(f"Installing provider {provider_name}")
            ProvidersService.install_provider(
                tenant_id=tenant_id,
                installed_by="system",
                provider_id=provider_config["type"],
                provider_name=provider_name,
                provider_type=provider_config["type"],
                provider_config=provider_config["authentication"],
            )
            logger.info(f"Provider {provider_name} provisioned")
