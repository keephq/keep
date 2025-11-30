import logging
import requests
import json
from datetime import datetime
from typing import Optional, Dict, Any
from keep.api.models.alert import AlertDto

logger = logging.getLogger(__name__)


class AIEnrichmentService:
    def __init__(self):
        # Берем конфиги из environment variables
        self.prometheus_url = "http://localhost:9090"  # Будет из конфига
        self.enabled = True  # По умолчанию выключим потом

    async def enrich_alert(self, alert: AlertDto) -> Dict[str, Any]:
        """Анализирует алерт и возвращает данные для enrichment"""
        if not self.enabled:
            return {}

        try:
            if alert.status.value == "resolved":
                return {}

            metric_query = self._extract_metric_query(alert)
            if not metric_query:
                return {}

            analysis = await self._analyze_with_prometheus(metric_query)
            return self._format_enrichment_data(analysis, metric_query)

        except Exception as e:
            logger.error(f"AI enrichment failed for alert {alert.id}: {e}")
            return {}

    def _extract_metric_query(self, alert: AlertDto) -> Optional[str]:
        labels = alert.labels or {}

        if "metric_query" in labels:
            return labels["metric_query"]
        if "metric_name" in labels:
            return labels["metric_name"]

        if alert.service and alert.name:
            service_name = alert.service.lower()
            alert_name = alert.name.lower()

            if any(word in alert_name for word in ['cpu', 'processor', 'load']):
                return f'rate(container_cpu_usage_seconds_total{{container="{service_name}"}}[5m])'
            elif any(word in alert_name for word in ['memory', 'ram', 'oom']):
                return f'container_memory_usage_bytes{{container="{service_name}"}}'

        return None

    async def _analyze_with_prometheus(self, metric_query: str) -> Dict[str, Any]:
        try:
            promql_query = f"abs(stddev_over_time({metric_query}[1h]))"

            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={'query': promql_query},
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            confidence_score = self._calculate_confidence_score(data)

            return {
                "confidence_score": confidence_score,
                "verdict": self._get_verdict(confidence_score),
                "promql_query": promql_query
            }

        except Exception as e:
            logger.error(f"Prometheus analysis failed: {e}")
            return {
                "confidence_score": 0.5,
                "verdict": "inconclusive",
                "error": str(e)
            }

    def _calculate_confidence_score(self, prometheus_data: Dict) -> float:
        try:
            result = prometheus_data.get('data', {}).get('result', [])
            if result and len(result) > 0:
                value = float(result[0]['value'][1])
                if value < 0.05:
                    return value * 6
                elif value < 0.1:
                    return 0.3 + (value - 0.05) * 6
                else:
                    return min(0.6 + (value - 0.1) * 4, 1.0)
            return 0.5
        except Exception:
            return 0.5

    def _get_verdict(self, confidence_score: float) -> str:
        if confidence_score > 0.8:
            return "confirmed_anomaly"
        elif confidence_score < 0.2:
            return "likely_false_positive"
        else:
            return "inconclusive"

    def _format_enrichment_data(self, analysis: Dict, metric_query: str) -> Dict[str, Any]:
        return {
            "ai_confidence_score": str(round(analysis["confidence_score"], 3)),
            "ai_verdict": analysis["verdict"],
            "ai_metric_analyzed": metric_query,
            "ai_analyzed_at": datetime.utcnow().isoformat() + "Z"
        }


ai_enrichment_service = AIEnrichmentService()