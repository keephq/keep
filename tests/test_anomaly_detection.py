import pytest
import numpy as np
from datetime import datetime, timedelta, timezone
from keep.providers.anomaly_detection_provider.anomaly_detection_provider import (
    AnomalyDetectionProvider,
    AnomalyDetectionProviderAuthConfig,
)
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig


def test_anomaly_detection_provider_normal_alert():
    context_manager = ContextManager(tenant_id="test")
    config = ProviderConfig(
        authentication={"sensitivity": 0.1, "min_samples": 5}
    )
    provider = AnomalyDetectionProvider(context_manager, "test", config)

    alerts = []
    base_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

    for i in range(15):
        hour = 10 + (i % 8)
        alert = AlertDto(
            id=f"alert-{i}",
            name="CPU High",
            severity=AlertSeverity.WARNING,
            lastReceived=(base_time + timedelta(hours=i)).replace(hour=hour).isoformat(),
            service="api-server",
            description="CPU usage is high"
        )
        alerts.append(alert)

    result = provider.detect_anomalies(alerts)

    print(f"DEBUG normal alert test:")
    print(f"  anomaly_score: {result['anomaly_score']}")
    print(f"  confidence: {result['confidence']}")
    print(f"  explanation: {result['explanation']}")

    assert result["is_anomaly"] == False, f"Expected no anomaly, but got: {result}"
    assert result["confidence"] < 0.5, f"Confidence too high for normal alert: {result['confidence']}"


def test_anomaly_detection_provider_anomalous_alert():
    context_manager = ContextManager(tenant_id="test")
    config = ProviderConfig(
        authentication={"sensitivity": 0.1, "min_samples": 10}
    )
    provider = AnomalyDetectionProvider(context_manager, "test", config)

    alerts = []
    base_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

    for i in range(15):
        alert = AlertDto(
            id=f"alert-{i}",
            name="CPU Usage High",
            severity=AlertSeverity.WARNING,
            lastReceived=(base_time + timedelta(hours=i)).replace(hour=10 + (i % 8)).isoformat(),
            service="api-service",
            description="CPU usage above 80% threshold"
        )
        alerts.append(alert)

    anomalous_alert = AlertDto(
        id="alert-anomalous",
        name="!!!DISK FULL!!! CRITICAL EMERGENCY !!!",
        severity=AlertSeverity.CRITICAL,
        lastReceived=(base_time + timedelta(days=1, hours=3)).isoformat(),
        service="storage-cluster",
        description="!!!DISK 99.9% FULL!!! SYSTEM MAY CRASH!!! IMMEDIATE ACTION REQUIRED!!! URGENT!!!"
    )
    alerts.append(anomalous_alert)

    result = provider.detect_anomalies(alerts)

    print(f"DEBUG anomalous alert test:")
    print(f"  anomaly_score: {result['anomaly_score']}")
    print(f"  confidence: {result['confidence']}")
    print(f"  explanation: {result['explanation']}")

    assert result["is_anomaly"] == True, \
        f"Expected anomaly detection. Got: {result}"


def test_anomaly_detection_provider_feature_extraction():
    context_manager = ContextManager(tenant_id="test")
    config = ProviderConfig(
        authentication={"sensitivity": 0.1, "min_samples": 5}
    )
    provider = AnomalyDetectionProvider(context_manager, "test", config)

    alerts = [
        AlertDto(
            id="test1",
            name="Short",
            severity=AlertSeverity.CRITICAL,
            lastReceived=datetime.now().replace(hour=14).isoformat(),
            service="srv",
            description="Desc"
        ),
        AlertDto(
            id="test2",
            name="Very Long Alert Name Here",
            severity=AlertSeverity.INFO,
            lastReceived=datetime.now().replace(hour=3).isoformat(),
            service="very-long-service-name",
            description="Very long description text for testing purposes"
        )
    ]

    features = provider._extract_features(alerts)

    assert features.shape == (2, 10), f"Expected shape (2, 10), got {features.shape}"

    assert features[0][0] == 5
    expected_hour_sin_14 = np.sin(2 * np.pi * 14 / 24)
    assert abs(features[0][1] - expected_hour_sin_14) < 0.001
    expected_hour_cos_14 = np.cos(2 * np.pi * 14 / 24)
    assert abs(features[0][2] - expected_hour_cos_14) < 0.001
    assert abs(features[0][4] - 0.05) < 0.001

    assert features[1][0] == 2
    expected_hour_sin_3 = np.sin(2 * np.pi * 3 / 24)
    assert abs(features[1][1] - expected_hour_sin_3) < 0.001
    assert abs(features[1][4] - 0.23) < 0.001


def test_anomaly_detection_provider_severity_escalation():
    context_manager = ContextManager(tenant_id="test")
    config = ProviderConfig(
        authentication={"sensitivity": 0.1, "min_samples": 10}
    )
    provider = AnomalyDetectionProvider(context_manager, "test", config)

    alerts = []
    base_time = datetime.now()

    for i in range(15):
        alert = AlertDto(
            id=f"alert-{i}",
            name=f"Info Alert {i}",
            severity=AlertSeverity.INFO,
            lastReceived=(base_time + timedelta(hours=i)).isoformat(),
            service="monitoring",
            description=f"Regular info alert {i}"
        )
        alerts.append(alert)

    critical_alert = AlertDto(
        id="alert-critical",
        name="!!!SYSTEM CRITICAL!!!",
        severity=AlertSeverity.CRITICAL,
        lastReceived=(base_time + timedelta(hours=16)).replace(hour=2).isoformat(),
        service="monitoring",
        description="!!!CRITICAL SYSTEM FAILURE!!!"
    )
    alerts.append(critical_alert)

    result = provider.detect_anomalies(alerts)

    assert result["is_anomaly"] == True, \
        f"Expected severity escalation detection. Got: {result}"
    assert result["confidence"] > 0.3, \
        f"Expected confidence > 0.3 for critical alert, got: {result['confidence']}"


def test_anomaly_detection_provider_insufficient_data():
    context_manager = ContextManager(tenant_id="test")
    config = ProviderConfig(
        authentication={"sensitivity": 0.1, "min_samples": 10}
    )
    provider = AnomalyDetectionProvider(context_manager, "test", config)

    alerts = []
    base_time = datetime.now()
    for i in range(3):
        alert = AlertDto(
            id=f"alert-{i}",
            name="Test Alert",
            severity=AlertSeverity.INFO,
            lastReceived=(base_time + timedelta(hours=i)).isoformat(),
            service="test",
            description="Test"
        )
        alerts.append(alert)

    result = provider.detect_anomalies(alerts)
    assert result["is_anomaly"] == False
    assert "Insufficient data" in result["explanation"]


def test_anomaly_detection_provider_empty_alerts():
    context_manager = ContextManager(tenant_id="test")
    config = ProviderConfig(
        authentication={"sensitivity": 0.1, "min_samples": 5}
    )
    provider = AnomalyDetectionProvider(context_manager, "test", config)

    alerts = []
    result = provider.detect_anomalies(alerts)
    assert result["is_anomaly"] == False
    assert "No alerts provided" in result["explanation"]


def test_anomaly_detection_provider_time_anomaly():
    context_manager = ContextManager(tenant_id="test")
    config = ProviderConfig(
        authentication={"sensitivity": 0.1, "min_samples": 15}
    )
    provider = AnomalyDetectionProvider(context_manager, "test", config)

    alerts = []
    base_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    for i in range(25):
        hour = 9 + (i % 9)
        day_offset = i // 9

        alert = AlertDto(
            id=f"alert-{i}",
            name="Working Hours Alert",
            severity=AlertSeverity.HIGH,
            lastReceived=(base_time + timedelta(days=day_offset, hours=hour)).isoformat(),
            service="production",
            description="Alert during normal working hours"
        )
        alerts.append(alert)

    night_alert = AlertDto(
        id="alert-night",
        name="Night Emergency",
        severity=AlertSeverity.HIGH,
        lastReceived=(base_time + timedelta(days=3, hours=3)).isoformat(),
        service="production",
        description="Critical alert at 3 AM - unusual timing"
    )
    alerts.append(night_alert)

    result = provider.detect_anomalies(alerts)

    is_anomaly_detected = result["is_anomaly"]
    has_low_score = result["anomaly_score"] < 0

    assert is_anomaly_detected or has_low_score, \
        f"Expected time anomaly detection. Got: is_anomaly={is_anomaly_detected}, score={result['anomaly_score']}"


def test_anomaly_detection_provider_severity_escalation():
    context_manager = ContextManager(tenant_id="test")
    config = ProviderConfig(
        authentication={"sensitivity": 0.05, "min_samples": 10}
    )
    provider = AnomalyDetectionProvider(context_manager, "test", config)

    alerts = []
    base_time = datetime.now()

    for i in range(20):
        alert = AlertDto(
            id=f"alert-{i}",
            name=f"Info Alert {i}",
            severity=AlertSeverity.INFO,
            lastReceived=(base_time + timedelta(hours=i)).isoformat(),
            service="monitoring-system",
            description=f"Informational alert number {i}"
        )
        alerts.append(alert)

    critical_alert = AlertDto(
        id="alert-critical",
        name="!!!SYSTEM DOWN!!! CRITICAL EMERGENCY!!!",
        severity=AlertSeverity.CRITICAL,
        lastReceived=(base_time + timedelta(hours=22)).isoformat(),
        service="core-database",
        description="!!!CRITICAL: ENTIRE DATABASE SYSTEM IS DOWN!!! ALL SERVICES OFFLINE!!! URGENT!!!"
    )
    alerts.append(critical_alert)

    result = provider.detect_anomalies(alerts)

    print(f"DEBUG severity escalation test:")
    print(f"  anomaly_score: {result['anomaly_score']}")
    print(f"  confidence: {result['confidence']}")
    print(f"  explanation: {result['explanation']}")

    assert result["is_anomaly"] == True, \
        f"Expected severity escalation detection. Got: {result}"

def test_anomaly_detection_provider_model_retraining():
    context_manager = ContextManager(tenant_id="test")
    config = ProviderConfig(
        authentication={"sensitivity": 0.1, "min_samples": 10}
    )
    provider = AnomalyDetectionProvider(context_manager, "test", config)

    alerts_batch1 = []
    base_time = datetime.now() - timedelta(days=1)
    for i in range(15):
        alert = AlertDto(
            id=f"alert-batch1-{i}",
            name="Batch1 Normal Alert",
            severity=AlertSeverity.WARNING,
            lastReceived=(base_time + timedelta(hours=i)).isoformat(),
            service="service1",
            description="First batch normal pattern"
        )
        alerts_batch1.append(alert)

    result1 = provider.detect_anomalies(alerts_batch1)

    provider.last_training_time = datetime.now() - timedelta(days=2)

    alerts_batch2 = []
    current_time = datetime.now()
    for i in range(15):
        alert = AlertDto(
            id=f"alert-batch2-{i}",
            name="Batch2 Different Pattern Alert",
            severity=AlertSeverity.HIGH,
            lastReceived=(current_time + timedelta(hours=i)).isoformat(),
            service="service2",
            description="Second batch with different pattern characteristics"
        )
        alerts_batch2.append(alert)

    result2 = provider.detect_anomalies(alerts_batch2)

    assert provider.model is not None


def test_anomaly_detection_provider_config_validation():
    context_manager = ContextManager(tenant_id="test")

    config1 = ProviderConfig(
        authentication={"sensitivity": 0.01, "min_samples": 5, "time_window_hours": 1}
    )
    provider1 = AnomalyDetectionProvider(context_manager, "test1", config1)
    assert provider1.authentication_config.sensitivity == 0.01
    assert provider1.authentication_config.min_samples == 5

    config2 = ProviderConfig(
        authentication={"sensitivity": 0.5, "min_samples": 100, "time_window_hours": 168}
    )
    provider2 = AnomalyDetectionProvider(context_manager, "test2", config2)
    assert provider2.authentication_config.sensitivity == 0.5
    assert provider2.authentication_config.min_samples == 100


def test_anomaly_detection_provider_feature_extraction():
    context_manager = ContextManager(tenant_id="test")
    config = ProviderConfig(
        authentication={"sensitivity": 0.1, "min_samples": 5}
    )
    provider = AnomalyDetectionProvider(context_manager, "test", config)

    now = datetime.now(timezone.utc)
    time1 = now.replace(hour=14, minute=0, second=0, microsecond=0)
    time2 = now.replace(hour=3, minute=0, second=0, microsecond=0)

    alerts = [
        AlertDto(
            id="test1",
            name="Short",
            severity=AlertSeverity.CRITICAL,
            lastReceived=time1.isoformat(),
            service="srv",
            description="Desc"
        ),
        AlertDto(
            id="test2",
            name="Very Long Alert Name Here",
            severity=AlertSeverity.INFO,
            lastReceived=time2.isoformat(),
            service="very-long-service-name",
            description="Very long description text for testing purposes"
        )
    ]

    features = provider._extract_features(alerts)

    assert features.shape == (2, 10), f"Expected shape (2, 10), got {features.shape}"
    print(f"ISO format check:")
    print(f"time1: {time1}, iso: {time1.isoformat()}")
    print(f"Parsed back: {datetime.fromisoformat(time1.isoformat())}")

    print(f"Features[0]: {features[0]}")
    print(f"Features[1]: {features[1]}")

    assert features[0][0] == 5.0, f"CRITICAL severity should be 5.0, got {features[0][0]}"

    expected_hour_sin_14 = np.sin(2 * np.pi * 14 / 24)
    expected_hour_cos_14 = np.cos(2 * np.pi * 14 / 24)

    print(f"Expected for 14h: sin={expected_hour_sin_14}, cos={expected_hour_cos_14}")
    print(f"Actual for alert 1: sin={features[0][1]}, cos={features[0][2]}")

    tolerance = 0.0001

    assert abs(features[0][1] - expected_hour_sin_14) < tolerance, \
        f"hour_sin for 14h: expected {expected_hour_sin_14}, got {features[0][1]}"

    assert abs(features[0][2] - expected_hour_cos_14) < tolerance, \
        f"hour_cos for 14h: expected {expected_hour_cos_14}, got {features[0][2]}"

    assert abs(features[0][4] - 0.05) < tolerance

    assert features[1][0] == 2.0, f"INFO severity should be 2.0, got {features[1][0]}"

    expected_hour_sin_3 = np.sin(2 * np.pi * 3 / 24)
    expected_hour_cos_3 = np.cos(2 * np.pi * 3 / 24)

    print(f"Expected for 3h: sin={expected_hour_sin_3}, cos={expected_hour_cos_3}")
    print(f"Actual for alert 2: sin={features[1][1]}, cos={features[1][2]}")

    assert abs(features[1][1] - expected_hour_sin_3) < tolerance, \
        f"hour_sin for 3h: expected {expected_hour_sin_3}, got {features[1][1]}"

    assert abs(features[1][2] - expected_hour_cos_3) < tolerance, \
        f"hour_cos for 3h: expected {expected_hour_cos_3}, got {features[1][2]}"

    assert abs(features[0][7]) < tolerance, f"has_exclamation should be 0, got: {features[0][7]}"
    assert abs(features[1][7]) < tolerance, f"has_exclamation should be 0, got: {features[1][7]}"

    assert features[0][8] == 0, f"has_critical_words should be 0, got: {features[0][8]}"
    assert features[1][8] == 0, f"has_critical_words should be 0, got: {features[1][8]}"

    assert abs(features[0][9] - 0.2) < tolerance, f"uppercase_ratio for 'Short': expected 0.2, got {features[0][9]}"


if __name__ == "__main__":
    import sys

    tests = [
        ("Normal Alert", test_anomaly_detection_provider_normal_alert),
        ("Anomalous Alert", test_anomaly_detection_provider_anomalous_alert),
        ("Insufficient Data", test_anomaly_detection_provider_insufficient_data),
        ("Empty Alerts", test_anomaly_detection_provider_empty_alerts),
        ("Time Anomaly", test_anomaly_detection_provider_time_anomaly),
        ("Severity Escalation", test_anomaly_detection_provider_severity_escalation),
        ("Model Retraining", test_anomaly_detection_provider_model_retraining),
        ("Config Validation", test_anomaly_detection_provider_config_validation),
        ("Feature Extraction", test_anomaly_detection_provider_feature_extraction),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ {name} passed")
            passed += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)