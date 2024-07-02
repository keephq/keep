import logging

from keep.api.core.db import get_tenants_configurations


class TenantConfiguration:
    _instance = None

    class _TenantConfiguration:
        def __init__(self):
            # Load all tenant configurations into memory
            self.logger = logging.getLogger(__name__)
            self.configurations = self._load_tenant_configurations()

        def _load_tenant_configurations(self):
            self.logger.info("Loading tenants configurations")
            tenants_configuration = get_tenants_configurations()
            self.logger.info("Tenants configurations loaded")
            return tenants_configuration

        def get_configuration(self, tenant_id, config_name):
            tenant_config = self.configurations.get(tenant_id, {})
            if not tenant_config:
                # try to load the tenant configuration
                self.logger.info(f"Tenant {tenant_id} not found in memory, loading it")
                self.configurations = self._load_tenant_configurations()
                tenant_config = self.configurations.get(tenant_id, {})

            if not tenant_config:
                self.logger.warning(f"Tenant {tenant_id} not found")
                raise ValueError(f"Tenant {tenant_id} not found")

            return tenant_config.get(config_name, None)

    def get_configuration(self, tenant_id, config_name):
        return self._instance.get_configuration(tenant_id, config_name)

    def __new__(cls):
        if not cls._instance:
            cls._instance = cls._TenantConfiguration()
        return cls._instance
