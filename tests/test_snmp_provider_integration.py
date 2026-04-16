import pytest
import subprocess
import time
import socket
import os
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

@pytest.fixture(scope="module")
def snmpsim_server():
    """
    Start an snmpsim subprocess for integration testing.
    Depends on `public.snmprec` located in `tests/data/`.
    """
    port = 11161
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    
    # Start the simulator using the snmpsim-command-responder module
    # We pass the data directory containing public.snmprec
    process = subprocess.Popen(
        [
            "snmpsim-command-responder",
            f"--data-dir={data_dir}",
            f"--agent-udpv4-endpoint=127.0.0.1:{port}"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Allow time for snmpsim to bind and start
    time.sleep(2)

    yield port

    process.terminate()
    process.wait(timeout=5)


@pytest.fixture
def provider(snmpsim_server):
    context_manager = ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")
    config = ProviderConfig(
        authentication={
            "host": "127.0.0.1",
            "port": snmpsim_server,
            "community": "public",
            "oids": "1.3.6.1.2.1.1.1.0, 1.3.6.1.2.1.1.5.0", # Fetching sysDescr & sysName
        }
    )
    return SnmpProvider(context_manager, "integration_snmp", config)


def test_fetch_metrics_integration(provider):
    """Test fetch_metrics against the live snmpsim agent."""
    metrics = provider.fetch_metrics(["1.3.6.1.2.1.1.1.0", "1.3.6.1.2.1.1.5.0"])
    
    assert "1.3.6.1.2.1.1.1.0" in metrics
    assert "Hardware: amd64 Software: Linux" in metrics["1.3.6.1.2.1.1.1.0"]
    
    assert "1.3.6.1.2.1.1.5.0" in metrics
    assert metrics["1.3.6.1.2.1.1.5.0"] == "test-router"


def test_query_integration(provider):
    """Test full query flow generating AlertDtos."""
    alerts = provider._query()
    
    assert len(alerts) == 2
    
    alert_names = [a.name for a in alerts]
    assert "SNMP OID 1.3.6.1.2.1.1.1.0" in alert_names
    assert "SNMP OID 1.3.6.1.2.1.1.5.0" in alert_names
    
    for alert in alerts:
        assert alert.service == "127.0.0.1"
        if "1.3.6.1.2.1.1.5.0" in alert.name:
            assert alert.payload["value"] == "test-router"

def test_fetch_invalid_oid_integration(provider):
    """Test robustness when fetching a non-existent OID."""
    # This OID is intentionally not in public.snmprec
    metrics = provider.fetch_metrics(["1.3.6.1.4.1.9999.9999.0"])
    
    # Depending on simulator behavior and SNMP version, it might return empty 
    # or raise an exception (like NoSuchObject). We just ensure it doesn't crash 
    # abnormally outside of documented exceptions.
    try:
        assert isinstance(metrics, dict)
    except Exception as e:
        assert "SNMP" in str(e)
