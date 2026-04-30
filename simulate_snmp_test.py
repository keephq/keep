import time
import threading
import logging
from keep.providers.snmp_provider.snmp_provider import SnmpProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.contextmanager.contextmanager import ContextManager
from pysnmp.hlapi import *

# Set up logging to see what's happening
logging.basicConfig(level=logging.DEBUG)

def start_provider():
    context_manager = ContextManager(tenant_id="test-tenant")
    config = ProviderConfig(
        authentication={
            "bind_address": "127.0.0.1",
            "port": 1162,
            "community": "public",
        }
    )
    provider = SnmpProvider(
        context_manager=context_manager,
        provider_id="snmp-test",
        config=config
    )
    
    # Mock _push_alert to see if it's called
    provider._push_alert = lambda alert: print(f"\n[SUCCESS] Alert Pushed to Keep: {alert['name']}\nPayload: {alert['payload']}\n")
    
    provider.start_consume()

def send_trap():
    print("Sending SNMP Trap to localhost:1162...")
    errorIndication, errorStatus, errorIndex, varBinds = next(
        sendNotification(
            SnmpEngine(),
            CommunityData('public', mpModel=0),
            UdpTransportTarget(('127.0.0.1', 1162)),
            ContextData(),
            'trap',
            NotificationType(
                ObjectIdentity('1.3.6.1.6.3.1.1.5.2') # Cold Start Trap
            ).addVarBinds(
                ('1.3.6.1.2.1.1.5.0', OctetString('Test-Device'))
            )
        )
    )
    if errorIndication:
        print(f"Error sending trap: {errorIndication}")
    else:
        print("Trap sent successfully!")

if __name__ == "__main__":
    # Start provider in a background thread
    t = threading.Thread(target=start_provider, daemon=True)
    t.start()
    
    # Wait for provider to start
    time.sleep(2)
    
    # Send a trap
    send_trap()
    
    # Wait to see the result
    time.sleep(5)
    print("Simulation finished.")
