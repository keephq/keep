import asyncio
import logging
from datetime import datetime, timedelta

from keep.api.core.config import config
from keep.api.core.db import get_tenants_configurations


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

            # Patching because this method could be called from a sync context which is inside the loop.
            # Todo: asynchroiize the whole method.
            import nest_asyncio
            nest_asyncio.apply()
            
            tenants_configuration = asyncio.run(get_tenants_configurations())
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

        def get_configuration(self, tenant_id, config_name):
            self._reload_if_needed()
            # tenant_config = self.configurations.get(tenant_id, {})
            tenant_config = self.configurations.get(tenant_id)
            if not tenant_config:
                self.logger.debug(f"Tenant {tenant_id} not found in memory, loading it")
                self.configurations = self._load_tenant_configurations()
                tenant_config = self.configurations.get(tenant_id, {})

            if tenant_id not in self.configurations:
                self.logger.warning(
                    f"Tenant not found [id: {tenant_id}]",
                    extra={
                        "tenant_id": tenant_id,
                    },
                )
                raise ValueError(f"Tenant not found [id: {tenant_id}]")

            return tenant_config.get(config_name, None)

    def __new__(cls):
        if not cls._instance:
            cls._instance = cls._TenantConfiguration()
        return cls._instance
