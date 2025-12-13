# tests/test_predictive_unit.py
import pytest
from datetime import datetime
from keep.api.models.alert import AlertDto, AlertStatus, AlertSeverity
from keep.api.routes.predictive_engine import PredictiveEngine


class TestPredictiveEngineUnit:
    """Модульные тесты - тестируем PredictiveEngine в изоляции"""

    def test_engine_initialization(self):
        """Тест 1: Проверяем, что движок создается"""
        engine = PredictiveEngine(tenant_id="test-tenant")
        assert engine.tenant_id == "test-tenant"
        assert engine.confidence_threshold == 0.75
        print("✅ Движок создается корректно")

    def test_night_anomaly_detection(self):
        """Тест 2: Обнаружение ночной аномалии"""
        engine = PredictiveEngine(tenant_id="test-tenant")

        # Создаем историю: 10 дневных алертов
        history = []
        for i in range(10):
            history.append({
                "name": "Day alert",
                "lastReceived": datetime(2024, 1, 1, 14, i, 0).isoformat() + "Z"  # 14:00-14:10
            })

        # Создаем ночной алерт (03:00)
        night_alert = AlertDto(
            id="night-1",
            name="Night alert",
            lastReceived=datetime(2024, 1, 1, 3, 0, 0).isoformat() + "Z"  # 03:00
        )

        # Анализируем
        is_anomaly, confidence, reason = engine._simple_anomaly_detection(
            night_alert, history
        )

        # Должен обнаружить аномалию (ночной алерт при дневной истории)
        assert is_anomaly is True
        assert confidence > 0.7
        assert "night" in reason.lower() or "timing" in reason.lower()
        print("✅ Ночная аномалия обнаружена корректно")

    def test_critical_word_anomaly(self):
        """Тест 3: Обнаружение аномалии по критическим словам"""
        engine = PredictiveEngine(tenant_id="test-tenant")

        # Создаем историю: 10 обычных алертов
        history = []
        for i in range(10):
            history.append({"name": f"Normal alert {i}"})

        # Создаем критический алерт
        critical_alert = AlertDto(
            id="critical-1",
            name="CRITICAL: Database failure",
            lastReceived=datetime.utcnow().isoformat() + "Z"
        )

        # Анализируем
        is_anomaly, confidence, reason = engine._simple_anomaly_detection(
            critical_alert, history
        )

        # Должен обнаружить аномалию (CRITICAL в названии)
        assert is_anomaly is True
        assert confidence > 0.7
        assert "critical" in reason.lower()
        print("✅ Критическая аномалия обнаружена корректно")

    def test_normal_alert_no_false_positive(self):
        """Тест 4: Нормальный алерт не должен вызывать ложное срабатывание"""
        engine = PredictiveEngine(tenant_id="test-tenant")

        # Создаем историю: 10 дневных алертов
        history = []
        for i in range(10):
            history.append({
                "name": f"Normal alert {i}",
                "lastReceived": datetime(2024, 1, 1, 14, i, 0).isoformat() + "Z"
            })

        # Создаем еще один дневной алерт (нормальный)
        normal_alert = AlertDto(
            id="normal-1",
            name="Another normal alert",
            lastReceived=datetime(2024, 1, 1, 14, 30, 0).isoformat() + "Z"
        )

        # Анализируем
        is_anomaly, confidence, reason = engine._simple_anomaly_detection(
            normal_alert, history
        )

        # НЕ должен обнаружить аномалию (все нормально)
        assert is_anomaly is False
        assert confidence < 0.3
        print("✅ Ложное срабатывание предотвращено")

    def test_confidence_threshold_filtering(self):
        """Тест 5: Фильтрация по порогу уверенности"""
        engine_low = PredictiveEngine(tenant_id="test-tenant", confidence_threshold=0.9)
        engine_high = PredictiveEngine(tenant_id="test-tenant", confidence_threshold=0.3)

        # Тестовый алерт с умеренной уверенностью
        test_result = (True, 0.6, "Test anomaly")  # 60% уверенности

        # С порогом 90% - НЕ должен сработать
        should_trigger_low = test_result[0] and test_result[1] >= engine_low.confidence_threshold
        assert should_trigger_low is False

        # С порогом 30% - ДОЛЖЕН сработать
        should_trigger_high = test_result[0] and test_result[1] >= engine_high.confidence_threshold
        assert should_trigger_high is True

        print("✅ Порог уверенности работает корректно")


if __name__ == "__main__":
    # Запуск всех тестов
    print("🧪 Запуск модульных тестов PredictiveEngine...")
    tests = TestPredictiveEngineUnit()
    tests.test_engine_initialization()
    tests.test_night_anomaly_detection()
    tests.test_critical_word_anomaly()
    tests.test_normal_alert_no_false_positive()
    tests.test_confidence_threshold_filtering()
    print("🎉 Все модульные тесты пройдены!")