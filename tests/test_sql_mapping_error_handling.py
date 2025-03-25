from unittest.mock import patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.bl.mapping_rule_matcher import MappingRuleMatcher
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.mapping import MappingRule
from tests.fixtures.client import test_app  # noqa


@pytest.fixture
def mock_mapping_rule():
    """Create a simple mapping rule for testing."""
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Test Rule",
        description="A test rule for error handling",
        matchers=[["service"]],
        rows=[
            {"service": "web", "owner": "team-a", "email": "team-a@example.com"},
            {"service": "api", "owner": "team-b", "email": "team-b@example.com"},
        ],
        type="csv",
        file_name="",
        created_by="test",
        condition="",
        new_property_name="",
        prefix_to_remove="",
    )
    return rule


@pytest.fixture
def alert_dto():
    """Create a test alert DTO."""
    alert = AlertDto(
        id="test-id",
        name="Test Alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.HIGH,
        lastReceived="2023-01-01T00:00:00Z",
        source=["test-source"],
        fingerprint="test-fingerprint",
    )
    # Add service attribute
    setattr(alert, "service", "web")
    return alert


@pytest.fixture
def alert_dto_multi_level():
    """Create a test alert DTO."""
    alert = AlertDto(
        id="test-id",
        name="Test Alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.HIGH,
        lastReceived="2023-01-01T00:00:00Z",
        source=["test-source"],
        fingerprint="test-fingerprint",
        services=["web"],
    )
    return alert


def test_fallback_on_sql_error(db_session: Session, mock_mapping_rule, alert_dto):
    """Test that matcher falls back to in-memory matching when SQL query fails."""
    # Mock the execute method to raise an exception
    with patch(
        "sqlmodel.Session.execute", side_effect=SQLAlchemyError("Mocked SQL error")
    ):
        # Create the matcher with the mocked session
        matcher = MappingRuleMatcher(
            dialect_name="sqlite", session=db_session  # Use a known dialect name
        )

        # Call get_matching_row which should trigger the SQL error and fall back
        alert_values = {"service": "web"}
        matched_row = matcher.get_matching_row(mock_mapping_rule, alert_values)

        # Should still get a result from the fallback method
        assert matched_row is not None
        assert matched_row["owner"] == "team-a"
        assert matched_row["email"] == "team-a@example.com"


def test_fallback_on_multi_level_sql_error(db_session: Session):
    """Test that matcher falls back on multi-level matching when SQL query fails."""
    # Create a multi-level mapping rule
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Multi-level Test Rule",
        description="A multi-level test rule for error handling",
        matchers=[["services"]],
        rows=[
            {"service_id": "web", "owner": "team-a", "email": "team-a@example.com"},
            {"service_id": "api", "owner": "team-b", "email": "team-b@example.com"},
        ],
        type="csv",
        is_multi_level=True,
        new_property_name="service_info",
        file_name="",
        created_by="test",
        condition="",
        prefix_to_remove="",
    )

    # Mock the execute method to raise an exception
    with patch(
        "sqlmodel.Session.execute", side_effect=SQLAlchemyError("Mocked SQL error")
    ):
        # Create the matcher with the mocked session
        matcher = MappingRuleMatcher(
            dialect_name="sqlite", session=db_session  # Use a known dialect name
        )

        # Call get_matching_rows_multi_level which should trigger the SQL error and fall back
        service_ids = ["web", "api"]
        matches = matcher.get_matching_rows_multi_level(rule, "service_id", service_ids)

        # Should still get results from the fallback method
        assert len(matches) == 2
        assert matches["web"]["owner"] == "team-a"
        assert matches["api"]["owner"] == "team-b"


def test_enrichment_bl_fallback_on_error(
    db_session: Session, mock_mapping_rule, alert_dto
):
    """Test that EnrichmentsBl falls back when MappingRuleMatcher fails."""
    # Set up a mock that will raise an exception when get_matching_row is called
    with patch(
        "keep.api.bl.mapping_rule_matcher.MappingRuleMatcher.get_matching_row",
        side_effect=Exception("Matcher error"),
    ):
        # Create an instance of EnrichmentsBl
        enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

        # Call check_if_match_and_enrich which should catch the exception and fall back
        result = enrichment_bl.check_if_match_and_enrich(alert_dto, mock_mapping_rule)

        # Should still succeed with the fallback method
        assert result is True
        assert hasattr(alert_dto, "owner")
        assert alert_dto.owner == "team-a"
        assert hasattr(alert_dto, "email")
        assert alert_dto.email == "team-a@example.com"


def test_unsupported_dialect(mock_mapping_rule):
    """Test handling of unsupported database dialect."""
    # Create matcher with an unsupported dialect
    matcher = MappingRuleMatcher(dialect_name="unsupported_dialect", session=None)

    # Should fall back to Python implementation
    alert_values = {"service": "web"}
    matched_row = matcher.get_matching_row(mock_mapping_rule, alert_values)

    # Should still get a result
    assert matched_row is not None
    assert matched_row["owner"] == "team-a"
    assert matched_row["email"] == "team-a@example.com"


def test_null_session_handling(mock_mapping_rule):
    """Test handling of null database session."""
    # Create matcher with a valid dialect but null session
    matcher = MappingRuleMatcher(dialect_name="sqlite", session=None)

    # Should fall back to Python implementation
    alert_values = {"service": "web"}
    matched_row = matcher.get_matching_row(mock_mapping_rule, alert_values)

    # Should still get a result
    assert matched_row is not None
    assert matched_row["owner"] == "team-a"
    assert matched_row["email"] == "team-a@example.com"


def test_missing_alert_values(db_session: Session, mock_mapping_rule):
    """Test behavior when alert values don't have required attributes."""
    dialect_name = None
    if (
        hasattr(db_session, "bind")
        and db_session.bind is not None
        and hasattr(db_session.bind, "dialect")
    ):
        dialect_name = db_session.bind.dialect.name

    matcher = MappingRuleMatcher(dialect_name=dialect_name, session=db_session)

    # Empty alert values - should not match anything
    alert_values = {}
    matched_row = matcher.get_matching_row(mock_mapping_rule, alert_values)

    # Should not match anything
    assert matched_row is None

    # Partial alert values - missing the required "service" field
    alert_values = {"other_field": "value"}
    matched_row = matcher.get_matching_row(mock_mapping_rule, alert_values)

    # Should not match anything
    assert matched_row is None


def test_multi_level_enrichment_fallback(db_session: Session, alert_dto_multi_level):
    """Test that multi-level enrichment falls back when matcher fails."""
    # Create a multi-level mapping rule
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Multi-level Test Rule",
        description="A multi-level test rule for error handling",
        matchers=[["services"]],
        rows=[
            {"services": "web", "owner": "team-a", "email": "team-a@example.com"},
            {"services": "api", "owner": "team-b", "email": "team-b@example.com"},
        ],
        type="csv",
        is_multi_level=True,
        new_property_name="service_info",
        file_name="",
        created_by="test",
        condition="",
        prefix_to_remove="",
    )

    # Set up a mock that will raise an exception when get_matching_rows_multi_level is called
    with patch(
        "keep.api.bl.mapping_rule_matcher.MappingRuleMatcher.get_matching_rows_multi_level",
        side_effect=Exception("Matcher error"),
    ):
        # Create an instance of EnrichmentsBl
        enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

        # Call check_if_match_and_enrich which should catch the exception and fall back
        result = enrichment_bl.check_if_match_and_enrich(alert_dto_multi_level, rule)

        # Should still succeed with the fallback method
        assert result is True
        assert hasattr(alert_dto_multi_level, "service_info")
        assert len(alert_dto_multi_level.service_info) == 1
        assert alert_dto_multi_level.service_info["web"]["owner"] == "team-a"
        assert (
            alert_dto_multi_level.service_info["web"]["email"] == "team-a@example.com"
        )
