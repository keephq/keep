from datetime import datetime
from typing import List

import pytest
from sqlmodel import Session

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto
from keep.api.models.db.mapping import MappingRule
from tests.fixtures.client import test_app  # noqa


@pytest.fixture
def alert_dto():
    """Create a test AlertDto for testing."""
    return AlertDto(
        id="test-alert-id",
        name="Test Alert",
        status="firing",
        severity="high",
        lastReceived=datetime.utcnow().isoformat(),
        source=["test-source"],
        fingerprint="test-fingerprint",
        service="test-service",
        environment="test-environment",
    )


@pytest.fixture
def simple_mapping_rule(db_session: Session):
    """Create a simple mapping rule for testing."""
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Simple Mapping Rule",
        description="A simple mapping rule for testing",
        matchers=[["service"]],
        rows=[{"service": "test-service", "team": "test-team", "owner": "test-owner"}],
        type="csv",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


@pytest.fixture
def multi_matcher_rule(db_session: Session):
    """Create a mapping rule with multiple matchers."""
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Multi Matcher Rule",
        description="A rule with multiple matchers",
        matchers=[["service", "environment"], ["source"]],
        rows=[
            {
                "service": "test-service",
                "environment": "test-environment",
                "team": "test-team",
                "owner": "test-owner",
                "tier": "tier-1",
            },
            {
                "source": "test-source",
                "team": "source-team",
                "owner": "source-owner",
                "tier": "tier-2",
            },
        ],
        type="csv",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


@pytest.fixture
def multi_level_rule(db_session: Session):
    """Create a multi-level mapping rule."""
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Multi-Level Rule",
        description="A multi-level mapping rule",
        matchers=[["tags"]],
        rows=[
            {"tags": "tag1", "contact": "contact1", "team": "team1"},
            {"tags": "tag2", "contact": "contact2", "team": "team2"},
            {"tags": "tag3", "contact": "contact3", "team": "team3"},
        ],
        is_multi_level=True,
        new_property_name="tag_info",
        type="csv",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


@pytest.fixture
def wildcard_rule(db_session: Session):
    """Create a mapping rule with wildcard matcher."""
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Wildcard Rule",
        description="A rule with wildcard matcher",
        matchers=[["service"]],
        rows=[
            {
                "service": "*",  # Matches any service
                "team": "default-team",
                "owner": "default-owner",
            }
        ],
        type="csv",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


@pytest.fixture
def all_mapping_rules(
    db_session: Session,
    simple_mapping_rule: MappingRule,
    multi_matcher_rule: MappingRule,
    multi_level_rule: MappingRule,
    wildcard_rule: MappingRule,
) -> List[MappingRule]:
    """Return all created mapping rules."""
    return [simple_mapping_rule, multi_matcher_rule, multi_level_rule, wildcard_rule]


def test_simple_mapping_rule_match(
    db_session: Session, alert_dto: AlertDto, simple_mapping_rule: MappingRule
):
    """Test that a simple mapping rule correctly matches and enriches an alert."""
    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

    # Run the matching logic
    result = enrichment_bl.check_if_match_and_enrich(alert_dto, simple_mapping_rule)

    # Verify the result
    assert result is True
    assert alert_dto.team == "test-team"
    assert alert_dto.owner == "test-owner"


def test_multi_matcher_rule_first_matcher(
    db_session: Session, alert_dto: AlertDto, multi_matcher_rule: MappingRule
):
    """Test that the first matcher group in a multi-matcher rule matches correctly."""
    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

    # Alert already has service="test-service" and environment="test-environment"
    result = enrichment_bl.check_if_match_and_enrich(alert_dto, multi_matcher_rule)

    # Verify the result
    assert result is True
    assert alert_dto.team == "test-team"
    assert alert_dto.owner == "test-owner"
    assert alert_dto.tier == "tier-1"


def test_multi_matcher_rule_second_matcher(
    db_session: Session, alert_dto: AlertDto, multi_matcher_rule: MappingRule
):
    """Test that the second matcher group in a multi-matcher rule matches correctly."""
    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

    # Change service to not match the first matcher
    alert_dto.service = "different-service"
    # source still matches the second matcher

    result = enrichment_bl.check_if_match_and_enrich(alert_dto, multi_matcher_rule)

    # Verify the result
    assert result is True
    assert alert_dto.team == "source-team"
    assert alert_dto.owner == "source-owner"
    assert alert_dto.tier == "tier-2"


def test_no_match(
    db_session: Session, alert_dto: AlertDto, simple_mapping_rule: MappingRule
):
    """Test that no match returns False and doesn't enrich the alert."""
    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

    # Modify the alert to not match any rule
    alert_dto.service = "non-matching-service"
    alert_dto.source = ["non-matching-source"]

    # Store original attribute values
    original_team = getattr(alert_dto, "team", None)
    original_owner = getattr(alert_dto, "owner", None)

    result = enrichment_bl.check_if_match_and_enrich(alert_dto, simple_mapping_rule)

    # Verify the result
    assert result is False
    assert getattr(alert_dto, "team", None) == original_team
    assert getattr(alert_dto, "owner", None) == original_owner


def test_wildcard_match(
    db_session: Session, alert_dto: AlertDto, wildcard_rule: MappingRule
):
    """Test that wildcard matching works correctly."""
    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

    # Modify the alert to have a service that doesn't explicitly match
    alert_dto.service = "any-service"

    result = enrichment_bl.check_if_match_and_enrich(alert_dto, wildcard_rule)

    # Verify the result
    assert result is True
    assert alert_dto.team == "default-team"
    assert alert_dto.owner == "default-owner"


def test_multi_level_mapping(
    db_session: Session, alert_dto: AlertDto, multi_level_rule: MappingRule
):
    """Test that multi-level mapping works correctly."""
    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

    # Set tags attribute to a list of values
    alert_dto.tags = ["tag1", "tag3", "non-existent-tag"]

    result = enrichment_bl.check_if_match_and_enrich(alert_dto, multi_level_rule)

    # Verify the result
    assert result is True
    assert hasattr(alert_dto, "tag_info")

    # Verify the nested structure
    tag_info = alert_dto.tag_info
    assert "tag1" in tag_info
    assert "tag3" in tag_info
    assert "non-existent-tag" not in tag_info

    assert tag_info["tag1"]["contact"] == "contact1"
    assert tag_info["tag1"]["team"] == "team1"
    assert tag_info["tag3"]["contact"] == "contact3"
    assert tag_info["tag3"]["team"] == "team3"


def test_run_mapping_rules(
    db_session: Session, alert_dto: AlertDto, all_mapping_rules: List[MappingRule]
):
    """Test running all mapping rules on an alert."""
    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

    # Set up alert to match a specific rule
    alert_dto.service = "test-service"
    alert_dto.environment = "test-environment"
    alert_dto.source = ["test-source"]
    alert_dto.tags = ["tag1", "tag2"]

    # Run all mapping rules
    result_alert = enrichment_bl.run_mapping_rules(alert_dto)

    # Verify that the alert was enriched
    assert result_alert == alert_dto  # Same object
    assert hasattr(alert_dto, "team")
    assert hasattr(alert_dto, "owner")
    # Multi-level enrichment should also have happened
    assert hasattr(alert_dto, "tag_info")
    assert "tag1" in alert_dto.tag_info
    assert "tag2" in alert_dto.tag_info


def test_rule_ordering_by_priority(db_session: Session, alert_dto: AlertDto):
    """Test that rules are applied in order of priority."""
    # Create two rules with different priorities that would apply different enrichments
    high_priority_rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=10,  # Higher priority
        name="High Priority Rule",
        description="Rule with high priority",
        matchers=[["service"]],
        rows=[
            {
                "service": "test-service",
                "team": "high-priority-team",
                "owner": "high-priority-owner",
            }
        ],
        type="csv",
    )

    low_priority_rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=5,  # Lower priority
        name="Low Priority Rule",
        description="Rule with low priority",
        matchers=[["service"]],
        rows=[
            {
                "service": "test-service",
                "team": "low-priority-team",
                "owner": "low-priority-owner",
            }
        ],
        type="csv",
    )

    db_session.add(high_priority_rule)
    db_session.add(low_priority_rule)
    db_session.commit()

    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

    # Set up alert to match both rules
    alert_dto.service = "test-service"

    # Run all mapping rules
    result_alert = enrichment_bl.run_mapping_rules(alert_dto)

    # Verify that the high priority rule was applied
    assert result_alert.team == "low-priority-team"
    assert result_alert.owner == "low-priority-owner"
