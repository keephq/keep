"""
SNMP Provider for Keep
This provider listens for SNMP traps and pushes them as alerts to Keep.
"""


import asyncio
import logging

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntfrcv

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.config import SNMPProviderAuthConfig

class SNMPProvider( BaseProvider ):
    def __init__( self, context_manager, provider_id: str, config: ProviderConfig ):
        super().__init__( context_manager, provider_id, config )
        self.logger = logging.getLogger( __name__ )
        self.snmp_engine = engine.SnmpEngine()
        self.transport_dispatcher = None

    def validate_config( self ):
        self.authentication_config = SNMPProviderAuthConfig(
            **self.config.authentication
        )
        return True
        
    def dispose( self ):
        if self.transport_dispatcher:
            self.transport_dispatcher.closeDispatcher()
        super().dispose()

    def _process_trap( self, snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx ):
        transportDomain, transportAddress = snmpEngine.message_dispatcher.get_transport_info( stateReference )
        source_ip = transportAddress[0]

        self.logger.info( f"Received SNMP trap from { source_ip }" )

        trap_data = {}
        msg = []

        for name, val in varBinds:
            oid_str = name.prettyPrint()
            value_str = val.prettyPrint()
            trap_data[oid_str] = value_str
            msg.append( f"{ oid_str }: { value_str }" )

        event = {
            "name": "SNMP Trap",
            "source": ["snmp"],
            "description": f"Trap received from { source_ip }",
            "status": "info", 
            "severity": "info",
            "fingerprint": f"{source_ip}-{ next( iter( trap_data ), 'empty' ) }",
            "trap_data": trap_data,
            "details": "\n".join( msg ),
            "host": source_ip,
        }

        self.logger.info( f"Pushing SNMP alert to Keep: { event }" )

        try:
            self._push_alert( event )
        except Exception as e:
            self.logger.error( f"Failed to push alert: { e }" )

    async def listen( self ):
        """Listener for SNMP traps"""
        
        host = self.authentication_config.host
        port = self.authentication_config.port
        community = self.authentication_config.community

        self.logger.info( f"Starting SNMP Trap listener on { host }:{ port } with community '{ community }'" )

        config.add_transport(
            self.snmp_engine,
            udp.DOMAIN_NAME + (1,),
            udp.UdpTransport().open_server_mode( ( host, port ) )
        )

        config.add_v1_system(self.snmp_engine, 'my-area', community)

        ntfrcv.NotificationReceiver(self.snmp_engine, self._process_trap)

        self.transport_dispatcher = self.snmp_engine.transport_dispatcher

        try:
            self.transport_dispatcher.job_started(1)
            while True:
                self.transport_dispatcher.run_dispatcher()
                await asyncio.sleep(1) 
        except Exception as e:
            self.logger.error(f"SNMP Listener failed: {e}")
        finally:
            self.transport_dispatcher.job_finished(1)
            self.transport_dispatcher.closeDispatcher()
# --------------------------------------------------------------------------------
# Standalone execution for testing
# Run with: python -m keep.providers.snmp_provider.snmp_provider
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    class MockProviderConfig:
        authentication = { "host": "0.0.0.0", "port": SNMPProviderAuthConfig.DEFAULTPORT, "community": "public" }

    class TestSNMPProvider( SNMPProvider ):
        def __init__( self ):            
            self.logger = logging.getLogger("TestSNMP")
            self.snmp_engine = engine.SnmpEngine()
            self.config = MockProviderConfig()
            self.transport_dispatcher = None
            
            self.validate_config()

            logging.basicConfig(level=logging.INFO)
            
        def _push_alert(self, event):
            print( f"\n[✅ ALERT PUSHED] { event['name'] } from { event['host'] }" )
            print( f"Description: { event['description'] }" )
            print( f"Data: { event[ 'trap_data' ] }\n" )


    print( "🚀 Starting Standalone SNMP Trap Listener..." )
    provider = TestSNMPProvider()

    try:
        asyncio.run( provider.listen() )
    except KeyboardInterrupt:
        print( "\nStopping..." )