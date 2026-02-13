import dataclasses
import pydantic
#config.py
@pydantic.dataclasses.dataclass
class SNMPProviderAuthConfig: # SNMP authentication configuration.

    DEFAULTPORT = 1162

    port: int = pydantic.Field(
        default=DEFAULTPORT, # SNMP default port
        metadata={
            "required": True,
            "description": "SNMP port for listening for traps",
            "hint": "SNMP defaults to 1162; elevate to port 162 for standard SNMP (requires root)"
        }
    )
    community: str = pydantic.Field(
        default="public",
        metadata={
            "required": True,
            "description": "SNMP community str",
            "hint": "e.g. public"
        }
    )