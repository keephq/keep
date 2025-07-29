import pytest
from unittest.mock import Mock
from keep.api.models.alert import AlertSeverity, AlertStatus, AlertDto
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
        "output": "HTTP OK: HTTP/1.1 200 OK - 1234 bytes in 0.123 second response time",
    },
    # Service alert - CRITICAL state
    {
        "host_name": "db-server-01",
        "service_description": "MySQL",
        "service_state": "CRITICAL",
        "timestamp": "2024-01-01T10:05:00Z",
        "output": "CRITICAL - Cannot connect to MySQL: Connection refused",
    },
    # Service alert - WARNING state
    {
        "host_name": "app-server-01",
        "service_description": "CPU Load",
        "service_state": "WARNING",
        "timestamp": "2024-01-01T10:10:00Z",
        "output": "WARNING - load average: 5.23, 4.12, 3.55",
    },
    # Host alert - DOWN state
    {
        "host_name": "network-switch-01",
        "host_state": "DOWN",
        "timestamp": "2024-01-01T10:15:00Z",
        "output": "PING CRITICAL - Packet loss = 100%",
    },
    # Host alert - UP state
    {
        "host_name": "firewall-01",
        "host_state": "UP",
        "timestamp": "2024-01-01T10:20:00Z",
        "output": "PING OK - Packet loss = 0%, RTA = 0.42 ms",
    },
    # Host alert - UNREACHABLE state
    {
        "host_name": "remote-site-router",
        "host_state": "UNREACHABLE",
        "timestamp": "2024-01-01T10:25:00Z",
        "output": "CRITICAL - Host Unreachable",
    },
    # Service alert - UNKNOWN state
    {
        "host_name": "storage-server-01",
        "service_description": "Disk Space",
        "service_state": "UNKNOWN",
        "timestamp": "2024-01-01T10:30:00Z",
        "output": "UNKNOWN - Unable to read disk statistics",
    },
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
                "password": "test_pass",
            },
        )

    @pytest.fixture
    def provider(self, provider_config):
        """Create a testable NagiosProvider instance"""
        context_manager = Mock()
        return TestableNagiosProvider(context_manager, "test-nagios", provider_config)

    @pytest.mark.parametrize(
        "alert, expected",
        [
            (
                ALERTS_MOCK[0],
                {
                    "host": "web-server-01",
                    "service": "HTTP",
                    "severity": AlertSeverity.LOW,
                    "status": AlertStatus.RESOLVED,
                    "name": "HTTP",
                    "lastReceived": "2024-01-01T10:00:00Z",
                    "source": ["nagios"],
                    "service_state": "OK",
                    "output": "HTTP OK: HTTP/1.1 200 OK - 1234 bytes in 0.123 second response time",
                },
            ),
            (
                ALERTS_MOCK[1],
                {
                    "host": "db-server-01",
                    "service": "MySQL",
                    "severity": AlertSeverity.HIGH,
                    "status": AlertStatus.FIRING,
                    "name": "MySQL",
                    "lastReceived": "2024-01-01T10:05:00Z",
                    "source": ["nagios"],
                    "service_state": "CRITICAL",
                    "output": "CRITICAL - Cannot connect to MySQL: Connection refused",
                },
            ),
            (
                ALERTS_MOCK[2],
                {
                    "host": "app-server-01",
                    "service": "CPU Load",
                    "severity": AlertSeverity.WARNING,
                    "status": AlertStatus.FIRING,
                    "name": "CPU Load",
                    "lastReceived": "2024-01-01T10:10:00Z",
                    "source": ["nagios"],
                    "service_state": "WARNING",
                    "output": "WARNING - load average: 5.23, 4.12, 3.55",
                },
            ),
            (
                ALERTS_MOCK[3],
                {
                    "host": "network-switch-01",
                    "service": None,
                    "severity": AlertSeverity.CRITICAL,
                    "status": AlertStatus.FIRING,
                    "name": "network-switch-01",
                    "lastReceived": "2024-01-01T10:15:00Z",
                    "source": ["nagios"],
                    "host_state": "DOWN",
                    "output": "PING CRITICAL - Packet loss = 100%",
                },
            ),
            (
                ALERTS_MOCK[4],
                {
                    "host": "firewall-01",
                    "service": None,
                    "severity": AlertSeverity.LOW,
                    "status": AlertStatus.RESOLVED,
                    "name": "firewall-01",
                    "lastReceived": "2024-01-01T10:20:00Z",
                    "source": ["nagios"],
                    "host_state": "UP",
                    "output": "PING OK - Packet loss = 0%, RTA = 0.42 ms",
                },
            ),
            (
                ALERTS_MOCK[5],
                {
                    "host": "remote-site-router",
                    "service": None,
                    "severity": AlertSeverity.CRITICAL,
                    "status": AlertStatus.FIRING,
                    "name": "remote-site-router",
                    "lastReceived": "2024-01-01T10:25:00Z",
                    "source": ["nagios"],
                    "host_state": "UNREACHABLE",
                    "output": "CRITICAL - Host Unreachable",
                },
            ),
            (
                ALERTS_MOCK[6],
                {
                    "host": "storage-server-01",
                    "service": "Disk Space",
                    "severity": AlertSeverity.INFO,
                    "status": AlertStatus.FIRING,
                    "name": "Disk Space",
                    "lastReceived": "2024-01-01T10:30:00Z",
                    "source": ["nagios"],
                    "service_state": "UNKNOWN",
                    "output": "UNKNOWN - Unable to read disk statistics",
                },
            ),
        ],
    )
    def test_nagios_alerts_formatting(self, provider, alert, expected):
        """Test Nagios alert formatting with mock data using parametrization."""
        formatted_alert = provider._format_alert(alert)

        # The provider sets `description` from `output`. We should test that behavior directly.
        description = alert.get("output", "No description provided")
        expected_dto_kwargs = {
            "id": formatted_alert.id,
            "name": expected["name"],
            "status": expected["status"],
            "severity": expected["severity"],
            "lastReceived": expected["lastReceived"],
            "description": description,
            "source": expected["source"],
            "host": expected["host"],
            "service": expected["service"],
            "output": alert.get("output"),
        }

        if "service_state" in alert:
            expected_dto_kwargs["service_state"] = alert["service_state"]
        if "host_state" in alert:
            expected_dto_kwargs["host_state"] = alert["host_state"]

        expected_alert_dto = AlertDto(**expected_dto_kwargs)
        assert formatted_alert == expected_alert_dto

    @pytest.mark.parametrize(
        "state_type, state, expected_severity",
        [
            ("service_state", "OK", AlertSeverity.LOW),
            ("service_state", "WARNING", AlertSeverity.WARNING),
            ("service_state", "CRITICAL", AlertSeverity.HIGH),
            ("service_state", "UNKNOWN", AlertSeverity.INFO),
            ("host_state", "UP", AlertSeverity.LOW),
            ("host_state", "DOWN", AlertSeverity.CRITICAL),
            ("host_state", "UNREACHABLE", AlertSeverity.CRITICAL),
        ],
    )
    def test_severity_mapping(self, provider, state_type, state, expected_severity):
        """Test severity mapping for different states"""
        event = {state_type: state}
        assert provider._determine_severity(event) == expected_severity

    @pytest.mark.parametrize(
        "timestamp, expected",
        [
            ("2024-01-01T10:00:00Z", True),
            ("2024-12-31T23:59:59Z", True),
            ("2024-06-15T12:30:45Z", True),
            (None, False),
            ("", False),
            ("invalid-timestamp", False),
            ("2024-13-01T10:00:00Z", False),  # Invalid month
            ("2024-01-32T10:00:00Z", False),  # Invalid day
        ],
    )
    def test_timestamp_validation(self, provider, timestamp, expected):
        """Test timestamp validation"""
        assert provider._validate_timestamp(timestamp) is expected

    def test_alert_id_generation(self, provider):
        """Test alert ID generation for proper deduplication"""
        event1 = {
            "host_name": "test-host",
            "service_description": "test-service",
            "timestamp": "2024-01-01T10:00:00Z",
        }
        event2 = {
            "host_name": "test-host",
            "service_description": "test-service",
            "timestamp": "2024-01-01T10:05:00Z",  # Different timestamp
        }

        # Should generate consistent IDs for same event source
        id1 = provider._generate_alert_id(event1)
        id2 = provider._generate_alert_id(event2)
        assert id1 == id2

        # Should generate different IDs for different event sources
        event3 = event1.copy()
        event3["host_name"] = "different-host"
        id3 = provider._generate_alert_id(event3)
        assert id1 != id3

        event4 = event1.copy()
        event4["service_description"] = "different-service"
        id4 = provider._generate_alert_id(event4)
        assert id1 != id4

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
            provider._format_alert(
                {"host_name": "test-host", "timestamp": "invalid-timestamp"}
            )

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
            "password": "test_pass",
        },
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