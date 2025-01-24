"""
Test script for SNMP Provider
"""

from asyncio.log import logger
import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock, PropertyMock
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider, SnmpProviderAuthConfig
from keep.exceptions.provider_exception import ProviderException
from keep.api.models.alert import AlertDto

# pytestmark = pytest.mark.asyncio(scope="session")

@pytest.fixture(scope="session")
def event_loop_policy():
    """Create and configure the event loop policy for the test session."""
    policy = asyncio.get_event_loop_policy()
    
    def cleanup_loop(loop):
        # Clean up any pending tasks
        pending = asyncio.all_tasks(loop)
        if pending:
            # Log pending tasks
            logger.info(f"Pending tasks: {pending}")
            
            # Cancel all pending tasks
            for task in pending:
                if not task.done():
                    task.cancel()
            
            # Run the event loop to process cancellations
            try:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except asyncio.CancelledError:
                pass
            
            # Wait a bit to ensure all resources are cleaned up
            loop.run_until_complete(asyncio.sleep(0.1))
        
        # Close the loop
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
        except Exception as e:
            logger.warning(f"Error during loop shutdown: {e}")
        
        loop.close()

    # Create a custom policy that includes our cleanup
    class CustomPolicy(type(policy)):
        def new_event_loop(self):
            loop = super().new_event_loop()
            loop.set_debug(True)
            return loop

        def get_event_loop(self):
            loop = super().get_event_loop()
            loop.set_debug(True)
            return loop

    custom_policy = CustomPolicy()
    asyncio.set_event_loop_policy(custom_policy)
    
    yield custom_policy

@pytest.fixture
def context_manager():
    return ContextManager(
        tenant_id="test",
        workflow_id="test_snmp"
    )

@pytest.fixture
def provider_config():
    return ProviderConfig(
        authentication={
            "snmp_version": "v2c",
            "community_string": "public",
            "listen_port": 162
        }
    )

@pytest.fixture
def snmp_provider(context_manager, provider_config):
    provider = SnmpProvider(
        context_manager=context_manager,
        provider_id="snmp_test",
        config=provider_config
    )
    return provider

@pytest.mark.asyncio(loop_scope="function")
async def test_snmp_get_operation(snmp_provider):
    """Test SNMP GET operation"""
    # Mock the MIB view controller
    mock_view_controller = MagicMock()
    mock_view_controller.get_node_name.return_value = ('SNMPv2-MIB', 'sysDescr', 0)
    snmp_provider.mib_view_controller = mock_view_controller

    result = await snmp_provider.query(
        operation='GET',
        host='demo.pysnmp.com',
        port=161,
        oid='1.3.6.1.2.1.1.1.0'  # System description
    )
    assert isinstance(result, list)
    assert len(result) > 0
    assert 'oid' in result[0]
    assert 'value' in result[0]
    assert result[0]['oid'] == 'SNMPv2-MIB::sysDescr.0'

@pytest.mark.asyncio(loop_scope="function")
async def test_snmp_getnext_operation(snmp_provider):
    """Test SNMP GETNEXT operation"""
    # Mock the MIB view controller
    mock_view_controller = MagicMock()
    mock_view_controller.get_node_name.return_value = ('SNMPv2-MIB', 'sysDescr', 0)
    snmp_provider.mib_view_controller = mock_view_controller

    result = await snmp_provider.query(
        operation='GETNEXT',
        host='demo.pysnmp.com',
        port=161,
        oid='1.3.6.1.2.1.1'  # System MIB
    )
    assert isinstance(result, list)
    assert len(result) > 0
    assert 'oid' in result[0]
    assert 'value' in result[0]

@pytest.mark.asyncio(loop_scope="function")
async def test_snmp_getbulk_operation(snmp_provider):
    """Test SNMP GETBULK operation"""
    # Mock the MIB view controller
    mock_view_controller = MagicMock()
    mock_view_controller.get_node_name.return_value = ('SNMPv2-MIB', 'ifTable', 'ifEntry', 'ifIndex', 1)
    snmp_provider.mib_view_controller = mock_view_controller

    result = await snmp_provider.query(
        operation='GETBULK',
        host='demo.pysnmp.com',
        port=161,
        oid='1.3.6.1.2.1.2.2'  # Interfaces table
    )
    assert isinstance(result, list)
    assert len(result) > 0
    for item in result:
        assert 'oid' in item
        assert 'value' in item
        assert item['oid'].startswith('SNMPv2-MIB::ifTable.ifEntry.ifIndex')

@pytest.mark.asyncio(loop_scope="function")
async def test_snmp_invalid_operation(snmp_provider):
    """Test invalid SNMP operation"""
    with pytest.raises(ProviderException) as exc_info:
        await snmp_provider.query(
            operation='INVALID',
            host='demo.pysnmp.com',
            port=161,
            oid='1.3.6.1.2.1.1.1.0'
        )
    assert "Unsupported SNMP operation" in str(exc_info.value)

@pytest.mark.asyncio(loop_scope="function")
async def test_snmp_missing_parameters(snmp_provider):
    """Test missing required parameters"""
    with pytest.raises(ProviderException) as exc_info:
        await snmp_provider.query(
            operation='GET',
            port=161
        )
    assert "Host and OID are required" in str(exc_info.value)



def test_provider_scopes_validation(context_manager, provider_config):
    """Test provider scopes validation"""
    provider = SnmpProvider(context_manager, "test", provider_config)
    scopes = provider.validate_scopes()
    assert isinstance(scopes, dict)
    assert "receive_traps" in scopes
    assert isinstance(scopes["receive_traps"], bool)

def create_test_provider():
    return ProviderConfig(
        authentication={
            "snmp_version": "v2c",
            "community_string": "public",
            "listen_port": 162
        }
    )

# @pytest.mark.asyncio
def test_format_alert():
    # Create a mock provider
    provider = SnmpProvider(MagicMock(), "test", create_test_provider())
    
    # Test mapping of different trap severities
    severity_map = {
        'emergency': 'critical',
        'alert': 'critical',
        'critical': 'critical',
        'error': 'high',
        'warning': 'warning',
        'notice': 'info',
        'info': 'info',
        'debug': 'info',
        'unknown': 'info'
    }
    
    for trap_severity, expected_severity in severity_map.items():
        alert = provider._format_alert({
            'trap_type': 'test_trap',
            'severity': trap_severity,
            'source_address': '127.0.0.1',
            'trap_timestamp': '2024-01-01T00:00:00Z'
        })
        assert isinstance(alert, AlertDto)
        assert alert.severity == expected_severity, f"Expected {expected_severity} for trap severity {trap_severity}, got {alert.severity}"
        
    # Ensure all pending tasks are completed
    # pending = asyncio.all_tasks()
    # if pending: 
    #     await asyncio.wait(pending)

def test_provider_config_validation():
    """Test that SNMPv3 configuration validation works correctly"""
    # Test that validation fails when username, auth_key and priv_key are missing for SNMPv3
    config = ProviderConfig(
        authentication={
            "snmp_version": "v3",
            "target_host": "demo.snmplabs.com",
            "target_port": 161
        }
    )
    
    # Create provider - this should raise an exception since username is required for SNMPv3
    with pytest.raises(ProviderException, match="The following fields are required for SNMPv3: Username, Authentication key, Privacy key"):
        provider = SnmpProvider(MagicMock(), "test", config)
        
    # Test that validation succeeds with valid SNMPv3 configuration
    config = ProviderConfig(
        authentication={
            "snmp_version": "v3",
            "username": "test_user",
            "auth_protocol": "SHA",
            "auth_key": "test_auth_key",
            "priv_protocol": "AES",
            "priv_key": "test_priv_key",
            "target_host": "demo.snmplabs.com",
            "target_port": 161
        }
    )
    
    # This should not raise an exception
    provider = SnmpProvider(MagicMock(), "test", config)
    assert provider.authentication_config.username == "test_user"

@pytest.mark.asyncio(loop_scope="function")
async def test_provider_disposal():
    """Test provider disposal"""
    provider = SnmpProvider(MagicMock(), "test", create_test_provider())
    
    # Create a mock dispatcher with async support
    mock_dispatcher = MagicMock()
    
    # Create a future for the loopingcall
    loop = asyncio.get_event_loop()
    loopingcall = loop.create_future()
    loopingcall.cancel()  # Mark it as cancelled
    
    mock_dispatcher.loopingcall = loopingcall
    mock_dispatcher._transports = {}
    
    # Create a mock engine
    provider.snmp_engine = MagicMock()
    provider.snmp_engine.transport_dispatcher = mock_dispatcher
    
    await provider.dispose()
    
    # Verify that close_dispatcher was called
    mock_dispatcher.close_dispatcher.assert_called_once()

@pytest.mark.asyncio(loop_scope="function")
async def test_snmp_get():
    provider = SnmpProvider(MagicMock(), "test", create_test_provider())
    try:
        # Mock the MIB view controller
        mock_view_controller = MagicMock()
        mock_view_controller.get_node_name.return_value = ('SNMPv2-MIB', 'sysDescr', 0)
        provider.mib_view_controller = mock_view_controller

        result = await provider.query(
            operation='GET',
            host='demo.pysnmp.com',
            port=161,
            oid='1.3.6.1.2.1.1.1.0'  # System description
        )
        # Validate result structure and content
        assert isinstance(result, list), "Result should be a list"
        assert len(result) > 0, "Result should not be empty"
        
        # Validate first result item structure
        first_result = result[0]
        assert isinstance(first_result, dict), "Result item should be a dictionary"
        assert 'oid' in first_result, "Result should contain 'oid' key"
        assert 'value' in first_result, "Result should contain 'value' key"
        
        # Validate OID format
        assert first_result['oid'] == 'SNMPv2-MIB::sysDescr.0', "OID should match expected format"
        
        # Validate value is not empty
        assert first_result['value'], "Result value should not be empty"
    finally:
        # Ensure proper cleanup
        await provider.dispose()
        # Wait a bit for any pending tasks to complete
        await asyncio.sleep(0.1)

@pytest.mark.asyncio(loop_scope="function")
async def test_snmp_getnext():
    provider = SnmpProvider(MagicMock(), "test", create_test_provider())
    try:
        result = await provider.query(
            operation='GETNEXT',
            host='demo.pysnmp.com',
            port=161,
            oid='1.3.6.1.2.1.1.1.0'
        )
        assert result is not None
    finally:
        await provider.dispose()
        await asyncio.sleep(0.1)

@pytest.mark.asyncio(loop_scope="function")
async def test_snmp_getbulk():
    provider = SnmpProvider(MagicMock(), "test", create_test_provider())
    try:
        result = await provider.query(
            operation='GETBULK',
            host='demo.pysnmp.com',
            port=161,
            oid='1.3.6.1.2.1.1'
        )
        assert result is not None
    finally:
        await provider.dispose()
        await asyncio.sleep(0.1)

def test_mib_compiler_setup(context_manager):
    """Test MIB compiler setup"""
    # Create a temporary MIB directory with a test MIB file
    test_mib_dir = "test_mibs"
    os.makedirs(test_mib_dir, exist_ok=True)
    
    config = ProviderConfig(
        authentication={
            "snmp_version": "v2c",
            "community_string": "public",
            "listen_port": 162,
            "mib_dirs": [test_mib_dir]
        }
    )
    
    with patch('pysnmp.smi.compiler.add_mib_compiler') as mock_add_compiler:
        provider = SnmpProvider(context_manager, "test", config)
        provider._setup_mib_compiler()
        
        assert provider.mib_view_controller is not None
        mock_add_compiler.assert_called_once()
    
    # Clean up
    os.rmdir(test_mib_dir)

if __name__ == "__main__":
    pytest.main([__file__]) 