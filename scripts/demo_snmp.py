#!/usr/bin/env python3
"""
Simple script demonstrating how to initialize the SNMP Provider natively
and query metrics/simulate traps.
"""
import logging
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider

logging.basicConfig(level=logging.INFO)

def main():
    print("=== SNMP Provider Demo ===")
    print("Configuring Provider to point to demo.pysnmp.com...")

    # Set up Keep Context
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="demo")

    # Set up config for the provider
    config = ProviderConfig(
        authentication={
            "host": "demo.pysnmp.com",  # Public SNMP agent
            "port": 161,
            "community": "public",
            "oids": "1.3.6.1.2.1.1.1.0, 1.3.6.1.2.1.1.5.0", # sysDescr, sysName
            "trap_port": 1162
        }
    )

    provider = SnmpProvider(context_manager, "demo-snmp-provider", config)

    # 1. Fetch configured OIDs (pull)
    print("\n--- 1. Testing Polling (Pull) ---")
    try:
        alerts = provider._get_alerts()
        for alert in alerts:
            print(f"[{alert.name}] -> {alert.payload['value']}")
    except Exception as e:
        print(f"Error querying OIDs: {e}")



if __name__ == "__main__":
    main()
