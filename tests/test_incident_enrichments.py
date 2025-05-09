import pytest
from datetime import datetime, timezone
from uuid import uuid4

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.models.action_type import ActionType
from keep.api.models.alert import EnrichIncidentRequestBody, UnEnrichIncidentRequestBody
from keep.api.core.db import get_incident_by_id, get_enrichment
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.incident import IncidentDto, IncidentDtoIn, IncidentStatus, IncidentSeverity

@pytest.fixture
def enrichments_bl(db_session):
    return EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, session=db_session)

@pytest.fixture
def sample_incident(db_session):
    incident_dto = IncidentDtoIn(
        name="Test Incident",
        summary="Test incident for enrichment testing",
        status=IncidentStatus.open,
        severity=IncidentSeverity.high,
        assignee="test@example.com"
    )
    incident = IncidentDto.from_dto_in(incident_dto)
    return incident

def test_enrich_incident(enrichments_bl, sample_incident):
    # Test enriching an incident with new data
    enrichment_data = {
        "environment": "production",
        "region": "us-west-2",
        "team": "platform"
    }
    
    enrichments_bl.enrich_entity(
        entity_id=str(sample_incident.id),
        enrichments=enrichment_data,
        action_type=ActionType.INCIDENT_ENRICH,
        action_callee="test",
        action_description="Test enrichment"
    )
    
    # Verify enrichment was added
    enrichment = get_enrichment(
        tenant_id=SINGLE_TENANT_UUID,
        entity_id=str(sample_incident.id)
    )
    
    assert enrichment is not None
    assert enrichment.enrichments == enrichment_data

def test_update_incident_enrichment(enrichments_bl, sample_incident):
    # Initial enrichment
    initial_data = {"environment": "staging"}
    enrichments_bl.enrich_entity(
        entity_id=str(sample_incident.id),
        enrichments=initial_data,
        action_type=ActionType.INCIDENT_ENRICH,
        action_callee="test",
        action_description="Initial enrichment"
    )
    
    # Update enrichment
    updated_data = {"environment": "production"}
    enrichments_bl.enrich_entity(
        entity_id=str(sample_incident.id),
        enrichments=updated_data,
        action_type=ActionType.INCIDENT_ENRICH,
        action_callee="test",
        action_description="Updated enrichment"
    )
    
    # Verify enrichment was updated
    enrichment = get_enrichment(
        tenant_id=SINGLE_TENANT_UUID,
        entity_id=str(sample_incident.id)
    )
    
    assert enrichment.enrichments["environment"] == "production"

def test_remove_incident_enrichment(enrichments_bl, sample_incident):
    # Add initial enrichment
    initial_data = {
        "environment": "production",
        "region": "us-west-2"
    }
    enrichments_bl.enrich_entity(
        entity_id=str(sample_incident.id),
        enrichments=initial_data,
        action_type=ActionType.INCIDENT_ENRICH,
        action_callee="test",
        action_description="Initial enrichment"
    )
    
    # Remove one enrichment field
    enrichments_bl.unenrich_entity(
        entity_id=str(sample_incident.id),
        fields=["environment"],
        action_callee="test",
        action_description="Remove environment enrichment"
    )
    
    # Verify field was removed
    enrichment = get_enrichment(
        tenant_id=SINGLE_TENANT_UUID,
        entity_id=str(sample_incident.id)
    )
    
    assert "environment" not in enrichment.enrichments
    assert "region" in enrichment.enrichments
    assert enrichment.enrichments["region"] == "us-west-2"

def test_enrich_incident_with_invalid_data(enrichments_bl, sample_incident):
    # Test enriching with invalid data types
    invalid_data = {
        "invalid_field": object()  # Non-serializable object
    }
    
    with pytest.raises(TypeError):
        enrichments_bl.enrich_entity(
            entity_id=str(sample_incident.id),
            enrichments=invalid_data,
            action_type=ActionType.INCIDENT_ENRICH,
            action_callee="test",
            action_description="Invalid enrichment"
        )

def test_enrich_nonexistent_incident(enrichments_bl):
    # Test enriching an incident that doesn't exist
    nonexistent_id = str(uuid4())
    enrichment_data = {"environment": "production"}
    
    enrichments_bl.enrich_entity(
        entity_id=nonexistent_id,
        enrichments=enrichment_data,
        action_type=ActionType.INCIDENT_ENRICH,
        action_callee="test",
        action_description="Enrichment for nonexistent incident"
    )
    
    # Verify enrichment was still created
    enrichment = get_enrichment(
        tenant_id=SINGLE_TENANT_UUID,
        entity_id=nonexistent_id
    )
    
    assert enrichment is not None
    assert enrichment.enrichments == enrichment_data

def test_bulk_enrich_incidents(enrichments_bl, sample_incident):
    # Create multiple incidents
    incidents = [sample_incident]
    enrichment_data = {"environment": "production"}
    
    # Bulk enrich incidents
    for incident in incidents:
        enrichments_bl.enrich_entity(
            entity_id=str(incident.id),
            enrichments=enrichment_data,
            action_type=ActionType.INCIDENT_ENRICH,
            action_callee="test",
            action_description="Bulk enrichment"
        )
    
    # Verify all incidents were enriched
    for incident in incidents:
        enrichment = get_enrichment(
            tenant_id=SINGLE_TENANT_UUID,
            entity_id=str(incident.id)
        )
        assert enrichment is not None
        assert enrichment.enrichments == enrichment_data