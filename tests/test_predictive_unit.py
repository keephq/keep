import pytest
from datetime import datetime
from keep.api.models.alert import AlertDto, AlertStatus, AlertSeverity
from keep.api.routes.predictive_engine import PredictiveEngine


class TestPredictiveEngineUnit:

    def test_engine_initialization(self):
        engine = PredictiveEngine(tenant_id="test-tenant")
        assert engine.tenant_id == "test-tenant"
        assert engine.confidence_threshold == 0.75

    def test_night_anomaly_detection(self):
        engine = PredictiveEngine(tenant_id="test-tenant")

        history = []
        for i in range(10):
            history.append({
                "name": "Day alert",
                "lastReceived": datetime(2024, 1, 1, 14, i, 0).isoformat() + "Z"
            })

        night_alert = AlertDto(
            id="night-1",
            name="Night alert",
            lastReceived=datetime(2024, 1, 1, 3, 0, 0).isoformat() + "Z"
        )

        is_anomaly, confidence, reason = engine._simple_anomaly_detection(
            night_alert, history
        )

        assert is_anomaly is True
        assert confidence > 0.7
        assert "night" in reason.lower() or "timing" in reason.lower()

    def test_critical_word_anomaly(self):
        engine = PredictiveEngine(tenant_id="test-tenant")

        history = []
        for i in range(10):
            history.append({"name": f"Normal alert {i}"})

        critical_alert = AlertDto(
            id="critical-1",
            name="CRITICAL: Database failure",
            lastReceived=datetime.utcnow().isoformat() + "Z"
        )

        is_anomaly, confidence, reason = engine._simple_anomaly_detection(
            critical_alert, history
        )

        assert is_anomaly is True
        assert confidence > 0.7
        assert "critical" in reason.lower()

    def test_normal_alert_no_false_positive(self):
        engine = PredictiveEngine(tenant_id="test-tenant")

        history = []
        for i in range(10):
            history.append({
                "name": f"Normal alert {i}",
                "lastReceived": datetime(2024, 1, 1, 14, i, 0).isoformat() + "Z"
            })

        normal_alert = AlertDto(
            id="normal-1",
            name="Another normal alert",
            lastReceived=datetime(2024, 1, 1, 14, 30, 0).isoformat() + "Z"
        )

        is_anomaly, confidence, reason = engine._simple_anomaly_detection(
            normal_alert, history
        )

        assert is_anomaly is False
        assert confidence < 0.3

    def test_confidence_threshold_filtering(self):
        engine_low = PredictiveEngine(tenant_id="test-tenant", confidence_threshold=0.9)
        engine_high = PredictiveEngine(tenant_id="test-tenant", confidence_threshold=0.3)

        test_result = (True, 0.6, "Test anomaly")

        should_trigger_low = test_result[0] and test_result[1] >= engine_low.confidence_threshold
        assert should_trigger_low is False

        should_trigger_high = test_result[0] and test_result[1] >= engine_high.confidence_threshold
        assert should_trigger_high is True


if __name__ == "__main__":
    print("Running PredictiveEngine unit tests...")
    tests = TestPredictiveEngineUnit()
    tests.test_engine_initialization()
    tests.test_night_anomaly_detection()
    tests.test_critical_word_anomaly()
    tests.test_normal_alert_no_false_positive()
    tests.test_confidence_threshold_filtering()
    print("All unit tests passed!")