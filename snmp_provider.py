import threading
from datetime import datetime
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.entity.rfc3413 import ntfrcv


class SNMPProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["snmp", "traps"]

    def __init__(self, context_manager, provider_id, config):
        super().__init__(context_manager, provider_id, config)
        self.snmp_engine = None
        self.listener_thread = None
        self.running = False

    def validate_config(self):
        self.authentication_config = SNMPProviderAuthConfig(
            **self.config.authentication
        )

    def _trap_callback(self, snmpEngine, stateReference, contextEngineId,
                       contextName, varBinds, cbCtx):

        alert_data = {}
        
        for name, val in varBinds:
            alert_data[str(name)] = str(val)

        # Basic mapping logic (you will refine this)
        severity = AlertSeverity.INFO
        if "critical" in json.dumps(alert_data).lower():
            severity = AlertSeverity.CRITICAL

        alert = AlertDto(
            id=f"snmp-{datetime.utcnow().timestamp()}",
            name="SNMP Trap Received",
            description=json.dumps(alert_data),
            severity=severity,
            status=AlertStatus.FIRING,
            source="snmp",
            timestamp=datetime.utcnow(),
        )

        # Send alert into Keep
        self.logger.info(f"Received SNMP trap: {alert_data}")
        self.context_manager.trigger_event(alert)

    def _start_listener(self):
        self.snmp_engine = engine.SnmpEngine()

        config.addTransport(
            self.snmp_engine,
            udp.domainName,
            udp.UdpTransport().openServerMode(
                (self.authentication_config.listen_host,
                 self.authentication_config.listen_port)
            )
        )

        config.addV1System(
            self.snmp_engine,
            "my-area",
            self.authentication_config.community
        )

        ntfrcv.NotificationReceiver(
            self.snmp_engine,
            self._trap_callback
        )

        self.running = True

        try:
            self.snmp_engine.transportDispatcher.jobStarted(1)
            self.snmp_engine.transportDispatcher.runDispatcher()
        except Exception as e:
            self.logger.error(f"SNMP listener error: {e}")
        finally:
            self.snmp_engine.transportDispatcher.closeDispatcher()

    def start(self):
        """Custom method to start SNMP listener"""
        self.listener_thread = threading.Thread(target=self._start_listener)
        self.listener_thread.daemon = True
        self.listener_thread.start()

    def dispose(self):
        self.running = False
        if self.snmp_engine:
            try:
                self.snmp_engine.transportDispatcher.closeDispatcher()
            except Exception:
                pass
