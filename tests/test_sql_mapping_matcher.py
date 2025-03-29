import pytest
from sqlmodel import Session, select

from keep.api.bl.mapping_rule_matcher import MappingRuleMatcher
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.mapping import MappingRule
from tests.fixtures.client import test_app  # noqa


@pytest.fixture
def mapping_rule(db_session: Session):
    """Create a mapping rule with test data."""
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Test SQL Matcher Rule",
        description="Test rule for SQL-based matching",
        matchers=[["service", "severity"], ["source"]],
        rows=[
            {
                "service": "backend",
                "severity": "high",
                "team": "backend-team",
                "owner": "backend-owner",
            },
            {
                "service": "frontend",
                "severity": "medium",
                "team": "frontend-team",
                "owner": "frontend-owner",
            },
            {
                "source": "prometheus",
                "team": "monitoring-team",
                "owner": "monitoring-owner",
            },
            {
                "service": "*",  # Wildcard
                "severity": "critical",
                "team": "sre-team",
                "owner": "sre-owner",
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
    """Create a multi-level mapping rule with test data."""
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Multi-Level SQL Matcher Rule",
        description="Test rule for multi-level SQL-based matching",
        matchers=[["customer"]],
        rows=[
            {"customer": "customer-1", "contact": "contact-1", "priority": "high"},
            {"customer": "customer-2", "contact": "contact-2", "priority": "medium"},
            {"customer": "customer-3", "contact": "contact-3", "priority": "low"},
        ],
        type="csv",
        is_multi_level=True,
        new_property_name="customer_data",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


def test_get_matching_row_exact_match(db_session: Session, mapping_rule: MappingRule):
    """Test that exact matching works correctly with DB session."""
    matcher = MappingRuleMatcher(
        dialect_name=db_session.bind.dialect.name, session=db_session
    )

    # Test case 1: Exact match on service and severity
    alert_values = {"service": "backend", "severity": "high"}

    matched_row = matcher.get_matching_row(mapping_rule, alert_values)

    assert matched_row is not None
    assert matched_row["team"] == "backend-team"
    assert matched_row["owner"] == "backend-owner"


def test_get_matching_row_wildcard_match(
    db_session: Session, mapping_rule: MappingRule
):
    """Test that wildcard matching works correctly with DB session."""
    matcher = MappingRuleMatcher(
        dialect_name=db_session.bind.dialect.name, session=db_session
    )

    # Test with wildcard row
    alert_values = {
        "service": "unknown-service",  # Not directly in the rule
        "severity": "critical",
    }

    matched_row = matcher.get_matching_row(mapping_rule, alert_values)

    assert matched_row is not None
    assert matched_row["team"] == "sre-team"
    assert matched_row["owner"] == "sre-owner"


def test_get_matching_row_alternative_matcher(
    db_session: Session, mapping_rule: MappingRule
):
    """Test that alternative matchers (OR conditions) work correctly with DB session."""
    matcher = MappingRuleMatcher(
        dialect_name=db_session.bind.dialect.name, session=db_session
    )

    # Test with source matcher (alternative matcher)
    alert_values = {"source": "prometheus"}

    matched_row = matcher.get_matching_row(mapping_rule, alert_values)

    assert matched_row is not None
    assert matched_row["team"] == "monitoring-team"
    assert matched_row["owner"] == "monitoring-owner"


def test_get_matching_row_no_match(db_session: Session, mapping_rule: MappingRule):
    """Test handling of no matches with DB session."""
    matcher = MappingRuleMatcher(
        dialect_name=db_session.bind.dialect.name, session=db_session
    )

    # Test with values that shouldn't match anything
    alert_values = {
        "service": "unknown-service",
        "severity": "low",  # Not critical, so won't match the wildcard row
    }

    matched_row = matcher.get_matching_row(mapping_rule, alert_values)

    assert matched_row is None


def test_get_matching_rows_multi_level(
    db_session: Session, multi_level_rule: MappingRule
):
    """Test multi-level matching with DB session."""
    matcher = MappingRuleMatcher(
        dialect_name=db_session.bind.dialect.name, session=db_session
    )

    # Test with multiple customer values
    customers = ["customer-1", "customer-3", "customer-not-exists"]

    matches = matcher.get_matching_rows_multi_level(
        multi_level_rule, "customer", customers
    )

    assert len(matches) == 2  # Should match two customers
    assert "customer-1" in matches
    assert "customer-3" in matches
    assert matches["customer-1"]["contact"] == "contact-1"
    assert matches["customer-1"]["priority"] == "high"
    assert matches["customer-3"]["contact"] == "contact-3"
    assert matches["customer-3"]["priority"] == "low"


def test_multiple_rules_priority(db_session: Session):
    """Test that rule priority works correctly."""
    # Create two rules with different priorities
    rule1 = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=10,  # Higher priority
        name="High Priority Rule",
        description="Rule with high priority",
        matchers=[["service"]],
        rows=[{"service": "shared-service", "result": "high-priority"}],
        type="csv",
    )

    rule2 = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=5,  # Lower priority
        name="Low Priority Rule",
        description="Rule with low priority",
        matchers=[["service"]],
        rows=[{"service": "shared-service", "result": "low-priority"}],
        type="csv",
    )

    db_session.add(rule1)
    db_session.add(rule2)
    db_session.commit()
    db_session.refresh(rule1)
    db_session.refresh(rule2)

    # Use direct query to verify the order
    rules = db_session.exec(
        select(MappingRule)
        .filter(MappingRule.tenant_id == SINGLE_TENANT_UUID)
        .filter(MappingRule.name.in_(["High Priority Rule", "Low Priority Rule"]))
        .order_by(MappingRule.priority.desc())
    ).all()

    assert len(rules) == 2
    assert rules[0].name == "High Priority Rule"
    assert rules[1].name == "Low Priority Rule"

    # Also test with a matcher to ensure we get the high priority result
    matcher = MappingRuleMatcher(
        dialect_name=db_session.bind.dialect.name, session=db_session
    )

    alert_values = {"service": "shared-service"}

    # Should match the higher priority rule
    matched_row = matcher.get_matching_row(rule1, alert_values)
    assert matched_row is not None
    assert matched_row["result"] == "high-priority"


def test_large_dataset(db_session: Session):
    """Test with a large dataset to ensure SQL optimization works."""
    # Create a rule with many rows
    large_rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Large Dataset Rule",
        description="Rule with many rows to test SQL performance",
        matchers=[["id"]],
        rows=[{"id": f"id-{i}", "value": f"value-{i}"} for i in range(1000)],
        type="csv",
    )

    db_session.add(large_rule)
    db_session.commit()
    db_session.refresh(large_rule)

    matcher = MappingRuleMatcher(
        dialect_name=db_session.bind.dialect.name, session=db_session
    )

    # Test finding a specific ID in the large dataset
    alert_values = {"id": "id-500"}

    matched_row = matcher.get_matching_row(large_rule, alert_values)
    assert matched_row is not None
    assert matched_row["value"] == "value-500"

    # Test finding the last entry to ensure full scan works
    alert_values = {"id": "id-999"}

    matched_row = matcher.get_matching_row(large_rule, alert_values)
    assert matched_row is not None
    assert matched_row["value"] == "value-999"
