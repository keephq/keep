"""Contract pins the composite key observed after real upstream migrations.

This metadata fixture is not a migration test. The full isolated image runs
actual upstream migrations separately; that evidence is required in addition.
"""
from sqlalchemy import inspect, insert

from test_contract import db, policy, clock, signal, TENANT
from keep.api.bl.inventory_attention import InventoryAttentionService
from keep.api.models.db.tenant import Tenant
from keep.api.models.db.alert import AlertEnrichment
from uuid import uuid4


def test_enrichment_fixture_matches_observed_tenant_scoped_migration(db):
    constraints = inspect(db).get_unique_constraints('alertenrichment')
    assert any(set(item['column_names']) == {'tenant_id', 'alert_fingerprint'} for item in constraints)
    assert not any(item['column_names'] == ['alert_fingerprint'] for item in constraints)
    other = 'fixture-other-tenant'
    with db.begin() as connection:
        connection.execute(insert(Tenant.__table__).values(id=other, name='Fixture other tenant'))
        for tenant in (TENANT, other):
            connection.execute(insert(AlertEnrichment.__table__).values(
                id=uuid4(), tenant_id=tenant, alert_fingerprint='fixture-same-fingerprint', enrichments={}))


def test_inventory_upsert_deduplicates_on_actual_composite_key(db, policy, clock):
    service = InventoryAttentionService(db, TENANT, policy, clock=clock)
    first = service.ingest(signal(clock))
    second = service.ingest(signal(clock))
    assert second['incident_id'] == first['incident_id']
    assert second['primary_due_at'] == first['primary_due_at']
