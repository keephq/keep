# keep/predictive/predictive_engine.py
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlmodel import select

from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import Alert
from keep.api.bl.enrichments_bl import EnrichmentsBl


class PredictiveEngine:
    """Упрощенный движок предиктивного анализа для Keep"""

    def __init__(self, tenant_id: str, confidence_threshold: float = 0.75):
        self.tenant_id = tenant_id
        self.confidence_threshold = confidence_threshold
        self.logger = logging.getLogger(__name__)

    def run_predictive_rules(
            self,
            events: List[AlertDto],
            session: Optional[Session] = None
    ) -> List[Dict]:
        """
        Упрощенный метод предиктивного анализа
        Возвращает список словарей с предиктивными инцидентами
        """
        predictive_incidents = []

        for event in events:
            try:
                # 1. Получаем исторические данные
                historical_alerts = self._get_simple_historical_data(event, session)

                if len(historical_alerts) < 3:  # Минимум данных
                    continue

                # 2. Простой анализ аномалий
                is_anomaly, confidence, reason = self._simple_anomaly_detection(
                    event, historical_alerts
                )

                # 3. Проверяем порог уверенности
                if is_anomaly and confidence >= self.confidence_threshold:
                    # 4. Обогащаем алерт
                    self._simple_enrich_alert(event, confidence, reason, session)

                    # 5. Создаем запись о предиктивном инциденте
                    incident_data = {
                        "type": "predictive",
                        "alert_id": event.id,
                        "alert_fingerprint": event.fingerprint,
                        "confidence": confidence,
                        "reason": reason,
                        "detected_at": datetime.utcnow().isoformat(),
                        "anomaly_type": "statistical"
                    }
                    predictive_incidents.append(incident_data)

                    self.logger.info(
                        f"Predictive anomaly detected: {reason} (confidence: {confidence:.2f})",
                        extra={
                            "alert_id": event.id,
                            "confidence": confidence,
                            "tenant_id": self.tenant_id
                        }
                    )

            except Exception as e:
                self.logger.error(
                    f"Predictive analysis error for alert {event.id}: {str(e)}"
                )
                continue

        return predictive_incidents

    def _get_simple_historical_data(self, alert: AlertDto, session: Session) -> List[Dict]:
        """Простой запрос исторических данных"""
        try:
            # За последние 24 часа
            time_window = datetime.utcnow() - timedelta(days=7)

            query = select(Alert).where(
                Alert.tenant_id == self.tenant_id,
                Alert.timestamp >= time_window,
                Alert.fingerprint != alert.fingerprint  # Исключаем текущий алерт
            ).limit(50)  # Ограничиваем для производительности

            results = session.exec(query).all()

            historical_data = []
            for result in results:
                historical_data.append(result.event)

            return historical_data

        except Exception as e:
            self.logger.error(f"Error getting historical data: {str(e)}")
            return []

    def _simple_anomaly_detection(self, current_alert: AlertDto, historical_data: List[Dict]) -> tuple:
        """
        Упрощенное обнаружение аномалий
        Возвращает: (is_anomaly, confidence, reason)
        """
        if not historical_data:
            return False, 0.0, "No historical data"

        # Простые эвристики:

        # 1. Проверяем нерабочее время
        current_time = datetime.fromisoformat(current_alert.lastReceived.replace('Z', '+00:00'))
        if current_time.hour < 6 or current_time.hour > 22:
            # Считаем сколько % исторических алертов в нерабочее время
            night_alerts = 0
            for alert in historical_data:
                alert_time = datetime.fromisoformat(alert['lastReceived'].replace('Z', '+00:00'))
                if alert_time.hour < 6 or alert_time.hour > 22:
                    night_alerts += 1

            night_ratio = night_alerts / len(historical_data)

            # Если ночных алертов мало, а текущий ночной - аномалия
            if night_ratio < 0.1:
                return True, 0.85, f"Unusual timing (night alert, night ratio: {night_ratio:.2f})"

        # 2. Проверяем критические слова в названии
        critical_words = ["CRITICAL", "EMERGENCY", "FAILED", "DOWN", "ERROR", "URGENT"]
        if any(word in current_alert.name.upper() for word in critical_words):
            # Проверяем, насколько часто такие слова встречались в истории
            critical_count = 0
            for alert in historical_data:
                if any(word in alert.get('name', '').upper() for word in critical_words):
                    critical_count += 1

            critical_ratio = critical_count / len(historical_data)
            if critical_ratio < 0.2:  # Если критических алертов было мало
                return True, 0.8, f"Critical keywords detected (critical ratio: {critical_ratio:.2f})"

        return False, 0.0, "Normal pattern"

    def _simple_enrich_alert(self, alert: AlertDto, confidence: float, reason: str, session: Session):
        """Упрощенное обогащение алерта"""
        try:
            enrichments_bl = EnrichmentsBl(self.tenant_id, session)

            enrichments = {
                "disposable_predictive_confidence": confidence,
                "disposable_predictive_reason": reason,
                "disposable_anomaly_detected": True
            }

            # Проверяем, существует ли алерт в БД
            from keep.api.core.alerts import get_last_alert_by_fingerprint

            last_alert = get_last_alert_by_fingerprint(
                self.tenant_id, alert.fingerprint, session=session
            )

            if not last_alert:
                # Алерт еще не сохранен в БД - используем enrich_entity с should_exist=False
                self.logger.debug(
                    f"Alert {alert.fingerprint} not found in DB, using enrich_entity with should_exist=False"
                )

                enrichments_bl.enrich_entity(
                    fingerprint=alert.fingerprint,
                    enrichments=enrichments,
                    action_type=ActionType.GENERIC_ENRICH,
                    action_callee="predictive_engine",
                    action_description=f"Predictive anomaly: {reason}",
                    should_exist=False,  # Ключевое изменение!
                    dispose_on_new_alert=True,
                    audit_enabled=True
                )
            else:
                # Алерт уже в БД - используем disposable_enrich_entity
                enrichments_bl.disposable_enrich_entity(
                    fingerprint=alert.fingerprint,
                    enrichments=enrichments,
                    action_type=ActionType.GENERIC_ENRICH,
                    action_callee="predictive_engine",
                    action_description=f"Predictive anomaly: {reason}",
                    audit_enabled=True
                )

            self.logger.debug(
                f"Alert {alert.fingerprint} enriched with predictive data",
                extra={"confidence": confidence, "reason": reason}
            )

        except Exception as e:
            self.logger.error(f"Error enriching alert {alert.fingerprint}: {str(e)}")