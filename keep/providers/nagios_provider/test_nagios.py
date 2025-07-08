from nagios_provider import NagiosProvider
from keep.providers.models.provider_config import ProviderConfig

from ALERT_MOCK import ALERTS_MOCK

def test_nagios_alerts():
    config = ProviderConfig(
        id="test-nagios",
        name="Test Nagios",
        type="nagios"
    )
    
    provider = NagiosProvider(None, "test-nagios", config)
    
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