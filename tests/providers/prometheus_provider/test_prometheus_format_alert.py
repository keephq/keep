from keep.api.models.alert import AlertStatus
from keep.providers.prometheus_provider.prometheus_provider import PrometheusProvider


def _api_v1_alerts(state: str) -> dict:
    # Shape of the `data` object returned by Prometheus' GET /api/v1/alerts,
    # which is what PrometheusProvider._get_alerts passes to _format_alert.
    return {
        "alerts": [
            {
                "labels": {"alertname": "HighLatency", "severity": "warning"},
                "annotations": {"summary": "p99 latency above 500ms"},
                "state": state,
                "activeAt": "2026-10-26T09:00:00Z",
                "value": "6.1e-01",
            }
        ]
    }


def test_pending_alert_is_not_reported_as_firing():
    alerts = PrometheusProvider._format_alert(_api_v1_alerts("pending"))

    assert len(alerts) == 1
    assert alerts[0].status == AlertStatus.PENDING.value


def test_firing_alert_stays_firing():
    alerts = PrometheusProvider._format_alert(_api_v1_alerts("firing"))

    assert alerts[0].status == AlertStatus.FIRING.value
