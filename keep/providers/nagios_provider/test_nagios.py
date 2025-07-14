import pytest
from unittest.mock import Mock
from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.nagios_provider.nagios_provider import NagiosProvider


class TestableNagiosProvider(NagiosProvider):
    """Testable version of NagiosProvider implemented abstract methods"""
    
    def dispose(self):
        pass
    
    def validate_config(self):
        return True


ALERTS_MOCK = [
    # Service alert - OK state
    {
        "host_name": "web-server-01",
        "service_description": "HTTP",
        "service_state": "OK",
        "timestamp": "2024-01-01T10:00:00Z", 
        "output": "HTTP OK: HTTP/1.1 200 OK - 1234 bytes in 0.123 second response time"
    },
    
    # Service alert - CRITICAL state 
    {
        "host_name": "db-server-01",
        "service_description": "MySQL",
        "service_state": "CRITICAL", 
        "timestamp": "2024-01-01T10:05:00Z",
        "output": "CRITICAL - Cannot connect to MySQL: Connection refused"
    },
    
    # Service alert - WARNING state
    {
        "host_name": "app-server-01", 
        "service_description": "CPU Load",
        "service_state": "WARNING",
        "timestamp": "2024-01-01T10:10:00Z",
        "output": "WARNING - load average: 5.23, 4.12, 3.55"
    },
    
    # Host alert - DOWN state
    {
        "host_name": "network-switch-01",
        "host_state": "DOWN",
        "timestamp": "2024-01-01T10:15:00Z", 
        "output": "PING CRITICAL - Packet loss = 100%"
    },
    
    # Host alert - UP state
    {
        "host_name": "firewall-01",
        "host_state": "UP", 
        "timestamp": "2024-01-01T10:20:00Z",
        "output": "PING OK - Packet loss = 0%, RTA = 0.42 ms"
    },
    
    # Host alert - UNREACHABLE state
    {
        "host_name": "remote-site-router",
        "host_state": "UNREACHABLE",
        "timestamp": "2024-01-01T10:25:00Z",
        "output": "CRITICAL - Host Unreachable"
    },
    
    # Service alert - UNKNOWN state
    {
        "host_name": "storage-server-01",
        "service_description": "Disk Space", 
        "service_state": "UNKNOWN",
        "timestamp": "2024-01-01T10:30:00Z",
        "output": "UNKNOWN - Unable to read disk statistics"
    }
]


class TestNagiosProvider:
    """Test suite for NagiosProvider"""

    @pytest.fixture
    def provider_config(self):
        """Create a test provider configuration"""
        return ProviderConfig(
            id="test-nagios",
            name="Test Nagios", 
            type="nagios",
            authentication={
                "url": "http://test.nagios.local",
                "username": "test_user",
                "password": "test_pass"
            }
        )

    @pytest.fixture
    def provider(self, provider_config):
        """Create a testable NagiosProvider instance"""
        context_manager = Mock()
        return TestableNagiosProvider(context_manager, "test-nagios", provider_config)

    def test_nagios_alerts_formatting(self, provider):
        """Test Nagios alert formatting with mock data"""
        expected_results = [
            # Service alert - OK state
            {
                "host": "web-server-01",
                "service": "HTTP",
                "severity": AlertSeverity.LOW,
                "status": AlertStatus.RESOLVED,
                "name": "HTTP"
            },
            # Service alert - CRITICAL state 
            {
                "host": "db-server-01",
                "service": "MySQL",
                "severity": AlertSeverity.HIGH,
                "status": AlertStatus.FIRING,
                "name": "MySQL"
            },
            # Service alert - WARNING state
            {
                "host": "app-server-01",
                "service": "CPU Load",
                "severity": AlertSeverity.WARNING,
                "status": AlertStatus.FIRING,
                "name": "CPU Load"
            },
            # Host alert - DOWN state
            {
                "host": "network-switch-01",
                "service": None,
                "severity": AlertSeverity.CRITICAL,
                "status": AlertStatus.FIRING,
                "name": "network-switch-01"
            },
            # Host alert - UP state
            {
                "host": "firewall-01",
                "service": None,
                "severity": AlertSeverity.LOW,
                "status": AlertStatus.RESOLVED,
                "name": "firewall-01"
            },
            # Host alert - UNREACHABLE state
            {
                "host": "remote-site-router",
                "service": None,
                "severity": AlertSeverity.CRITICAL,
                "status": AlertStatus.FIRING,
                "name": "remote-site-router"
            },
            # Service alert - UNKNOWN state
            {
                "host": "storage-server-01",
                "service": "Disk Space",
                "severity": AlertSeverity.INFO,
                "status": AlertStatus.FIRING,
                "name": "Disk Space"
            }
        ]
        
        for i, alert in enumerate(ALERTS_MOCK):
            formatted_alert = provider._format_alert(alert)
            expected = expected_results[i]
            
            # Assert key properties
            assert formatted_alert.host == expected["host"]
            assert formatted_alert.service == expected["service"]
            assert formatted_alert.severity == expected["severity"]
            assert formatted_alert.status == expected["status"]
            assert formatted_alert.name == expected["name"]
            
            # Assert other properties
            assert formatted_alert.lastReceived == alert["timestamp"]
            assert formatted_alert.description == alert["output"]
            assert formatted_alert.source == ["nagios"]
            assert formatted_alert.id is not None

    def test_severity_mapping(self, provider):
        """Test severity mapping for different states"""
        # Test service states
        service_states = {
            "OK": AlertSeverity.LOW,
            "WARNING": AlertSeverity.WARNING,
            "CRITICAL": AlertSeverity.HIGH,
            "UNKNOWN": AlertSeverity.INFO
        }
        
        for state, expected_severity in service_states.items():
            event = {"service_state": state}
            assert provider._determine_severity(event) == expected_severity
        
        # Test host states
        host_states = {
            "UP": AlertSeverity.LOW,
            "DOWN": AlertSeverity.CRITICAL,
            "UNREACHABLE": AlertSeverity.CRITICAL
        }
        
        for state, expected_severity in host_states.items():
            event = {"host_state": state}
            assert provider._determine_severity(event) == expected_severity

    def test_timestamp_validation(self, provider):
        """Test timestamp validation"""
        # Valid timestamps
        valid_timestamps = [
            "2024-01-01T10:00:00Z",
            "2024-12-31T23:59:59Z",
            "2024-06-15T12:30:45Z"
        ]
        
        for timestamp in valid_timestamps:
            assert provider._validate_timestamp(timestamp) is True
        
        # Invalid timestamps
        invalid_timestamps = [
            None,
            "",
            "invalid-timestamp",
            "2024-13-01T10:00:00Z",  # Invalid month
            "2024-01-32T10:00:00Z",  # Invalid day
        ]
        
        for timestamp in invalid_timestamps:
            assert provider._validate_timestamp(timestamp) is False

    def test_alert_id_generation(self, provider):
        """Test alert ID generation"""
        event = {
            "host_name": "test-host",
            "service_description": "test-service",
            "timestamp": "2024-01-01T10:00:00Z"
        }
        
        # Should generate consistent IDs for same event
        id1 = provider._generate_alert_id(event)
        id2 = provider._generate_alert_id(event)
        assert id1 == id2
        
        # Should generate different IDs for different events
        event2 = event.copy()
        event2["host_name"] = "different-host"
        id3 = provider._generate_alert_id(event2)
        assert id1 != id3

    def test_missing_required_fields(self, provider):
        """Test error handling for missing required fields"""
        # Missing host_name
        with pytest.raises(ValueError, match="Missing required field: host_name"):
            provider._format_alert({"timestamp": "2024-01-01T10:00:00Z"})
        
        # Missing timestamp
        with pytest.raises(ValueError, match="Invalid or missing timestamp"):
            provider._format_alert({"host_name": "test-host"})
        
        # Invalid timestamp
        with pytest.raises(ValueError, match="Invalid or missing timestamp"):
            provider._format_alert({
                "host_name": "test-host",
                "timestamp": "invalid-timestamp"
            })

    def test_provider_metadata(self):
        """Test provider metadata"""
        assert NagiosProvider.PROVIDER_DISPLAY_NAME == "Nagios"
        assert "alert" in NagiosProvider.PROVIDER_TAGS
        assert "incident" in NagiosProvider.PROVIDER_TAGS
        assert "Monitoring" in NagiosProvider.PROVIDER_CATEGORY
        assert NagiosProvider.PROVIDER_ICON == "nagios-icon.png"


def test_nagios_alerts():
    """Legacy test function for backward compatibility"""
    config = ProviderConfig(
        id="test-nagios",
        name="Test Nagios", 
        type="nagios",
        authentication={
            "url": "http://test.nagios.local",
            "username": "test_user",
            "password": "test_pass"
        }
    )
    
    provider = TestableNagiosProvider(Mock(), "test-nagios", config)
    
    for alert in ALERTS_MOCK:
        try:
            formatted_alert = provider._format_alert(alert)
            print("\nProcessing Alert:")
            print(f"Host: {formatted_alert.host}")
            print(f"Service: {formatted_alert.service or 'N/A'}")
            print(f"Severity: {formatted_alert.severity}")
            print(f"Status: {formatted_alert.status}")
            print(f"Description: {formatted_alert.description}")
        except Exception as e:
            print(f"Error processing alert: {e}")


if __name__ == "__main__":
    test_nagios_alerts()