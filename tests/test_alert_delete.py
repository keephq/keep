from types import SimpleNamespace

from keep.api.models.alert import DeleteRequestBody
from keep.api.routes import alerts


def test_delete_alert_without_last_received_deletes_all_alert_timestamps(monkeypatch):
    captured_enrichment = {}
    captured_fetch = {}

    class FakeEnrichmentsBl:
        def __init__(self, tenant_id):
            assert tenant_id == "tenant-1"

        def enrich_entity(self, **kwargs):
            captured_enrichment.update(kwargs)

    monkeypatch.setattr(alerts, "get_enrichment", lambda tenant_id, fingerprint: None)

    def fake_get_alerts_by_fingerprint(tenant_id, fingerprint, limit=1000):
        captured_fetch.update(
            {
                "tenant_id": tenant_id,
                "fingerprint": fingerprint,
                "limit": limit,
            }
        )
        return [
            SimpleNamespace(event={"lastReceived": "2024-01-01T00:00:00.000Z"}),
            SimpleNamespace(event={"lastReceived": "2024-01-02T00:00:00.000Z"}),
        ]

    monkeypatch.setattr(
        alerts, "get_alerts_by_fingerprint", fake_get_alerts_by_fingerprint
    )
    monkeypatch.setattr(alerts, "EnrichmentsBl", FakeEnrichmentsBl)

    response = alerts.delete_alert(
        DeleteRequestBody(fingerprint="alert-fingerprint"),
        authenticated_entity=SimpleNamespace(
            tenant_id="tenant-1",
            email="user@example.com",
        ),
    )

    assert response == {"status": "ok"}
    assert captured_fetch == {
        "tenant_id": "tenant-1",
        "fingerprint": "alert-fingerprint",
        "limit": None,
    }
    assert captured_enrichment["fingerprint"] == "alert-fingerprint"
    assert captured_enrichment["enrichments"]["deletedAt"] == [
        "2024-01-01T00:00:00.000Z",
        "2024-01-02T00:00:00.000Z",
    ]
    assert captured_enrichment["enrichments"]["assignees"] == {
        "2024-01-01T00:00:00.000Z": "user@example.com",
        "2024-01-02T00:00:00.000Z": "user@example.com",
    }
