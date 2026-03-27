from pysnmp.hlapi import *
from keep.providers.base_provider import BaseProvider
from keep.models.provider_config import ProviderConfig

class SnmpProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def validate_config(self):
        self.host = self.config.authentication.get("host")
        self.port = int(self.config.authentication.get("port", 161))
        self.community = self.config.authentication.get("community", "public")

    def query(self, **kwargs):
        oid = kwargs.get("oid")
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(self.community),
            UdpTransportTarget((self.host, self.port)),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        error_indication, error_status, error_index, var_binds = next(iterator)
        if error_indication:
            return str(error_indication)
        elif error_status:
            return str(error_status)
        else:
            return {str(var_bind[0]): str(var_bind[1]) for var_bind in var_binds}

    def dispose(self):
        pass
