from keep.providers.base.base_provider import BaseProvider
class SnmpProvider(BaseProvider):
    def __init__(self, provider_id: str, config):
        super().__init__(provider_id, config)
    def _process_trap(self, var_binds, source_ip):
        return {"source": "snmp", "event": str(var_binds), "host": source_ip, "trap_oid": "1.3.6.1.4.1.2021.251.1"}

