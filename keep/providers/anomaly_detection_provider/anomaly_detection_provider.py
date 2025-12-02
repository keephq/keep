"""
Anomaly Detection Provider for proactive alert analysis with minimal false positives.
"""
import dataclasses
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import pydantic
import pandas as pd

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class AnomalyDetectionProviderAuthConfig:
    """Anomaly Detection provider configuration."""

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
    """Provider for detecting anomalies in alert patterns."""

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
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.scaler = StandardScaler()
        self.last_training_time = None

    def dispose(self):
        """Clean up resources."""
        self.model = None
        self.scaler = None

    def validate_config(self):
        """Validate provider configuration."""
        auth_config = AnomalyDetectionProviderAuthConfig(**self.authentication_config)
        return auth_config

    def _extract_features(self, alerts: List[AlertDto]) -> np.ndarray:
        """Extract numerical features from alerts for ML processing."""
        features = []

        for alert in alerts:
            # Convert severity to numerical value
            severity_map = {
                AlertSeverity.LOW: 1,
                AlertSeverity.INFO: 2,
                AlertSeverity.WARNING: 3,
                AlertSeverity.HIGH: 4,
                AlertSeverity.CRITICAL: 5,
            }

            # Time-based features
            timestamp = datetime.fromisoformat(alert.lastReceived.replace('Z', '+00:00'))
            hour_of_day = timestamp.hour
            day_of_week = timestamp.weekday()

            # Alert features
            feature_vector = [
                severity_map.get(alert.severity, 3),
                hour_of_day,
                day_of_week,
                len(alert.name) if alert.name else 0,
                len(alert.description) if alert.description else 0,
                len(alert.service) if alert.service else 0,
            ]

            features.append(feature_vector)

        return np.array(features) if features else np.array([])

    def _train_model(self, features: np.ndarray):
        """Train the Isolation Forest model."""
        if len(features) < self.authentication_config.get("min_samples", 10):
            self.logger.warning("Insufficient data for training anomaly detection model")
            return False

            # Normalize features
        self.scaler.fit(features)
        normalized_features = self.scaler.transform(features)

        # Train Isolation Forest
        contamination = self.authentication_config.get("sensitivity", 0.1)
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        self.model.fit(normalized_features)
        self.last_training_time = datetime.now()

        self.logger.info(f"Anomaly detection model trained with {len(features)} samples")
        return True

    def detect_anomalies(self, alerts: List[AlertDto]) -> Dict[str, Any]:
        """
        Detect anomalies in the provided alerts.

        Returns:
            Dict containing:
            - is_anomaly: bool indicating if the latest alert is anomalous
            - anomaly_score: float anomaly score (-1 to 1, lower = more anomalous)
            - confidence: float confidence in the prediction
            - explanation: str explanation of the detection
        """
        if not alerts:
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "confidence": 0.0,
                "explanation": "No alerts provided"
            }

            # Extract features
        features = self._extract_features(alerts)

        if len(features) < 2:
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "confidence": 0.0,
                "explanation": "Insufficient data for anomaly detection"
            }

            # Train or update model if needed
        if (self.model is None or
                self.last_training_time is None or
                (datetime.now() - self.last_training_time).hours > 24):
            if not self._train_model(features[:-1]):  # Train on all but latest
                return {
                    "is_anomaly": False,
                    "anomaly_score": 0.0,
                    "confidence": 0.0,
                    "explanation": "Model training failed"
                }

                # Predict on the latest alert
        latest_features = features[-1:].reshape(1, -1)
        normalized_features = self.scaler.transform(latest_features)

        # Get anomaly score (-1 for anomalies, 1 for inliers)
        anomaly_score = self.model.decision_function(normalized_features)[0]
        is_anomaly = self.model.predict(normalized_features)[0] == -1

        # Calculate confidence based on distance from decision boundary
        confidence = abs(anomaly_score)

        # Generate explanation
        explanation = self._generate_explanation(alerts[-1], anomaly_score, is_anomaly)

        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": float(anomaly_score),
            "confidence": float(confidence),
            "explanation": explanation
        }

    def _generate_explanation(self, alert: AlertDto, score: float, is_anomaly: bool) -> str:
        """Generate human-readable explanation for the anomaly detection result."""
        if not is_anomaly:
            return f"Alert pattern appears normal (score: {score:.2f})"

        reasons = []

        # Check severity
        if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
            reasons.append(f"high severity ({alert.severity})")

            # Check timing
        timestamp = datetime.fromisoformat(alert.lastReceived.replace('Z', '+00:00'))
        if timestamp.hour < 6 or timestamp.hour > 22:
            reasons.append("unusual timing (off-hours)")

            # Check service
        if alert.service:
            reasons.append(f"service: {alert.service}")

        explanation = f"Anomaly detected (score: {score:.2f})"
        if reasons:
            explanation += f" - reasons: {', '.join(reasons)}"

        return explanation