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
        self.auth_protocol = self.config.authentication.get("auth_protocol", "HMAC-MD5")
        self.priv_protocol = self.config.authentication.get("priv_protocol", "AES-128")

    def _get_auth_data(self):
        if self.version == "v3":
            auth_protocols = {
                "HMAC-MD5": usmHMACMD5AuthProtocol,
                "HMAC-SHA": usmHMACSHAAuthProtocol,
                "HMAC-SHA2-224": usmHMAC128SHA224AuthProtocol,
                "HMAC-SHA2-256": usmHMAC192SHA256AuthProtocol,
            }
            priv_protocols = {
                "DES": usmDESPrivProtocol,
                "AES-128": usmAesCfb128Protocol,
                "AES-192": usmAesCfb192Protocol,
                "AES-256": usmAesCfb256Protocol,
            }
            
            return UsmUserData(
                self.username,
                self.auth_key,
                self.priv_key,
                authProtocol=auth_protocols.get(self.auth_protocol, usmHMACMD5AuthProtocol),
                privProtocol=priv_protocols.get(self.priv_protocol, usmAesCfb128Protocol)
            )
        return CommunityData(self.community)

    def query(self, **kwargs):
        oid = kwargs.get("oid")
        walk = kwargs.get("walk", False)
        auth_data = self._get_auth_data()
        transport = UdpTransportTarget((self.host, self.port))
        
        results = {}
        
        if walk:
            for (error_indication, error_status, error_index, var_binds) in nextCmd(
                SnmpEngine(),
                auth_data,
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False
            ):
                if error_indication or error_status:
                    break
                for var_bind in var_binds:
                    results[str(var_bind[0])] = str(var_bind[1])
        else:
            iterator = getCmd(
                SnmpEngine(),
                auth_data,
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            error_indication, error_status, error_index, var_binds = next(iterator)
            
            if error_indication:
                raise Exception(str(error_indication))
            elif error_status:
                raise Exception(str(error_status))
            
            for var_bind in var_binds:
                results[str(var_bind[0])] = str(var_bind[1])
                
        return results

    def listen(self, callback, **kwargs):
        pass

    def dispose(self):
        pass
        
