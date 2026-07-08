"""Tests for the flat assignee enrichment field used by the facet/filter system."""
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Unit tests — flat assignee field logic (no DB required)
# ---------------------------------------------------------------------------


def _compute_flat_assignee(assignees_last_received: dict) -> str | None:
    """Mirror of the production logic in assign_alert()."""
    return (
        next(iter(reversed(assignees_last_received.values())), None)
        if assignees_last_received
        else None
    )


def test_flat_assignee_single_entry():
    assignees = {"2024-01-01T00:00:00": "alice@example.com"}
    assert _compute_flat_assignee(assignees) == "alice@example.com"


def test_flat_assignee_multiple_entries_returns_last():
    assignees = {
        "2024-01-01T00:00:00": "alice@example.com",
        "2024-01-02T00:00:00": "bob@example.com",
    }
    assert _compute_flat_assignee(assignees) == "bob@example.com"


def test_flat_assignee_empty_dict_returns_none():
    assert _compute_flat_assignee({}) is None


def test_flat_assignee_none_input_returns_none():
    # Simulates unassign that empties the dict
    assignees = {}
    assert _compute_flat_assignee(assignees) is None


def test_flat_assignee_after_unassign():
    """After removing the last entry, flat_assignee should be None."""
    assignees = {"2024-01-01T00:00:00": "alice@example.com"}
    last_received = "2024-01-01T00:00:00"
    assignees.pop(last_received, None)
    assert _compute_flat_assignee(assignees) is None


def test_flat_assignee_after_partial_unassign():
    """After removing one of two entries, flat_assignee should be the remaining one."""
    assignees = {
        "2024-01-01T00:00:00": "alice@example.com",
        "2024-01-02T00:00:00": "bob@example.com",
    }
    assignees.pop("2024-01-02T00:00:00", None)
    assert _compute_flat_assignee(assignees) == "alice@example.com"


# ---------------------------------------------------------------------------
# Unit tests — enrichment_helpers: assignee excluded from enriched_fields
# ---------------------------------------------------------------------------


def test_assignee_excluded_from_enriched_fields():
    """The synthetic 'assignee' field must not appear in enriched_fields."""
    from keep.api.utils.enrichment_helpers import parse_and_enrich_deleted_and_assignees

    alert = MagicMock()
    alert.lastReceived = "2024-01-01T00:00:00.000Z"
    enrichments = {
        "status": "open",
        "assignees": {},
        "assignee": None,
        "severity": "high",
    }

    parse_and_enrich_deleted_and_assignees(alert, enrichments)

    assert "assignee" not in alert.enriched_fields


def test_non_assignee_fields_kept_in_enriched_fields():
    """Other enriched fields must not be removed."""
    from keep.api.utils.enrichment_helpers import parse_and_enrich_deleted_and_assignees

    alert = MagicMock()
    alert.lastReceived = "2024-01-01T00:00:00.000Z"
    enrichments = {"status": "open", "severity": "high", "assignee": None}

    parse_and_enrich_deleted_and_assignees(alert, enrichments)

    assert "status" in alert.enriched_fields
    assert "severity" in alert.enriched_fields


def test_no_error_when_assignee_not_in_enriched_fields():
    """Should not raise if 'assignee' is absent from enriched_fields."""
    from keep.api.utils.enrichment_helpers import parse_and_enrich_deleted_and_assignees

    alert = MagicMock()
    alert.lastReceived = "2024-01-01T00:00:00.000Z"
    enrichments = {"status": "open", "severity": "high"}

    parse_and_enrich_deleted_and_assignees(alert, enrichments)  # must not raise


# ---------------------------------------------------------------------------
# Integration-style tests — assign_alert enrichments payload
# ---------------------------------------------------------------------------


def _call_assign_alert(fingerprint, last_received, user_email, existing_enrichments=None, unassign=False):
    """Call the core assign logic and return the enrichments dict passed to enrich_entity."""
    from keep.api.routes.alerts import assign_alert

    mock_enrichment = None
    if existing_enrichments is not None:
        mock_enrichment = MagicMock()
        mock_enrichment.enrichments = existing_enrichments

    captured = {}

    def fake_enrich(fingerprint, enrichments, **kwargs):
        captured["enrichments"] = enrichments

    mock_entity = MagicMock()
    mock_entity.tenant_id = "keep"
    mock_entity.email = user_email

    with (
        patch("keep.api.routes.alerts.get_enrichment", return_value=mock_enrichment),
        patch("keep.api.routes.alerts.EnrichmentsBl") as mock_bl_cls,
        patch("keep.api.routes.alerts.send_email"),
        patch("keep.api.routes.alerts.get_alerts_by_fingerprint", return_value=[]),
        patch("keep.api.routes.alerts.WorkflowManager") as mock_wm,
    ):
        mock_wm.get_instance.return_value = MagicMock()
        mock_bl = MagicMock()
        mock_bl.enrich_entity.side_effect = fake_enrich
        mock_bl_cls.return_value = mock_bl

        assign_alert(
            fingerprint=fingerprint,
            last_received=last_received,
            unassign=unassign,
            authenticated_entity=mock_entity,
        )

    return captured.get("enrichments", {})


def test_assign_writes_flat_assignee():
    enrichments = _call_assign_alert(
        fingerprint="abc123",
        last_received="2024-01-01T00:00:00",
        user_email="alice@example.com",
    )
    assert enrichments["assignee"] == "alice@example.com"
    assert enrichments["assignees"] == {"2024-01-01T00:00:00": "alice@example.com"}


def test_assign_normalizes_email_to_lowercase():
    enrichments = _call_assign_alert(
        fingerprint="abc123",
        last_received="2024-01-01T00:00:00",
        user_email="Alice@Example.Com",
    )
    assert enrichments["assignee"] == "alice@example.com"
    assert enrichments["assignees"] == {"2024-01-01T00:00:00": "alice@example.com"}


def test_assign_flat_assignee_reflects_most_recent():
    existing = {
        "assignees": {
            "2024-01-01T00:00:00": "alice@example.com",
        }
    }
    enrichments = _call_assign_alert(
        fingerprint="abc123",
        last_received="2024-01-02T00:00:00",
        user_email="bob@example.com",
        existing_enrichments=existing,
    )
    assert enrichments["assignee"] == "bob@example.com"


def test_unassign_clears_flat_assignee_when_no_remaining():
    existing = {
        "assignees": {"2024-01-01T00:00:00": "alice@example.com"},
        "status": "acknowledged",
    }
    enrichments = _call_assign_alert(
        fingerprint="abc123",
        last_received="2024-01-01T00:00:00",
        user_email="alice@example.com",
        existing_enrichments=existing,
        unassign=True,
    )
    assert enrichments["assignee"] is None
    assert enrichments["assignees"] == {}


def test_unassign_keeps_other_assignee():
    existing = {
        "assignees": {
            "2024-01-01T00:00:00": "alice@example.com",
            "2024-01-02T00:00:00": "bob@example.com",
        },
        "status": "acknowledged",
    }
    enrichments = _call_assign_alert(
        fingerprint="abc123",
        last_received="2024-01-02T00:00:00",
        user_email="bob@example.com",
        existing_enrichments=existing,
        unassign=True,
    )
    assert enrichments["assignee"] == "alice@example.com"
    assert "bob@example.com" not in enrichments["assignees"].values()
