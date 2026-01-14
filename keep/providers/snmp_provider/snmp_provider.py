import asyncio
import logging

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntfrcv

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.config import SNMPProviderAuthConfig


class SNMPProvider( BaseProvider ): # SNMP Provider that listens for SNMP traps and pushes them as alerts to Keep.
    def __init__( self, context_manager, provider_id: str, config: ProviderConfig ):
        super().__init__( context_manager, provider_id, config )
        self.logger = logging.getLogger( __name__ )
        self.snmp_engine = engine.SnmpEngine()
        self.transport_dispatcher = None

    def validate_config( self ):
        return True

    def dispose( self ): # Cleanup resources when the provider is destroyed.
        if self.transport_dispatcher:
            self.transport_dispatcher.closeDispatcher()
        super().dispose()

    def _process_trap( self, snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx ): # Callback function executed when an SNMP trap is received.
        transportDomain, transportAddress = snmpEngine.msgAndPduDsp.getTransportInfo( stateReference )
        source_ip = transportAddress[0]

        self.logger.info( f"Received SNMP trap from { source_ip }" )

        # Parse the Variable Bindings (OIDs and Values)
        trap_data = {}
        msg = []

        for name, val in varBinds:
            oid_str = name.prettyPrint()
            value_str = val.prettyPrint()
            trap_data[oid_str] = value_str
            msg.append( f"{ oid_str }: { value_str }" )

        # Construct the alert dictionary
        # We try to find a standard OID for 'message' or just dump all data
        event = {
            "name": "SNMP Trap",
            "source": ["snmp"],
            "description": f"Trap received from { source_ip }",
            "status": "info",  # Default status could be mapped from specific OIDs
            "severity": "info",
            "fingerprint": f"{source_ip}-{ next( iter( trap_data ), 'empty' ) }",
            "trap_data": trap_data,  # Structured data
            "details": "\n".join( msg ),  # Readable string
            "host": source_ip,
        }

        self.logger.info( f"Pushing SNMP alert to Keep: { event }" )

        # Push the alert to Keep's core logic
        # Note: In a real Keep environment, ensure this is thread-safe or async-compatible
        try:
            self._push_alert( event )
        except Exception as e:
            self.logger.error( f"Failed to push alert: { e }" )

    async def listen( self ): # Starts the SNMP Trap listener (Async).
        # 1. Get Config
        auth_config = self.config.authentication
        host = auth_config.get( "host", "0.0.0.0" )
        port = int( auth_config.get( "port", SNMPProviderAuthConfig.DEFAULTPORT ) )
        community = auth_config.get( "community", "public" )

        self.logger.info( f"Starting SNMP Trap listener on { host }:{ port } with community '{ community }'" )

        # 2. Setup Transport (UDP)
        # This binds the engine to the port using asyncio-compatible UDP
        config.addTransport(
            self.snmp_engine,
            udp.domainName + (1,),
            udp.UdpTransport().openServerMode( ( host, port ) )
        )

        # 3. Setup Community (Security)
        # Allows this engine to accept traps with the specified community string
        config.addV1System(self.snmp_engine, 'my-area', community)

        # 4. Register the callback function
        # This tells the engine: "When a trap arrives, send it to self._process_trap"
        ntfrcv.NotificationReceiver(self.snmp_engine, self._process_trap)

        # 5. Start the Engine
        # We grab the dispatcher directly from the engine
        self.transport_dispatcher = self.snmp_engine.transportDispatcher

        try:
            self.transport_dispatcher.jobStarted(1)
            # Begin a loop that asyncio is ok with
            while True:
                self.transport_dispatcher.runDispatcher()
                await asyncio.sleep(1)  # Yields control to the asyncio loop
        except Exception as e:
            self.logger.error(f"SNMP Listener failed: {e}")
        finally:
            self.transport_dispatcher.jobStarted(-1)  # Cleanly stop the job
            self.transport_dispatcher.closeDispatcher()
# --------------------------------------------------------------------------------
# Standalone execution for testing
# Run with: python -m keep.providers.snmp_provider.snmp_provider
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    # Mocking BaseProvider dependencies for standalone run
    class MockProviderConfig:
        authentication = { "host": "0.0.0.0", "port": SNMPProviderAuthConfig.DEFAULTPORT, "community": "public" }


    # Simple Mock Provider to override _push_alert for CLI testing
    class TestSNMPProvider( SNMPProvider ):
        def __init__( self ):
            # Bypass BaseProvider init for simple testing
            self.logger = logging.getLogger("TestSNMP")
            self.snmp_engine = engine.SnmpEngine()
            self.config = MockProviderConfig()
            self.transport_dispatcher = None
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