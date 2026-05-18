from keep.providers.grafana_provider.grafana_provider import GrafanaProvider


def _grafana12_test_payload(generator_url: str = "?orgId=1") -> dict:
    return {
        "receiver": "webhook",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "TestAlert",
                    "grafana_folder": "Test Folder",
                    "instance": "Grafana",
                },
                "annotations": {
                    "description": "Test Description",
                    "summary": "TEST",
                },
                "startsAt": "2026-05-05T13:04:57.62281314Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": generator_url,
                "fingerprint": "c4edaaf9f9f839b0",
                "silenceURL": "https://grafana.example.com/alerting/silence/new",
                "dashboardURL": "https://grafana.example.com/d/dashboard_uid",
                "panelURL": "https://grafana.example.com/d/dashboard_uid?viewPanel=1",
                "values": {"B": 22, "C": 1},
                "valueString": "[ var='B' value=22 ]",
                "orgId": 1,
            }
        ],
        "groupLabels": {"alertname": "TestAlert"},
        "commonLabels": {"alertname": "TestAlert"},
        "commonAnnotations": {"description": "Test Description"},
        "externalURL": "https://grafana.example.com/",
        "appVersion": "12.4.2",
        "version": "1",
        "groupKey": "webhook-c4edaaf9f9f839b0-1777986297",
        "truncatedAlerts": 0,
        "orgId": 1,
        "title": "TestAlert",
        "state": "alerting",
        "message": "Firing",
    }


class TestResolveAlertUrl:
    def test_absolute_url_passes_through(self):
        assert (
            GrafanaProvider._resolve_alert_url(
                "https://grafana.example.com/d/foo", "https://ignored.example.com/"
            )
            == "https://grafana.example.com/d/foo"
        )

    def test_query_only_url_joins_with_external_url(self):
        # Grafana 12 test alerts emit this shape.
        assert (
            GrafanaProvider._resolve_alert_url(
                "?orgId=1", "https://grafana.example.com/"
            )
            == "https://grafana.example.com/?orgId=1"
        )

    def test_relative_path_joins_with_external_url(self):
        assert (
            GrafanaProvider._resolve_alert_url(
                "alerting/grafana/abc/view", "https://grafana.example.com/"
            )
            == "https://grafana.example.com/alerting/grafana/abc/view"
        )

    def test_relative_url_without_external_url_returns_none(self):
        assert GrafanaProvider._resolve_alert_url("?orgId=1", None) is None
        assert GrafanaProvider._resolve_alert_url("?orgId=1", "") is None

    def test_missing_or_empty_url_returns_none(self):
        assert GrafanaProvider._resolve_alert_url(None, "https://x/") is None
        assert GrafanaProvider._resolve_alert_url("", "https://x/") is None


class TestFormatAlertGrafana12:
    def test_test_alert_payload_parses(self):
        event = _grafana12_test_payload()

        alerts = GrafanaProvider._format_alert(event)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.name == "TestAlert"
        assert alert.fingerprint == "c4edaaf9f9f839b0"
        assert str(alert.url) == "https://grafana.example.com/?orgId=1"
        assert alert.values == {"B": 22, "C": 1}
        assert alert.description == "Test Description"

    def test_test_alert_without_external_url_drops_invalid_generator_url(self):
        event = _grafana12_test_payload()
        event.pop("externalURL")

        alerts = GrafanaProvider._format_alert(event)

        assert len(alerts) == 1
        assert alerts[0].url is None
