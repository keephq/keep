import dataclasses
import pydantic

#config.py
@pydantic.dataclasses.dataclass
class SNMPProviderAuthConfig:
    DEFAULTPORT = 1162
    
    host: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": True,
            "description": "Host/interface to bind SNMP listener",
            "hint": "Use 0.0.0.0 to listen on all interfaces"
        }
    )
    port: int = dataclasses.field(
        default=DEFAULTPORT,
        metadata={
            "required": True,
            "description": "SNMP port for listening for traps",
            "hint": "SNMP defaults to 1162; elevate to port 162 for standard SNMP (requires root)"
        }
    )
    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": True,
            "description": "SNMP community str",
            "hint": "e.g. public"
        }
    )