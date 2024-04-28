# test_enrichments.py
from unittest.mock import MagicMock, Mock, patch

import pytest

from keep.api.bl.enrichments import EnrichmentsBl
from keep.api.models.alert import AlertDto
from keep.api.models.db.extraction import ExtractionRule
from keep.api.models.db.mapping import MappingRule


@pytest.fixture
def mock_session():
    """Create a mock session to simulate database operations."""
    session = MagicMock()
    query_mock = MagicMock()
    session.query.return_value = query_mock
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.all.return_value = []  # Default to no rules, override in specific tests
    return session


@pytest.fixture
def mock_alert_dto():
    """Fixture for creating a mock AlertDto."""
    return AlertDto(
        id="test_id",
        name="Test Alert",
        status="firing",
        severity="high",
        lastReceived="2021-01-01T00:00:00Z",
        source=["test_source"],
        labels={},
    )


def test_run_extraction_rules_no_rules_applies(mock_session, mock_alert_dto):
    # Assuming there are no extraction rules
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = (
        []
    )

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)
    result_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    # Check that the event has not changed (no rules to apply)
    assert result_event == mock_alert_dto  # Assuming no change if no rules


def test_run_extraction_rules_regex_named_groups(mock_session, mock_alert_dto):
    # Setup an extraction rule that should apply based on the alert content
    rule = ExtractionRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        attribute="{{ name }}",
        regex="(?P<service_name>Test) (?P<alert_type>Alert)",
        disabled=False,
        pre=True,
        condition=None,  # No condition for simplicity
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Mocking chevron rendering to simulate template rendering
    with patch("chevron.render", return_value="Test Alert"):
        enriched_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    # Assert that the event is now enriched with regex group names
    assert enriched_event.service_name == "Test"
    assert enriched_event.alert_type == "Alert"


def test_run_extraction_rules_event_is_dict(mock_session):
    event = {"name": "Test Alert", "source": ["source_test"]}
    rule = ExtractionRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        attribute="{{ name }}",
        regex="Test Alert",
        disabled=False,
        pre=False,  # Rule applies to dict type events
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Mocking chevron rendering
    with patch("chevron.render", return_value="Test Alert"):
        enriched_event = enrichment_bl.run_extraction_rules(event)

    assert (
        enriched_event["name"] == "Test Alert"
    )  # Ensuring the attribute is correctly processed


def test_run_extraction_rules_no_rules(mock_session, mock_alert_dto):
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = (
        []
    )

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)
    result_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    assert (
        result_event == mock_alert_dto
    )  # Should return the original event if no rules apply


def test_run_extraction_rules_attribute_no_template(mock_session, mock_alert_dto):
    rule = ExtractionRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        attribute="name",  # No {{}} in attribute
        regex="Test",
        disabled=False,
        pre=True,
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    with patch("chevron.render", return_value="Test Alert"):
        enriched_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    assert (
        "name" not in enriched_event
    )  # Assuming the code does not modify the event if attribute is not in template format


def test_run_extraction_rules_empty_attribute_value(mock_session, mock_alert_dto):
    rule = ExtractionRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        attribute="{{ description }}",  # Assume description is empty
        regex=".*",
        disabled=False,
        pre=True,
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    with patch("chevron.render", return_value=""):
        enriched_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    assert enriched_event == mock_alert_dto  # Check if event is unchanged


def test_run_extraction_rules_handle_source_special_case(mock_session):
    event = {"name": "Test Alert", "source": "incorrect_format"}
    rule = ExtractionRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        attribute="{{ source }}",
        regex="(?P<source>incorrect_format)",
        disabled=False,
        pre=True,
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # We'll mock chevron to return the exact content of 'source' to simulate the template rendering
    with patch("chevron.render", return_value="incorrect_format"):
        # We need to mock 're.match' to return a match object with a groupdict that includes 'source'
        with patch(
            "re.match",
            return_value=Mock(groupdict=lambda: {"source": "incorrect_format"}),
        ):
            enriched_event = enrichment_bl.run_extraction_rules(event)

    # Assert that the event's 'source' is now a list with the updated source
    assert enriched_event["source"] == [
        "incorrect_format"
    ], "Source should be updated to a list containing the new source."


#### 2. Testing `run_extraction_rules` with CEL Conditions


def test_run_extraction_rules_with_conditions(mock_session, mock_alert_dto):
    rule = ExtractionRule(
        id=2,
        tenant_id="test_tenant",
        priority=1,
        attribute="{{ source[0] }}",
        regex="(?P<source_name>test_source)",
        disabled=False,
        pre=False,
        condition='source.includes("test_source")',
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]

    # Mocking the CEL environment to return True for the condition
    with patch("chevron.render", return_value="test_source"), patch(
        "celpy.Environment"
    ) as mock_env, patch("celpy.celpy.json_to_cel") as mock_json_to_cel:
        mock_env.return_value.compile.return_value = None
        mock_program = Mock()
        mock_env.return_value.program.return_value = mock_program
        mock_program.evaluate.return_value = True
        mock_json_to_cel.return_value = {}

        enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)
        enriched_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    # Assert that the event is now enriched with the source name from regex
    assert enriched_event.source_name == "test_source"


def test_run_mapping_rules_applies(mock_session, mock_alert_dto):
    # Setup a mapping rule
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=["name"],
        rows=[{"name": "Test Alert", "service": "new_service"}],
        disabled=False,
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    enrichment_bl.run_mapping_rules(mock_alert_dto)

    # Check if the alert's service is now updated to "new_service"
    assert mock_alert_dto.service == "new_service"
