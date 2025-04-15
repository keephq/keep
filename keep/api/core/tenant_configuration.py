import logging
from datetime import datetime, timedelta

from fastapi import HTTPException

from keep.api.core.config import config
from keep.api.core.db import get_tenants_configurations, write_tenant_config


class TenantConfiguration:
    _instance = None

    class _TenantConfiguration:

        def __init__(self):
            self.logger = logging.getLogger(__name__)
            self.configurations = self._load_tenant_configurations()
            self.last_loaded = datetime.now()
            self.reload_time = config(
                "TENANT_CONFIGURATION_RELOAD_TIME", default=5, cast=int
            )

        def _load_tenant_configurations(self):
            self.logger.debug("Loading tenants configurations")
            tenants_configuration = get_tenants_configurations()
            self.logger.debug(
                "Tenants configurations loaded",
                extra={
                    "number_of_tenants": len(tenants_configuration),
                },
            )
            self.last_loaded = datetime.now()
            return tenants_configuration

        def _reload_if_needed(self):
            if datetime.now() - self.last_loaded > timedelta(minutes=self.reload_time):
                self.logger.info("Reloading tenants configurations")
                self.configurations = self._load_tenant_configurations()
                self.logger.info("Tenants configurations reloaded")

        def get_configuration(self, tenant_id, config_name=None):
            self._reload_if_needed()
            # tenant_config = self.configurations.get(tenant_id, {})
            tenant_config = self.configurations.get(tenant_id)
            if not tenant_config:
                self.logger.debug(f"Tenant {tenant_id} not found in memory, loading it")
                self.configurations = self._load_tenant_configurations()
                tenant_config = self.configurations.get(tenant_id, {})

            if tenant_id not in self.configurations:
                self.logger.exception(
                    f"Tenant not found [id: {tenant_id}]",
                    extra={
                        "tenant_id": tenant_id,
                    },
                )
                raise HTTPException(
                    status_code=401, detail=f"Tenant not found [id: {tenant_id}]"
                )

            if config_name is None:
                return tenant_config

            return tenant_config.get(config_name, None)

        def update_configuration(
            self, tenant_id, configuration, config_name=None, config_value=None
        ):
            """
            Updates a tenant's configuration in the database and in memory.

            Args:
                tenant_id (str): The ID of the tenant
                configuration (dict, optional): The full configuration to set. If provided, it will replace the entire configuration.
                config_name (str, optional): The name of the specific configuration to update
                config_value (any, optional): The value to set for the specific configuration

            Returns:
                dict: The updated configuration

            Raises:
                HTTPException: If the tenant is not found
            """
            self._reload_if_needed()

            # Check if tenant exists
            if tenant_id not in self.configurations:
                self.logger.exception(
                    f"Tenant not found [id: {tenant_id}]",
                    extra={
                        "tenant_id": tenant_id,
                    },
                )
                raise HTTPException(
                    status_code=401, detail=f"Tenant not found [id: {tenant_id}]"
                )

            # If full configuration is provided, use it directly
            if configuration is not None:
                updated_config = configuration
            # Otherwise, update a specific config key
            elif config_name is not None and config_value is not None:
                # Get the current configuration or initialize empty dict if None
                current_config = self.configurations.get(tenant_id, {}) or {}
                # Create a copy to avoid modifying the original
                updated_config = dict(current_config)
                # Update the specific config
                updated_config[config_name] = config_value
            else:
                raise ValueError(
                    "Either configuration or config_name and config_value must be provided"
                )

            # Update in the database
            write_tenant_config(tenant_id, updated_config)

            # Update in memory
            self.configurations[tenant_id] = updated_config

            self.logger.info(
                f"Configuration updated for tenant {tenant_id}",
                extra={
                    "tenant_id": tenant_id,
                },
            )

            return updated_config

    def __new__(cls):
        if not cls._instance:
            cls._instance = cls._TenantConfiguration()
        return cls._instance
