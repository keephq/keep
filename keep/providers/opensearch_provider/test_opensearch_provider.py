from keep.providers.opensearch_provider.opensearch_provider import (
    OpensearchProvider,
    OpensearchProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig

def test_opensearch_provider_format_alert():
    event = {
        "monitor_id": "monitor-1",
        "monitor_name": "Error Rate Monitor",
        "trigger_name": "Trigger 1",
        "state": "ACTIVE",
        "severity": "1",
        "message": "Logs indicate high errors"
    }
    
    alert_dto = OpensearchProvider._format_alert(event)
    
    assert alert_dto.name == "Error Rate Monitor"
    assert alert_dto.description == "Logs indicate high errors"
    assert alert_dto.status == "firing"
    assert alert_dto.severity == "critical"
    assert alert_dto.source == ["opensearch"]

def test_opensearch_provider_format_resolved_alert():
    event = {
        "monitor_id": "monitor-1",
        "monitor_name": "Error Rate Monitor",
        "state": "COMPLETED",
        "severity": "3"
    }
    
    alert_dto = OpensearchProvider._format_alert(event)
    
    assert alert_dto.status == "resolved"

def test_opensearch_provider_config():
    config = ProviderConfig(
        id="opensearch-test",
        authentication={"api_key": "dummy_key"},
    )
    provider = OpensearchProvider(context_manager=None, provider_id="opensearch-test", config=config)
    provider.validate_config()
    assert provider.authentication_config.api_key == "dummy_key"
