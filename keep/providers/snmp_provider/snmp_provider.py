import logging
import snmp
from typing import Dict

class SNMPProvider:
    def __init__(self, config: Dict):
        self.config = config
        self.snmp = snmp

    def sendSNMPTrap(self, trap: Dict) -> None:
        if not self.config or not self.snmp:
            raise ValueError("SNMP provider is not configured or SNMP module is not available")

        try:
            self.snmp.send_trap(trap['oid'], trap['value'])
        except Exception as e:
            logging.error(f"Failed to send SNMP trap: {e}")