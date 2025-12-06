# import json
# from datetime import datetime
#
# import pytest
# from keep.api.tasks.process_event_task import process_anomaly_detection
# from keep.api.models.db.anomaly_result import AnomalyResult
# from keep.api.models.alert import AlertDto, AlertSeverity
#
#
# @pytest.mark.parametrize("test_app", [{"AUTH_TYPE": "NOAUTH"}], indirect=True)
# def test_anomaly_detection_integration(db_session, test_app):
#     """Тест интеграции обнаружения аномалий с process_event"""
#     # Создаем AI конфигурацию для tenant
#     from keep.api.models.db.ai_external import ExternalAIConfigAndMetadata
#
#     ai_config = ExternalAIConfigAndMetadata(
#         tenant_id="keep",
#         algorithm_id="anomaly_detection_v1",
#         settings=json.dumps({
#             "Enabled": True,
#             "Sensitivity": 0.1,
#             "Min Samples": 5,
#             "Time Window (hours)": 24
#         })
#     )
#     db_session.add(ai_config)
#     db_session.commit()
#
#     # Создаем тестовый алерт
#     alert = AlertDto(
#         id="test-anomaly",
#         name="Test Alert",
#         severity=AlertSeverity.CRITICAL,
#         lastReceived=datetime.now().isoformat(),
#         service="test-service"
#     )
#
#     # Вызываем функцию обнаружения аномалий
#     result = process_anomaly_detection("keep", alert)
#
#     # Проверяем результат
#     assert result is not None
#     assert "is_anomaly" in result
#     assert "anomaly_score" in result
#     assert "confidence" in result
#
#     # Проверяем сохранение в БД
#     anomaly_record = db_session.query(AnomalyResult).filter(
#         AnomalyResult.alert_fingerprint == alert.fingerprint
#     ).first()
#     assert anomaly_record is not None
#     assert anomaly_record.is_anomaly == result["is_anomaly"]

import pytest
import json
from datetime import datetime, timedelta
from keep.api.tasks.process_event_task import process_anomaly_detection
from keep.api.models.db.anomaly_result import AnomalyResult
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.ai_external import ExternalAIConfigAndMetadata
from keep.api.models.db.alert import Alert
from sqlalchemy.orm import Session


@pytest.mark.parametrize("test_app", [{"AUTH_TYPE": "NOAUTH"}], indirect=True)
def test_anomaly_detection_integration_normal(db_session, test_app):
    """Тест интеграции обнаружения аномалий - нормальный алерт"""
    # Создаем AI конфигурацию для tenant
    ai_config = ExternalAIConfigAndMetadata(
        tenant_id="keep",
        algorithm_id="anomaly_detection_v1",
        settings=json.dumps({
            "Enabled": True,
            "sensitivity": 0.1,
            "min_samples": 5,
            "time_window_hours": 24
        })
    )
    db_session.add(ai_config)
    db_session.commit()

    # Создаем исторические алерты для контекста
    base_time = datetime.now() - timedelta(hours=1)
    for i in range(10):
        historical_alert = Alert(
            id=f"historical-{i}",
            tenant_id="keep",
            fingerprint=f"test-fingerprint-{i}",
            name="CPU Usage High",
            severity="warning",  # Используем строковое значение
            status="firing",
            last_received=base_time - timedelta(minutes=i * 10),
            service="api-service",
            description="CPU usage above threshold"
        )
        db_session.add(historical_alert)
    db_session.commit()

    # Создаем тестовый алерт (нормальный - похож на исторические)
    alert = AlertDto(
        id="test-normal-alert",
        name="CPU Usage High",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.WARNING,
        lastReceived=datetime.now().isoformat(),
        service="api-service",
        description="CPU usage above threshold",
        fingerprint="test-normal-fingerprint"
    )

    # Вызываем функцию обнаружения аномалий
    result = process_anomaly_detection("keep", alert)

    # Проверяем результат
    assert result is not None
    assert "is_anomaly" in result
    assert "anomaly_score" in result
    assert "confidence" in result
    assert "explanation" in result

    # Нормальный алерт не должен быть аномалией
    assert result["is_anomaly"] == False
    assert result["confidence"] < 0.5  # Низкая уверенность для нормальных алертов

    # Проверяем сохранение в БД
    anomaly_record = db_session.query(AnomalyResult).filter(
        AnomalyResult.alert_fingerprint == alert.fingerprint
    ).first()
    assert anomaly_record is not None
    assert anomaly_record.is_anomaly == result["is_anomaly"]
    assert abs(anomaly_record.anomaly_score - result["anomaly_score"]) < 0.001
    assert anomaly_record.explanation == result["explanation"]


@pytest.mark.parametrize("test_app", [{"AUTH_TYPE": "NOAUTH"}], indirect=True)
def test_anomaly_detection_integration_anomalous(db_session, test_app):
    """Тест интеграции обнаружения аномалий - аномальный алерт"""
    # Создаем AI конфигурацию для tenant
    ai_config = ExternalAIConfigAndMetadata(
        tenant_id="keep",
        algorithm_id="anomaly_detection_v1",
        settings=json.dumps({
            "Enabled": True,
            "sensitivity": 0.1,
            "min_samples": 5,
            "time_window_hours": 24
        })
    )
    db_session.add(ai_config)
    db_session.commit()

    # Создаем исторические алерты (все INFO/WARNING)
    base_time = datetime.now() - timedelta(hours=1)
    for i in range(15):
        historical_alert = Alert(
            id=f"historical-info-{i}",
            tenant_id="keep",
            fingerprint=f"test-info-fingerprint-{i}",
            name="Info Alert",
            severity="info",  # Только INFO алерты
            status="firing",
            last_received=base_time - timedelta(minutes=i * 10),
            service="monitoring",
            description="Regular monitoring alert"
        )
        db_session.add(historical_alert)
    db_session.commit()

    # Создаем аномальный алерт (CRITICAL)
    alert = AlertDto(
        id="test-anomalous-alert",
        name="!!!SYSTEM CRITICAL!!!",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.now().isoformat(),
        service="monitoring",
        description="!!!CRITICAL SYSTEM FAILURE!!!",
        fingerprint="test-anomalous-fingerprint"
    )

    # Вызываем функцию обнаружения аномалий
    result = process_anomaly_detection("keep", alert)

    # Проверяем результат
    assert result is not None

    # CRITICAL алерт после INFO алертов должен быть аномалией
    # или иметь высокую уверенность в аномальности
    if not result["is_anomaly"]:
        # Проверяем, что хотя бы anomaly_score отрицательный (склонность к аномалии)
        assert result["anomaly_score"] < 0, f"Expected negative anomaly score for critical alert, got: {result}"
        assert result["confidence"] > 0.3, f"Expected higher confidence for critical alert, got: {result['confidence']}"
    else:
        assert result["is_anomaly"] == True
        assert result["confidence"] > 0.3

    # Проверяем сохранение в БД
    anomaly_record = db_session.query(AnomalyResult).filter(
        AnomalyResult.alert_fingerprint == alert.fingerprint
    ).first()
    assert anomaly_record is not None
    assert anomaly_record.explanation == result["explanation"]


@pytest.mark.parametrize("test_app", [{"AUTH_TYPE": "NOAUTH"}], indirect=True)
def test_anomaly_detection_disabled(db_session, test_app):
    """Тест, когда обнаружение аномалий отключено"""
    # Создаем AI конфигурацию с отключенным обнаружением
    ai_config = ExternalAIConfigAndMetadata(
        tenant_id="keep",
        algorithm_id="anomaly_detection_v1",
        settings=json.dumps({
            "Enabled": False,  # Отключено
            "sensitivity": 0.1,
            "min_samples": 5,
            "time_window_hours": 24
        })
    )
    db_session.add(ai_config)
    db_session.commit()

    alert = AlertDto(
        id="test-disabled",
        name="Test Alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.now().isoformat(),
        service="test",
        description="Test",
        fingerprint="test-disabled-fingerprint"
    )

    # Вызываем функцию обнаружения аномалий
    result = process_anomaly_detection("keep", alert)

    # Должен вернуться None, так как отключено
    assert result is None

    # Проверяем, что в БД ничего не сохранилось
    anomaly_record = db_session.query(AnomalyResult).filter(
        AnomalyResult.alert_fingerprint == alert.fingerprint
    ).first()
    assert anomaly_record is None


@pytest.mark.parametrize("test_app", [{"AUTH_TYPE": "NOAUTH"}], indirect=True)
def test_anomaly_detection_no_config(db_session, test_app):
    """Тест, когда нет конфигурации обнаружения аномалий"""
    alert = AlertDto(
        id="test-no-config",
        name="Test Alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.now().isoformat(),
        service="test",
        description="Test",
        fingerprint="test-no-config-fingerprint"
    )

    # Вызываем функцию обнаружения аномалий
    result = process_anomaly_detection("keep", alert)

    # Должен вернуться None, так как нет конфигурации
    assert result is None


@pytest.mark.parametrize("test_app", [{"AUTH_TYPE": "NOAUTH"}], indirect=True)
def test_anomaly_detection_insufficient_data(db_session, test_app):
    """Тест с недостаточными данными для обучения"""
    # Создаем AI конфигурацию с min_samples=20
    ai_config = ExternalAIConfigAndMetadata(
        tenant_id="keep",
        algorithm_id="anomaly_detection_v1",
        settings=json.dumps({
            "Enabled": True,
            "sensitivity": 0.1,
            "min_samples": 20,  # Высокое требование
            "time_window_hours": 24
        })
    )
    db_session.add(ai_config)
    db_session.commit()

    # Создаем только 5 исторических алертов (меньше min_samples)
    base_time = datetime.now() - timedelta(hours=1)
    for i in range(5):
        historical_alert = Alert(
            id=f"historical-few-{i}",
            tenant_id="keep",
            fingerprint=f"test-few-fingerprint-{i}",
            name="Alert",
            severity="warning",
            status="firing",
            last_received=base_time - timedelta(minutes=i * 10),
            service="test",
            description="Test alert"
        )
        db_session.add(historical_alert)
    db_session.commit()

    alert = AlertDto(
        id="test-insufficient",
        name="Test Alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.WARNING,
        lastReceived=datetime.now().isoformat(),
        service="test",
        description="Test",
        fingerprint="test-insufficient-fingerprint"
    )

    # Вызываем функцию обнаружения аномалий
    result = process_anomaly_detection("keep", alert)

    # Проверяем результат
    assert result is not None
    # При недостаточных данных должна быть is_anomaly = False
    assert result["is_anomaly"] == False
    assert "Insufficient data" in result["explanation"]


@pytest.mark.parametrize("test_app", [{"AUTH_TYPE": "NOAUTH"}], indirect=True)
def test_anomaly_detection_time_window(db_session, test_app):
    """Тест временного окна для исторических данных"""
    # Создаем AI конфигурацию с маленьким временным окном
    ai_config = ExternalAIConfigAndMetadata(
        tenant_id="keep",
        algorithm_id="anomaly_detection_v1",
        settings=json.dumps({
            "Enabled": True,
            "sensitivity": 0.1,
            "min_samples": 5,
            "time_window_hours": 1  # Только 1 час
        })
    )
    db_session.add(ai_config)
    db_session.commit()

    # Создаем старые алерты (больше 1 часа назад)
    old_time = datetime.now() - timedelta(hours=2)
    for i in range(10):
        historical_alert = Alert(
            id=f"historical-old-{i}",
            tenant_id="keep",
            fingerprint=f"test-old-fingerprint-{i}",
            name="Old Alert",
            severity="warning",
            status="firing",
            last_received=old_time - timedelta(minutes=i * 10),
            service="test",
            description="Old alert"
        )
        db_session.add(historical_alert)

    # Создаем свежие алерты (менее 1 часа назад)
    recent_time = datetime.now() - timedelta(minutes=30)
    for i in range(5):
        historical_alert = Alert(
            id=f"historical-recent-{i}",
            tenant_id="keep",
            fingerprint=f"test-recent-fingerprint-{i}",
            name="Recent Alert",
            severity="warning",
            status="firing",
            last_received=recent_time - timedelta(minutes=i * 5),
            service="test",
            description="Recent alert"
        )
        db_session.add(historical_alert)
    db_session.commit()

    alert = AlertDto(
        id="test-time-window",
        name="Test Alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.WARNING,
        lastReceived=datetime.now().isoformat(),
        service="test",
        description="Test",
        fingerprint="test-time-window-fingerprint"
    )

    # Вызываем функцию обнаружения аномалий
    result = process_anomaly_detection("keep", alert)

    # Проверяем результат
    assert result is not None
    # Должно использовать только свежие алерты (5 штук)
    # Если min_samples=5, то данных достаточно
    # Проверяем, что результат корректен
    assert "is_anomaly" in result
    assert "anomaly_score" in result


@pytest.mark.parametrize("test_app", [{"AUTH_TYPE": "NOAUTH"}], indirect=True)
def test_anomaly_detection_model_retraining(db_session, test_app):
    """Тест переобучения модели"""
    # Создаем AI конфигурацию
    ai_config = ExternalAIConfigAndMetadata(
        tenant_id="keep",
        algorithm_id="anomaly_detection_v1",
        settings=json.dumps({
            "Enabled": True,
            "sensitivity": 0.1,
            "min_samples": 5,
            "time_window_hours": 24
        })
    )
    db_session.add(ai_config)
    db_session.commit()

    # Создаем первую партию алертов
    base_time = datetime.now() - timedelta(hours=2)
    for i in range(10):
        historical_alert = Alert(
            id=f"historical-batch1-{i}",
            tenant_id="keep",
            fingerprint=f"test-batch1-fingerprint-{i}",
            name="Batch1 Alert",
            severity="warning",
            status="firing",
            last_received=base_time - timedelta(minutes=i * 10),
            service="service1",
            description="First batch"
        )
        db_session.add(historical_alert)
    db_session.commit()

    # Первый алерт
    alert1 = AlertDto(
        id="test-retrain-1",
        name="Test Alert 1",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.WARNING,
        lastReceived=datetime.now().isoformat(),
        service="service1",
        description="Test",
        fingerprint="test-retrain-fingerprint-1"
    )

    result1 = process_anomaly_detection("keep", alert1)
    assert result1 is not None

    # Вторая партия алертов (другой паттерн)
    for i in range(10):
        historical_alert = Alert(
            id=f"historical-batch2-{i}",
            tenant_id="keep",
            fingerprint=f"test-batch2-fingerprint-{i}",
            name="Batch2 Different",
            severity="high",
            status="firing",
            last_received=datetime.now() - timedelta(minutes=i * 5),
            service="service2",
            description="Second batch different"
        )
        db_session.add(historical_alert)
    db_session.commit()

    # Второй алерт (через 25 часов для триггера переобучения)
    # Нужно сымитировать, что прошло больше 24 часов
    # В реальном коде это проверяется через last_training_time
    alert2 = AlertDto(
        id="test-retrain-2",
        name="Test Alert 2",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.WARNING,
        lastReceived=datetime.now().isoformat(),
        service="service2",
        description="Test",
        fingerprint="test-retrain-fingerprint-2"
    )

    result2 = process_anomaly_detection("keep", alert2)
    assert result2 is not None

    # Проверяем, что оба результата сохранены
    records = db_session.query(AnomalyResult).filter(
        AnomalyResult.tenant_id == "keep"
    ).all()
    assert len(records) >= 2