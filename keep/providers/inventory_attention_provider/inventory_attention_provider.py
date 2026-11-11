"""Native Keep workflow adapter. Disabled policy performs no external I/O."""
from keep.providers.base.base_provider import BaseProvider
from keep.api.bl.inventory_attention_runtime import load_configuration, InventoryWorkflow, NativeSlackNotifier


class InventoryAttentionProvider(BaseProvider):
    def validate_config(self):
        pass

    def dispose(self):
        pass

    def _notify(self, operation='ingest', alert=None, **kwargs):
        tenant = self.context_manager.tenant_id
        config = load_configuration(tenant)
        if config is None:
            return {'status': 'disabled'}
        from keep.api.core.db import engine
        from keep.providers.providers_factory import ProvidersFactory
        slack = ProvidersFactory.get_installed_provider(tenant, config['slack_provider_id'], 'slack')
        fallback = ProvidersFactory.get_installed_provider(tenant, config["fallback_provider_id"], "webhook")
        return InventoryWorkflow(engine, tenant, config, NativeSlackNotifier(slack, config, fallback)).run(operation, alert)
