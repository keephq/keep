import json

import pytest
from sqlmodel import Session

from keep.api.bl.enrichments_bl import EnrichmentsBl, get_nested_attribute
from keep.api.bl.mapping_rule_matcher import MappingRuleMatcher
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.mapping import MappingRule
from tests.fixtures.client import test_app  # noqa


@pytest.fixture
def complex_mapping_rule(db_session: Session):
    """Create a mapping rule with complex JSON matchers."""
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Complex JSON Matcher",
        description="Rule for matching complex nested JSON structures",
        matchers=[["attributes.environment"], ["metadata.region", "metadata.zone"]],
        rows=[
            {
                "attributes.environment": "production",
                "owner": "prod-team",
                "sla": "99.9%",
                "priority": "critical",
            },
            {
                "attributes.environment": "staging",
                "owner": "dev-team",
                "sla": "99.5%",
                "priority": "high",
            },
            {
                "metadata.region": "us-west",
                "metadata.zone": "us-west-1",
                "owner": "west-team",
                "datacenter": "dc-west",
                "backup": "daily",
            },
            {
                "metadata.region": "us-east",
                "metadata.zone": "us-east-1",
                "owner": "east-team",
                "datacenter": "dc-east",
                "backup": "hourly",
            },
        ],
        type="csv",
        file_name="",
        created_by="test",
        condition="",
        new_property_name="",
        prefix_to_remove="",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


@pytest.fixture
def complex_multi_level_rule(db_session: Session):
    """Create a multi-level mapping rule with complex JSON matchers."""
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Complex Multi-level JSON Matcher",
        description="Multi-level rule for complex nested JSON structures",
        matchers=[["services.ids"]],
        rows=[
            {
                "service_id": "svc-1",
                "details.type": "web",
                "details.tier": "frontend",
                "owner": "team-a",
                "contact": {"email": "team-a@example.com", "slack": "#team-a-alerts"},
            },
            {
                "service_id": "svc-2",
                "details.type": "api",
                "details.tier": "backend",
                "owner": "team-b",
                "contact": {"email": "team-b@example.com", "slack": "#team-b-alerts"},
            },
            {
                "service_id": "svc-3",
                "details.type": "database",
                "details.tier": "data",
                "owner": "team-db",
                "contact": {
                    "email": "db-team@example.com",
                    "phone": "555-123-4567",
                    "slack": "#db-alerts",
                },
            },
        ],
        type="csv",
        is_multi_level=True,
        new_property_name="service_details",
        file_name="",
        created_by="test",
        condition="",
        prefix_to_remove="",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


@pytest.fixture
def complex_alert_dto():
    """Create an alert with complex nested attributes."""
    alert = AlertDto(
        id="test-complex-id",
        name="Complex Test Alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.HIGH,
        lastReceived="2023-01-01T00:00:00Z",
        source=["test-source"],
        fingerprint="test-complex-fingerprint",
    )

    # Add complex nested attributes using json strings
    attributes_json = json.dumps(
        {
            "environment": "production",
            "application": {
                "name": "payment-service",
                "version": "2.3.1",
                "components": ["api", "processor", "database"],
            },
            "tags": ["finance", "critical", "monitored"],
        }
    )
    setattr(alert, "attributes", json.loads(attributes_json))

    metadata_json = json.dumps(
        {
            "region": "us-west",
            "zone": "us-west-1",
            "instance": {
                "id": "i-12345abcdef",
                "type": "m5.large",
                "launchTime": "2023-01-01T00:00:00Z",
            },
            "network": {"vpc": "vpc-abc123", "subnet": "subnet-def456"},
        }
    )
    setattr(alert, "metadata", json.loads(metadata_json))

    # Add service IDs as an array attribute
    services_json = json.dumps(
        {"ids": ["svc-1", "svc-3"], "types": ["web", "database"]}
    )
    setattr(alert, "services", json.loads(services_json))

    return alert


@pytest.fixture
def dotted_attribute_rule(db_session: Session):
    """Create a mapping rule with a matcher for attributes containing dots in their names."""
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Dotted Attribute Matcher",
        description="Rule for matching attributes with dots in their names",
        matchers=[["config.aws@@region"]],
        rows=[
            {
                "config.aws@@region": "us-west-2",
                "owner": "west-team",
                "support": "24/7",
            },
            {
                "config.aws@@region": "us-east-1",
                "owner": "east-team",
                "support": "business hours",
            },
        ],
        type="csv",
        file_name="",
        created_by="test",
        condition="",
        new_property_name="",
        prefix_to_remove="",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


@pytest.fixture
def dotted_alert_dto():
    """Create an alert with attributes that contain dots in their names."""
    alert = AlertDto(
        id="test-dotted-id",
        name="Dotted Test Alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.HIGH,
        lastReceived="2023-01-01T00:00:00Z",
        source=["test-source"],
        fingerprint="test-dotted-fingerprint",
    )

    # Add a nested config object with a key that contains a dot
    config = {
        "aws.region": "us-west-2",
        "instance_type": "t2.micro",
        "subnet_id": "subnet-12345",
    }
    setattr(alert, "config", config)

    return alert


@pytest.fixture
def regex_pattern_rule(db_session: Session):
    """Create a mapping rule for testing regex pattern matching issues."""
    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Regex Pattern Rule",
        description="Rule for testing regex pattern matching behavior",
        matchers=[["service_id"]],
        rows=[
            {"service_id": "customer-9", "owner": "team-9", "region": "us-west-9"},
            {"service_id": "customer-99", "owner": "team-99", "region": "us-west-99"},
        ],
        type="csv",
        file_name="",
        created_by="test",
        condition="",
        new_property_name="",
        prefix_to_remove="",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


def test_match_nested_json_first_matcher_group(
    db_session: Session, complex_mapping_rule, complex_alert_dto
):
    """Test matching against the first matcher group with nested JSON."""
    dialect_name = None
    if (
        hasattr(db_session, "bind")
        and db_session.bind is not None
        and hasattr(db_session.bind, "dialect")
    ):
        dialect_name = db_session.bind.dialect.name

    matcher = MappingRuleMatcher(dialect_name=dialect_name, session=db_session)

    # Extract flattened alert values
    alert_values = {}
    if hasattr(complex_alert_dto, "attributes") and isinstance(
        complex_alert_dto.attributes, dict
    ):
        for key, value in complex_alert_dto.attributes.items():
            alert_values[f"attributes.{key}"] = value

    if hasattr(complex_alert_dto, "metadata") and isinstance(
        complex_alert_dto.metadata, dict
    ):
        for key, value in complex_alert_dto.metadata.items():
            alert_values[f"metadata.{key}"] = value

    # Get matching row using matcher
    matched_row = matcher.get_matching_row(complex_mapping_rule, alert_values)

    # Verify correct match is found (production environment)
    assert matched_row is not None
    assert matched_row["owner"] == "prod-team"
    assert matched_row["sla"] == "99.9%"
    assert matched_row["priority"] == "critical"


def test_match_nested_json_second_matcher_group(
    db_session: Session, complex_mapping_rule, complex_alert_dto
):
    """Test matching against the second matcher group with nested JSON."""
    dialect_name = None
    if (
        hasattr(db_session, "bind")
        and db_session.bind is not None
        and hasattr(db_session.bind, "dialect")
    ):
        dialect_name = db_session.bind.dialect.name

    matcher = MappingRuleMatcher(dialect_name=dialect_name, session=db_session)

    # Modify alert to not match the first matcher group
    if hasattr(complex_alert_dto, "attributes") and isinstance(
        complex_alert_dto.attributes, dict
    ):
        complex_alert_dto.attributes["environment"] = "unknown"

    # Extract flattened alert values
    alert_values = {}
    if hasattr(complex_alert_dto, "attributes") and isinstance(
        complex_alert_dto.attributes, dict
    ):
        for key, value in complex_alert_dto.attributes.items():
            alert_values[f"attributes.{key}"] = value

    if hasattr(complex_alert_dto, "metadata") and isinstance(
        complex_alert_dto.metadata, dict
    ):
        for key, value in complex_alert_dto.metadata.items():
            alert_values[f"metadata.{key}"] = value

    # Get matching row using matcher
    matched_row = matcher.get_matching_row(complex_mapping_rule, alert_values)

    # Verify correct match is found (us-west region and us-west-1 zone)
    assert matched_row is not None
    assert matched_row["owner"] == "west-team"
    assert matched_row["datacenter"] == "dc-west"
    assert matched_row["backup"] == "daily"


def test_multi_level_complex_json_matching(
    db_session: Session, complex_multi_level_rule, complex_alert_dto
):
    """Test multi-level matching with complex nested JSON structures."""
    dialect_name = None
    if (
        hasattr(db_session, "bind")
        and db_session.bind is not None
        and hasattr(db_session.bind, "dialect")
    ):
        dialect_name = db_session.bind.dialect.name

    matcher = MappingRuleMatcher(dialect_name=dialect_name, session=db_session)

    # Extract service IDs for multi-level matching
    service_ids = None
    if hasattr(complex_alert_dto, "services") and isinstance(
        complex_alert_dto.services, dict
    ):
        if "ids" in complex_alert_dto.services:
            service_ids = complex_alert_dto.services["ids"]

    assert service_ids is not None, "Service IDs not found in alert"

    # Get matching rows using multi-level matcher
    matches = matcher.get_matching_rows_multi_level(
        complex_multi_level_rule, "service_id", service_ids
    )

    # Verify correct matches are found
    assert len(matches) == 2  # Should match svc-1 and svc-3

    # Check svc-1 details
    assert "svc-1" in matches
    assert matches["svc-1"]["owner"] == "team-a"
    assert matches["svc-1"]["details.tier"] == "frontend"
    assert isinstance(matches["svc-1"]["contact"], dict)
    assert matches["svc-1"]["contact"]["email"] == "team-a@example.com"

    # Check svc-3 details
    assert "svc-3" in matches
    assert matches["svc-3"]["owner"] == "team-db"
    assert matches["svc-3"]["details.tier"] == "data"
    assert isinstance(matches["svc-3"]["contact"], dict)
    assert matches["svc-3"]["contact"]["email"] == "db-team@example.com"
    assert matches["svc-3"]["contact"]["phone"] == "555-123-4567"


def test_dotted_attribute_direct_access():
    """Test the get_nested_attribute function with attributes containing dots."""
    # Create a simple object with a nested attribute containing a dot
    alert = AlertDto(
        id="test-id",
        name="Test Alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.HIGH,
        lastReceived="2023-01-01T00:00:00Z",
        source=["test-source"],
        fingerprint="test-fingerprint",
    )

    # Add a nested config object with a key that contains a dot
    config = {"aws.region": "us-west-2", "instance_type": "t2.micro"}
    setattr(alert, "config", config)

    # Test direct access with the @@ placeholder
    value = get_nested_attribute(alert, "config.aws@@region")
    assert value == "us-west-2"

    # Test access without the placeholder (should fail or return None)
    value = get_nested_attribute(alert, "config.aws.region")
    assert value is None  # Since "aws" is not a nested object in config


def test_dotted_attribute_mapping_rule(
    db_session: Session, dotted_attribute_rule, dotted_alert_dto
):
    """Test that mapping rules correctly handle attributes with dots in their names."""
    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

    # Check if the rule matches and enriches the alert
    result = enrichment_bl.check_if_match_and_enrich(
        dotted_alert_dto, dotted_attribute_rule
    )

    # Verify enrichment worked
    assert result is True
    assert hasattr(dotted_alert_dto, "owner")
    assert dotted_alert_dto.owner == "west-team"
    assert hasattr(dotted_alert_dto, "support")
    assert dotted_alert_dto.support == "24/7"


def test_dotted_attribute_direct_matcher_access(
    db_session: Session, dotted_attribute_rule, dotted_alert_dto
):
    """Test that the matcher correctly handles attributes with dots in their names."""
    dialect_name = None
    if (
        hasattr(db_session, "bind")
        and db_session.bind is not None
        and hasattr(db_session.bind, "dialect")
    ):
        dialect_name = db_session.bind.dialect.name

    matcher = MappingRuleMatcher(dialect_name=dialect_name, session=db_session)

    # Extract the alert values including the dotted attribute
    alert_values = {}
    if hasattr(dotted_alert_dto, "config") and isinstance(
        dotted_alert_dto.config, dict
    ):
        for key, value in dotted_alert_dto.config.items():
            # If the key contains a dot, replace it with @@
            if "." in key:
                formatted_key = key.replace(".", "@@")
                alert_values[f"config.{formatted_key}"] = value
            else:
                alert_values[f"config.{key}"] = value

    # Get matching row using matcher
    matched_row = matcher.get_matching_row(dotted_attribute_rule, alert_values)

    # Verify correct match is found
    assert matched_row is not None
    assert matched_row["owner"] == "west-team"
    assert matched_row["support"] == "24/7"


def test_regex_pattern_matching_issue(db_session: Session, regex_pattern_rule):
    """Test the issue where 'customer-999' incorrectly matches 'customer-9' due to regex behavior."""
    matcher = MappingRuleMatcher(
        dialect_name=None, session=None  # Force fallback implementation
    )

    # Test with a value that contains, but is not equal to, the first row's service_id
    alert_values = {"service_id": "customer-999"}

    # Use the fallback method that uses regex matching
    matched_row = matcher._fallback_get_matching_row(regex_pattern_rule, alert_values)

    # With current implementation, this would match incorrectly to "customer-9"
    # We demonstrate the issue here, but in a fixed implementation this should be None
    assert matched_row is not None
    assert matched_row["owner"] == "team-9"  # Incorrectly matches customer-9

    # This demonstrates the current behavior is incorrect
    # The alert service_id "customer-999" should not match the rule pattern "customer-9"
    # In a fixed implementation, this test would be updated to assert matched_row is None
