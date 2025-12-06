import dataclasses
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class AnomalyDetectionProviderAuthConfig:
    sensitivity: float = dataclasses.field(
        default=0.1,
        metadata={
            "required": False,
            "description": "Anomaly detection sensitivity (0.01-0.5, lower = more sensitive)",
            "validation": "range:0.01,0.5",
        }
    )

    min_samples: int = dataclasses.field(
        default=10,
        metadata={
            "required": False,
            "description": "Minimum number of samples for training",
            "validation": "min:5",
        }
    )

    time_window_hours: int = dataclasses.field(
        default=24,
        metadata={
            "required": False,
            "description": "Time window for historical data analysis (hours)",
            "validation": "min:1,max:168",
        }
    )


class AnomalyDetectionProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Anomaly Detection"
    PROVIDER_CATEGORY = ["AI"]
    PROVIDER_TAGS = ["ai", "anomaly", "detection"]

    def __init__(
            self,
            context_manager: ContextManager,
            provider_id: str,
            config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self.validate_config()
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.scaler = StandardScaler()
        self.last_training_time = None

    def dispose(self):
        self.model = None
        self.scaler = None

    def validate_config(self):
        auth_config = AnomalyDetectionProviderAuthConfig(**self.config.authentication)
        self.authentication_config = auth_config
        return auth_config

    def _extract_features(self, alerts: List[AlertDto]) -> np.ndarray:
        features = []

        for alert in alerts:
            severity_str = alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity)

            severity_map = {
                "low": 1,
                "info": 2,
                "warning": 3,
                "high": 4,
                "critical": 5,
            }

            severity_num = severity_map.get(severity_str.lower(), 3)

            timestamp = datetime.fromisoformat(alert.lastReceived.replace('Z', '+00:00'))
            hour_of_day = timestamp.hour
            day_of_week = timestamp.weekday()

            hour_sin = np.sin(2 * np.pi * hour_of_day / 24)
            hour_cos = np.cos(2 * np.pi * hour_of_day / 24)

            name_length = len(alert.name) if alert.name else 0
            desc_length = len(alert.description) if alert.description else 0
            service_length = len(alert.service) if alert.service else 0

            name_upper = alert.name.upper() if alert.name else ""
            desc_upper = alert.description.upper() if alert.description else ""

            has_exclamation = (name_upper.count('!') + desc_upper.count('!')) / max(1, name_length + desc_length) * 10
            has_critical_words = sum(
                1 for word in ['CRITICAL', 'EMERGENCY', 'DOWN', 'FAILED', 'ERROR', 'URGENT', 'FULL']
                if word in name_upper or word in desc_upper)
            is_uppercase_ratio = sum(1 for c in alert.name if c.isupper()) / max(1, name_length) if alert.name else 0

            feature_vector = [
                severity_num,
                hour_sin,
                hour_cos,
                day_of_week / 6.0,
                name_length / 100.0,
                desc_length / 500.0,
                service_length / 50.0,
                has_exclamation,
                has_critical_words,
                is_uppercase_ratio,
            ]

            features.append(feature_vector)

        return np.array(features) if features else np.array([])

    def _train_model(self, features: np.ndarray):
        min_samples = getattr(self.authentication_config, 'min_samples', 10)
        sensitivity = getattr(self.authentication_config, 'sensitivity', 0.1)

        if len(features) < min_samples:
            self.logger.warning("Insufficient data for training anomaly detection model")
            return False

        if len(features) < 20:
            contamination = min(sensitivity, 0.05)
        else:
            contamination = sensitivity

        self.scaler.fit(features)
        normalized_features = self.scaler.transform(features)

        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100,
            max_samples=min(256, len(features)),
            bootstrap=False,
            n_jobs=-1
        )
        self.model.fit(normalized_features)
        self.last_training_time = datetime.now()

        self.logger.info(f"Anomaly detection model trained with {len(features)} samples, contamination={contamination}")
        return True

    def detect_anomalies(self, alerts: List[AlertDto]) -> Dict[str, Any]:
        if not alerts:
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "confidence": 0.0,
                "explanation": "No alerts provided"
            }

        features = self._extract_features(alerts)

        if len(features) < self.authentication_config.min_samples:
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "confidence": 0.0,
                "explanation": f"Insufficient data for anomaly detection (need {self.authentication_config.min_samples} samples)"
            }

        if (self.model is None or
                self.last_training_time is None or
                (datetime.now() - self.last_training_time).total_seconds() > 24 * 3600):

            training_features = features[:-1] if len(features) > self.authentication_config.min_samples else features

            if not self._train_model(training_features):
                return {
                    "is_anomaly": False,
                    "anomaly_score": 0.0,
                    "confidence": 0.0,
                    "explanation": "Model training failed"
                }

        latest_features = features[-1:].reshape(1, -1)
        normalized_features = self.scaler.transform(latest_features)

        anomaly_score = self.model.decision_function(normalized_features)[0]
        prediction = self.model.predict(normalized_features)[0]

        latest_alert = alerts[-1]

        base_threshold = -0.05 * (self.authentication_config.sensitivity / 0.1)

        if latest_alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
            severity_bonus = -0.08
        elif latest_alert.severity == AlertSeverity.WARNING:
            severity_bonus = -0.02
        elif latest_alert.severity == AlertSeverity.INFO:
            severity_bonus = 0.0
        else:
            severity_bonus = 0.01

        threshold = base_threshold + severity_bonus

        is_anomaly = (prediction == -1) or (anomaly_score < threshold)

        if anomaly_score >= 0:
            confidence = max(0.0, 0.5 - anomaly_score * 0.5)
        else:
            confidence = min(1.0, abs(anomaly_score) * 2)

        explanation = self._generate_explanation(alerts[-1], anomaly_score, is_anomaly)

        return {
            "is_anomaly": bool(is_anomaly),
            "anomaly_score": float(anomaly_score),
            "confidence": float(confidence),
            "explanation": explanation
        }

    def _generate_explanation(self, alert: AlertDto, score: float, is_anomaly: bool) -> str:
        if not is_anomaly:
            return f"Alert pattern appears normal (score: {score:.2f})"

        reasons = []

        if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
            reasons.append(f"high severity ({alert.severity})")

        timestamp = datetime.fromisoformat(alert.lastReceived.replace('Z', '+00:00'))
        if timestamp.hour < 6 or timestamp.hour > 22:
            reasons.append("unusual timing (off-hours)")

        if alert.service:
            reasons.append(f"service: {alert.service}")

        explanation = f"Anomaly detected (score: {score:.2f})"
        if reasons:
            explanation += f" - reasons: {', '.join(reasons)}"

        return explanation