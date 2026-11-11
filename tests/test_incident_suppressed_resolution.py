"""
Unit tests for Issue #6914:
resolve_on all_resolved closing an incident holding a suppressed alert (e.g. Sentry 'ignored').
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from keep.api.bl.incidents_bl import IncidentBl
from keep.api.core.db import (
    is_all_alerts_in_status,
    is_all_alerts_resolved,
    is_first_incident_alert_resolved,
    is_last_incident_alert_resolved,
)
from keep.api.models.alert import AlertStatus
from keep.api.models.db.alert import (
    Alert,
    AlertEnrichment,
    Incident,
    LastAlert,
    LastAlertToIncident,
)
from keep.api.models.db.incident import IncidentStatus
from keep.api.models.db.rule import ResolveOn
from keep.api.models.db.tenant import Tenant


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        # Create default tenant to ensure any relational hooks are satisfied
        t = Tenant(id="test-tenant", name="test-tenant")
        s.add(t)
        s.commit()
        yield s


def _add_alert_to_incident(
    session: Session,
    tenant_id: str,
    fingerprint: str,
    status: AlertStatus,
    incident_id: uuid.UUID,
    enriched_status: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> Alert:
    a_id = uuid.uuid4()
    now = timestamp or datetime.now(timezone.utc)
    alert = Alert(
        id=a_id,
        tenant_id=tenant_id,
        provider_type="sentry",
        fingerprint=fingerprint,
        timestamp=now,
        event={"status": status.value},
    )
    last_alert = LastAlert(
        tenant_id=tenant_id,
        fingerprint=fingerprint,
        alert_id=a_id,
        timestamp=now,
        first_timestamp=now,
    )
    link = LastAlertToIncident(
        tenant_id=tenant_id,
        fingerprint=fingerprint,
        incident_id=incident_id,
    )
    session.add(alert)
    session.add(last_alert)
    session.add(link)
    if enriched_status is not None:
        enrichment = AlertEnrichment(
            tenant_id=tenant_id,
            alert_fingerprint=fingerprint,
            enrichments={"status": enriched_status},
        )
        session.add(enrichment)
    session.commit()
    return alert


def test_is_all_alerts_resolved_with_suppressed_alert(session: Session):
    tenant_id = "test-tenant"
    incident_id = uuid.uuid4()

    incident = Incident(
        id=incident_id,
        tenant_id=tenant_id,
        user_summary="Test incident with resolved and suppressed alerts",
        resolve_on=ResolveOn.ALL.value,
        alerts_count=2,
        status=IncidentStatus.FIRING.value,
    )
    session.add(incident)
    session.commit()

    # Alert 1: RESOLVED
    _add_alert_to_incident(session, tenant_id, "fp-resolved", AlertStatus.RESOLVED, incident_id)
    # Alert 2: SUPPRESSED (e.g. Sentry ignored)
    _add_alert_to_incident(session, tenant_id, "fp-suppressed", AlertStatus.SUPPRESSED, incident_id)

    # When include_suppressed=True (default), both alerts are terminal -> incident resolves
    assert is_all_alerts_resolved(incident=incident, session=session) is True

    # When include_suppressed=False, suppressed alert blocks resolution
    assert (
        is_all_alerts_resolved(
            incident=incident, session=session, include_suppressed=False
        )
        is False
    )


def test_is_all_alerts_resolved_blocks_on_firing_alert(session: Session):
    tenant_id = "test-tenant"
    incident_id = uuid.uuid4()

    incident = Incident(
        id=incident_id,
        tenant_id=tenant_id,
        user_summary="Test incident with active alert",
        resolve_on=ResolveOn.ALL.value,
        alerts_count=3,
        status=IncidentStatus.FIRING.value,
    )
    session.add(incident)
    session.commit()

    _add_alert_to_incident(session, tenant_id, "fp-1", AlertStatus.RESOLVED, incident_id)
    _add_alert_to_incident(session, tenant_id, "fp-2", AlertStatus.SUPPRESSED, incident_id)
    _add_alert_to_incident(session, tenant_id, "fp-3", AlertStatus.FIRING, incident_id)

    # Firing alert must prevent resolution
    assert is_all_alerts_resolved(incident=incident, session=session) is False


def test_is_all_alerts_resolved_with_enrichment_status(session: Session):
    tenant_id = "test-tenant"
    incident_id = uuid.uuid4()

    incident = Incident(
        id=incident_id,
        tenant_id=tenant_id,
        user_summary="Test incident with enrichment",
        resolve_on=ResolveOn.ALL.value,
        alerts_count=1,
        status=IncidentStatus.FIRING.value,
    )
    session.add(incident)
    session.commit()

    # Alert event says firing, but enrichment marks it suppressed
    _add_alert_to_incident(
        session,
        tenant_id,
        "fp-enriched",
        AlertStatus.FIRING,
        incident_id,
        enriched_status=AlertStatus.SUPPRESSED.value,
    )

    # Enriched status = suppressed should resolve the incident
    assert is_all_alerts_resolved(incident=incident, session=session) is True


def test_resolve_incident_if_require_closes_incident_with_suppressed(session: Session):
    tenant_id = "test-tenant"
    incident_id = uuid.uuid4()

    incident = Incident(
        id=incident_id,
        tenant_id=tenant_id,
        user_summary="Closing incident",
        resolve_on=ResolveOn.ALL.value,
        alerts_count=2,
        status=IncidentStatus.FIRING.value,
    )
    session.add(incident)
    session.commit()

    # Alert 1 resolved, Alert 2 suppressed
    _add_alert_to_incident(session, tenant_id, "fp-res", AlertStatus.RESOLVED, incident_id)
    _add_alert_to_incident(session, tenant_id, "fp-sup", AlertStatus.SUPPRESSED, incident_id)

    bl = IncidentBl(tenant_id=tenant_id, session=session)
    bl.send_workflow_event = MagicMock()

    resolved_incident = bl.resolve_incident_if_require(incident)
    assert resolved_incident.status == IncidentStatus.RESOLVED.value
    bl.send_workflow_event.assert_called_once()


def test_resolve_incident_if_require_with_all_or_suppressed_enum(session: Session):
    tenant_id = "test-tenant"
    incident_id = uuid.uuid4()

    incident = Incident(
        id=incident_id,
        tenant_id=tenant_id,
        user_summary="Closing incident via ALL_OR_SUPPRESSED",
        resolve_on=ResolveOn.ALL_OR_SUPPRESSED.value,
        alerts_count=2,
        status=IncidentStatus.FIRING.value,
    )
    session.add(incident)
    session.commit()

    _add_alert_to_incident(session, tenant_id, "fp-res-2", AlertStatus.RESOLVED, incident_id)
    _add_alert_to_incident(session, tenant_id, "fp-sup-2", AlertStatus.SUPPRESSED, incident_id)

    bl = IncidentBl(tenant_id=tenant_id, session=session)
    bl.send_workflow_event = MagicMock()

    resolved_incident = bl.resolve_incident_if_require(incident)
    assert resolved_incident.status == IncidentStatus.RESOLVED.value
    bl.send_workflow_event.assert_called_once()
