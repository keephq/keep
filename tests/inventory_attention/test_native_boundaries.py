"""Native formatter, template renderer, provider and mutation-boundary regressions."""
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import HTTPException

from test_contract import db, policy, clock, TENANT, JOB, GRAPH, rows, Incident
from test_runtime import config, OfflineOAuthSlack, OfflineWebhook


@pytest.fixture
def configured_file(tmp_path, config, monkeypatch):
    monkeypatch.setenv('AUTH_TYPE', 'db')
    monkeypatch.setenv('KEEP_IMPERSONATION_ENABLED', 'false')
    config['slack_provider_id'] = 'fixture-oauth-installation'
    path = tmp_path / 'fixture-policy.json'
    path.write_text(json.dumps({'tenants': {TENANT: config}}))
    monkeypatch.setenv('INVENTORY_ATTENTION_POLICY_FILE', str(path))
    return config


def formatted_alert():
    from keep.providers.grafana_provider.grafana_provider import GrafanaProvider
    # Synthetic webhook matching the candidate rule. No fabricated timestamp label.
    webhook = {'title': 'Inventory retained failure candidate', 'status': 'firing',
               'alerts': [{'fingerprint': 'fixture-rule-fingerprint', 'labels': {
                   'inventory_attention_owner': 'inventory-attention-v1',
                   'inventory_kind': 'parent_failed', 'queue_state': 'failed',
                   'job_uuid': JOB, 'graph_uuid': GRAPH},
                   'annotations': {'description': 'Fixture retained failure'}}]}
    return GrafanaProvider._format_alert(webhook)[0]


def test_native_formatter_template_provider_circuit(db, configured_file, monkeypatch):
    from keep.contextmanager.contextmanager import ContextManager
    from keep.iohandler.iohandler import IOHandler
    from keep.providers.inventory_attention_provider.inventory_attention_provider import InventoryAttentionProvider
    from keep.providers.models.provider_config import ProviderConfig
    from keep.providers.providers_factory import ProvidersFactory
    from keep.api.core import db as native_db
    from keep.api.bl.inventory_attention import InventoryAttentionService, Policy
    import yaml

    formatted = formatted_alert()
    assert not hasattr(formatted, 'inventory_observed_at')
    assert formatted.annotations['description'] == 'Fixture retained failure'
    context = ContextManager(TENANT)
    context.event_context = formatted
    candidate = Path(__file__).parent / 'fixtures/inventory-attention.yaml'
    if os.environ.get('OAC_CANDIDATE_ROOT'):
        source = Path(os.environ['OAC_CANDIDATE_ROOT']) / 'workflows/keep/inventory-attention.yaml'
        assert candidate.read_text() == source.read_text()
    payload = yaml.safe_load(candidate.read_text())['workflow']['actions'][0]['provider']['with']
    rendered = IOHandler(context).render_context(payload)
    assert isinstance(rendered['alert'], dict)
    slack = OfflineOAuthSlack()
    monkeypatch.setattr(native_db, 'engine', db)
    monkeypatch.setattr(ProvidersFactory, 'get_installed_provider', lambda *args: OfflineWebhook() if args[-1] == 'webhook' else slack)
    provider = InventoryAttentionProvider(context, 'fixture-inventory-provider', ProviderConfig(authentication={}))
    state = provider._notify(**rendered)
    repeated = provider._notify(**rendered)
    assert state['incident_id'] == repeated['incident_id']
    assert len(rows(db, Incident)) == len(slack.calls) == 1
    assert state['last_observed_at'] == datetime.fromisoformat(formatted.lastReceived.replace('Z', '+00:00')).timestamp()
    assert state['correlation'].get('operation_id') is None
    assert 'operation_id' in state['missing']
    assert 'source_order_unknown' in state['evidence']['completeness']


def test_inactive_native_provider_performs_no_database_or_slack_lookup(monkeypatch):
    from keep.contextmanager.contextmanager import ContextManager
    from keep.providers.inventory_attention_provider.inventory_attention_provider import InventoryAttentionProvider
    from keep.providers.models.provider_config import ProviderConfig
    from keep.providers.providers_factory import ProvidersFactory
    monkeypatch.delenv('INVENTORY_ATTENTION_POLICY_FILE', raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError('Inactive provider attempted external lookup')
    monkeypatch.setattr(ProvidersFactory, 'get_installed_provider', forbidden)
    provider = InventoryAttentionProvider(ContextManager(TENANT), 'fixture', ProviderConfig(authentication={}))
    assert provider._notify(operation='ingest', alert={}) == {'status': 'disabled'}
    assert provider._notify(operation='sweep') == {'status': 'disabled'}


def test_actual_core_mutation_entrypoints_reject_reserved_state(db, policy, clock, monkeypatch):
    from keep.api.core import db as native_db
    from keep.api.bl.inventory_attention import InventoryAttentionService
    from test_contract import signal
    monkeypatch.setattr(native_db, 'engine', db)
    service = InventoryAttentionService(db, TENANT, policy, clock=clock)
    state = service.ingest(signal(clock))
    incident_id = UUID(state['incident_id'])
    calls = [
        lambda: native_db.enrich_entity(TENANT, 'inventory-policy:fixture', {}, None, 'fixture', 'fixture'),
        lambda: native_db.batch_enrich(TENANT, ['inventory-policy:fixture'], {}, None, 'fixture', 'fixture'),
        lambda: native_db.update_incident_from_dto_by_id(TENANT, incident_id, None),
        lambda: native_db.delete_incident_by_id(TENANT, incident_id),
        lambda: native_db.merge_incidents_to_id(TENANT, [incident_id], incident_id),
    ]
    for call in calls:
        with pytest.raises(HTTPException) as rejected:
            call()
        assert rejected.value.status_code == 409
    assert service.snapshot(str(incident_id))['status'] == 'open'


@pytest.mark.parametrize('actor_kind,expected', [('human', 200), ('api_key', 403), ('wrong_tenant', 404), ('resolve', 409), ('assign', 409)])
def test_native_http_status_uses_authenticated_identity(db, configured_file, policy, clock, monkeypatch, actor_kind, expected):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlmodel import Session
    from keep.api.routes import incidents
    from keep.api.core import db as native_db
    from keep.api.bl.inventory_attention import InventoryAttentionService
    from keep.identitymanager.authenticatedentity import AuthenticatedEntity
    from test_contract import signal, PRIMARY
    service = InventoryAttentionService(db, TENANT, policy, clock=clock)
    state = service.ingest(signal(clock))
    monkeypatch.setattr(native_db, 'engine', db)
    actor = AuthenticatedEntity(tenant_id='wrong-fixture-tenant' if actor_kind == 'wrong_tenant' else TENANT,
                                email=PRIMARY, api_key_name='fixture-key' if actor_kind == 'api_key' else None)
    app = FastAPI()
    app.include_router(incidents.router, prefix='/incidents')
    def local_session():
        with Session(db) as session:
            yield session
    app.dependency_overrides[native_db.get_session] = local_session
    route = next(r for r in incidents.router.routes if r.path == '/{incident_id}/status')
    auth = next(d.call for d in route.dependant.dependencies if d.name == 'authenticated_entity')
    app.dependency_overrides[auth] = lambda: actor
    assign_route = next(r for r in incidents.router.routes if r.path == '/{incident_id}/assign')
    assign_auth = next(d.call for d in assign_route.dependant.dependencies if d.name == 'authenticated_entity')
    app.dependency_overrides[assign_auth] = lambda: actor
    with TestClient(app) as client:
        response = client.post(f"/incidents/{state['incident_id']}/{'assign' if actor_kind == 'assign' else 'status'}", json={
            'status': 'resolved' if actor_kind == 'resolve' else 'acknowledged', 'comment': 'fixture', 'actor': 'forged@example.invalid'})
    assert response.status_code == expected, response.text
    durable = service.snapshot(state['incident_id'])
    if expected == 200:
        assert durable['ack']['actor'] == PRIMARY
    else:
        assert durable['ack'] is None


@pytest.mark.parametrize('filename', ['inventory-attention.yaml', 'inventory-attention-sweep.yaml'])
def test_native_parser_disabled_candidates(db, monkeypatch, filename):
    import yaml
    from keep.parser.parser import Parser
    from keep.api.core import db as native_db
    from keep.providers.providers_factory import ProvidersFactory
    from keep.providers.inventory_attention_provider.inventory_attention_provider import InventoryAttentionProvider
    monkeypatch.setattr(native_db, 'engine', db)
    fixture = Path(__file__).parent / 'fixtures' / filename
    if os.environ.get('OAC_CANDIDATE_ROOT'):
        source = Path(os.environ['OAC_CANDIDATE_ROOT']) / 'workflows/keep' / filename
        assert fixture.read_text() == source.read_text()
    parsed = Parser().parse(None, yaml.safe_load(fixture.read_text()), is_test=True,
                            workflow_db_id='fixture-parser-workflow')
    assert len(parsed) == 1
    assert parsed[0].workflow_disabled is True
    assert ProvidersFactory.get_provider_class('inventory_attention') is InventoryAttentionProvider


def test_owned_incident_uuid_enrichment_cannot_forge_status_or_owner(db, policy, clock, monkeypatch):
    from keep.api.core import db as native_db
    from keep.api.bl.inventory_attention import InventoryAttentionService
    from test_contract import signal
    monkeypatch.setattr(native_db, 'engine', db)
    service = InventoryAttentionService(db, TENANT, policy, clock=clock)
    state = service.ingest(signal(clock))
    with pytest.raises(HTTPException) as rejected:
        native_db.enrich_entity(TENANT, state['incident_id'], {'status': 'resolved', 'assignee': 'forged'},
                               None, 'fixture', 'fixture', audit_enabled=False)
    assert rejected.value.status_code == 409
    assert service.snapshot(state['incident_id'])['ack'] is None


def test_split_and_unenrich_entrypoints_guard_owned_state(db, policy, clock, monkeypatch):
    import asyncio
    from sqlmodel import Session
    from keep.api.routes import incidents
    from keep.api.core import db as native_db
    from keep.api.bl.enrichments_bl import EnrichmentsBl
    from keep.api.bl.inventory_attention import InventoryAttentionService
    from keep.api.models.incident import SplitIncidentRequestDto
    from test_contract import signal, AuthenticatedEntity, PRIMARY
    monkeypatch.setattr(native_db, 'engine', db)
    service = InventoryAttentionService(db, TENANT, policy, clock=clock)
    state = service.ingest(signal(clock))
    actor = AuthenticatedEntity(tenant_id=TENANT, email=PRIMARY)
    with Session(db) as session:
        with pytest.raises(HTTPException) as rejected:
            asyncio.run(incidents.split_incident(UUID(state['incident_id']),
                        SplitIncidentRequestDto(alert_fingerprints=[], destination_incident_id=UUID(state['incident_id'])),
                        actor, None, session))
        assert rejected.value.status_code == 409
        monkeypatch.setattr(EnrichmentsBl, 'ENRICHMENT_DISABLED', True)
        enrichment = EnrichmentsBl(TENANT, session)
        with pytest.raises(HTTPException) as dispose:
            enrichment.dispose_enrichments('inventory-policy:fixture')
        assert dispose.value.status_code == 409
