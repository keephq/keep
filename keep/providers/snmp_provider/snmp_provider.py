from pysnmp.hlapi import *
from keep.providers.base_provider import BaseProvider
from keep.models.provider_config import ProviderConfig

class SnmpProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def validate_config(self):
        self.host = self.config.authentication.get("host")
        self.port = int(self.config.authentication.get("port", 161))
        self.version = self.config.authentication.get("version", "v2c")
        self.community = self.config.authentication.get("community", "public")
        self.username = self.config.authentication.get("username")
        self.auth_key = self.config.authentication.get("auth_key")
        self.priv_key = self.config.authentication.get("priv_key")

    def _get_auth_data(self):
        if self.version == "v3":
            return UsmUserData(self.username, self.auth_key, self.priv_key)
        return CommunityData(self.community)

    def query(self, **kwargs):
        oid = kwargs.get("oid")
        auth_data = self._get_auth_data()
        
        iterator = getCmd(
            SnmpEngine(),
            auth_data,
            UdpTransportTarget((self.host, self.port)),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        
        error_indication, error_status, error_index, var_binds = next(iterator)
        
        if error_indication:
            raise Exception(str(error_indication))
        elif error_status:
            raise Exception(str(error_status))
        
        return {str(var_bind[0]): str(var_bind[1]) for var_bind in var_binds}

    def dispose(self):
        pass
        
