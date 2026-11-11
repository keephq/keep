"""Actual native DB/router operations for incidents outside Inventory ownership."""
from uuid import uuid4

import pytest
from sqlalchemy import insert
from sqlmodel import Session

from test_contract import db, TENANT, PRIMARY, rows, Incident, AuthenticatedEntity
from keep.api.models.db.alert import Alert, AlertToIncident, LastAlert, LastAlertToIncident, AlertEnrichment, CommentMention


@pytest.fixture
def native(db, monkeypatch):
    from keep.api.core import db as native_db
    monkeypatch.setattr(native_db, 'engine', db)
    for model in (Alert, AlertToIncident, LastAlert, LastAlertToIncident, CommentMention):
        model.__table__.create(db, checkfirst=True)
    return native_db


def create_incident(db, fingerprint='fixture-unrelated-alert'):
    identifier = uuid4()
    with db.begin() as connection:
        connection.execute(insert(Incident.__table__).values(
            id=identifier, tenant_id=TENANT, fingerprint=fingerprint,
            user_generated_name='Fixture unrelated incident', user_summary='fixture',
            status='firing', severity=1, affected_services=[], sources=[]))
    return identifier


def test_unrelated_update_delete_and_enrichment_preserve_native_behavior(db, native):
    from keep.api.models.incident import IncidentDtoIn
    identifier = create_incident(db)
    native.update_incident_from_dto_by_id(TENANT, identifier,
                                        IncidentDtoIn(user_generated_name='Fixture updated', user_summary='updated'))
    assert native.get_incident_by_id(TENANT, identifier).user_generated_name == 'Fixture updated'
    native.enrich_entity(TENANT, 'fixture-ordinary', {'team': 'fixture'}, None, PRIMARY, 'fixture', audit_enabled=False)
    native.batch_enrich(TENANT, ['fixture-ordinary', 'fixture-other'], {'severity': 'low'}, None, PRIMARY, 'fixture', audit_enabled=False)
    enrichment = {row['alert_fingerprint']: row['enrichments'] for row in rows(db, AlertEnrichment)}
    assert enrichment['fixture-ordinary'] == {'team': 'fixture', 'severity': 'low'}
    assert enrichment['fixture-other'] == {'severity': 'low'}
    assert native.delete_incident_by_id(TENANT, identifier)
    assert native.get_incident_by_id(TENANT, identifier).status == 'deleted'


def test_unrelated_assign_ack_resolve_retain_native_audit_and_workflow_events(db, native, monkeypatch):
    from keep.api.routes.incidents import assign_incident
    from keep.api.bl.incidents_bl import IncidentBl
    from keep.api.models.db.incident import IncidentStatus
    from keep.api.bl.enrichments_bl import EnrichmentsBl
    identifier = create_incident(db)
    actor = AuthenticatedEntity(TENANT, PRIMARY, role='admin')
    events = []
    monkeypatch.setattr(IncidentBl, 'send_workflow_event', lambda self, dto, event: events.append((dto.id, event)))
    monkeypatch.setattr(IncidentBl, 'update_client_on_incident_change', lambda *args: None)
    monkeypatch.setattr(EnrichmentsBl, 'ENRICHMENT_DISABLED', True)
    with Session(db) as session:
        assert assign_incident(identifier, actor, session).status_code == 202
        lifecycle = IncidentBl(TENANT, session)
        lifecycle.change_status(identifier, IncidentStatus.ACKNOWLEDGED, actor)
        assert native.get_incident_by_id(TENANT, identifier).status == 'acknowledged'
        lifecycle.change_status(identifier, IncidentStatus.RESOLVED, actor)
    incident = native.get_incident_by_id(TENANT, identifier)
    assert incident.status == 'resolved'
    assert incident.end_time is not None
    assert incident.assignee == PRIMARY
    assert events == [(identifier, 'updated'), (identifier, 'updated')]


def test_unrelated_empty_merge_retains_native_result(db, native):
    source, destination = create_incident(db), create_incident(db)
    merged, failed = native.merge_incidents_to_id(TENANT, [source], destination, merged_by=PRIMARY)
    assert merged == [source]
    assert failed == []
    assert native.get_incident_by_id(TENANT, source).status == 'merged'


def test_unrelated_split_router_keeps_native_flow(db, native, monkeypatch):
    import asyncio
    from keep.api.routes.incidents import split_incident
    from keep.api.models.incident import SplitIncidentRequestDto
    from keep.api.bl.incidents_bl import IncidentBl
    source, destination = create_incident(db), create_incident(db)
    actor = AuthenticatedEntity(TENANT, PRIMARY, role='admin')
    events = []
    monkeypatch.setattr(IncidentBl, 'send_workflow_event', lambda self, dto, event: events.append(event))
    monkeypatch.setattr(IncidentBl, 'update_client_on_incident_change', lambda *args: None)
    with Session(db) as session:
        result = asyncio.run(split_incident(source, SplitIncidentRequestDto(
            alert_fingerprints=[], destination_incident_id=destination), actor, None, session))
    assert result.destination_incident_id == destination
    assert result.moved_alert_fingerprints == []
    assert native.get_incident_by_id(TENANT, source).status == 'firing'
    assert native.get_incident_by_id(TENANT, destination).status == 'firing'


def test_unrelated_disposable_enrichment_is_removed(db, native, monkeypatch):
    from keep.api.bl.enrichments_bl import EnrichmentsBl
    monkeypatch.setattr(EnrichmentsBl, 'ENRICHMENT_DISABLED', False)
    native.enrich_entity(TENANT, 'fixture-disposable',
                        {'team': 'fixture', 'status': 'resolved', 'disposable_status': True},
                        None, PRIMARY, 'fixture', audit_enabled=False)
    with Session(db) as session:
        EnrichmentsBl(TENANT, session).dispose_enrichments('fixture-disposable')
    enrichment = rows(db, AlertEnrichment)[0]['enrichments']
    assert enrichment == {'team': 'fixture'}


def test_unrelated_inventory_word_prefix_is_not_ownership(db, native):
    identifier = create_incident(db, fingerprint='inventory:unrelated-native-team')
    assert native.delete_incident_by_id(TENANT, identifier)
    assert native.get_incident_by_id(TENANT, identifier).status == 'deleted'


@pytest.mark.parametrize('timeout', [None, 5])
def test_native_slack_oauth_default_and_bounded_timeout_preserve_receipt(monkeypatch, timeout):
    from types import SimpleNamespace
    from keep.contextmanager.contextmanager import ContextManager
    from keep.providers.slack_provider.slack_provider import SlackProvider
    from keep.providers.models.provider_config import ProviderConfig
    from keep.providers.slack_provider import slack_provider
    calls = []
    def local_post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(ok=True, json=lambda: {'ok': True, 'ts': '1700000000.000001'})
    monkeypatch.setattr(slack_provider.requests, 'post', local_post)
    provider = SlackProvider(ContextManager(TENANT), 'fixture-slack',
                             ProviderConfig(authentication={'access_token': 'fixture-only'}))
    arguments = {} if timeout is None else {'request_timeout': timeout}
    receipt = provider._notify(message='fixture', channel='FIXTURE', **arguments)
    assert receipt == {'slack_timestamp': '1700000000.000001'}
    assert len(calls) == 1
    assert calls[0][1]['timeout'] == timeout
    assert calls[0][1]['json']['text'] == 'fixture'
