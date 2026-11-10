"""Execute the exact candidate detector against fixture-only PostgreSQL 16+."""
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import text

from test_contract import db, policy, clock, TENANT, JOB
from test_runtime import config, OfflineOAuthSlack
from keep.api.bl.inventory_attention_runtime import InventoryWorkflow, NativeSlackNotifier


@pytest.fixture
def detector_db(db):
    if db.dialect.name != 'postgresql':
        pytest.skip('Actual detector SQL requires the isolated PostgreSQL runner')
    with db.begin() as connection:
        connection.execute(text('CREATE TABLE queue_job (id integer PRIMARY KEY, uuid text, graph_uuid text, records text, state text, channel text)'))
        connection.execute(text('CREATE TABLE inventory_orchestrator (id bigint PRIMARY KEY, state text)'))
        connection.execute(text("INSERT INTO inventory_orchestrator VALUES (42, 'done')"))
    return db


def reference(ids, model='inventory.orchestrator'):
    return json.dumps({'_type': 'odoo_recordset', 'model': model, 'ids': ids})


def execute_detector(db):
    path = Path(__file__).parent / 'fixtures/detector.sql'
    if os.environ.get('OAC_CANDIDATE_ROOT'):
        assert path.read_text() == (Path(os.environ['OAC_CANDIDATE_ROOT']) / 'candidates/inventory-attention/detector.sql').read_text()
    with db.begin() as connection:
        connection.execute(text("SET LOCAL statement_timeout='5s'"))
        connection.execute(text('SET TRANSACTION READ ONLY'))
        assert connection.execute(text('SHOW transaction_read_only')).scalar() == 'on'
        return list(connection.execute(text(path.read_text())).mappings())


def insert_jobs(db, records):
    with db.begin() as connection:
        connection.execute(text("INSERT INTO queue_job VALUES (:id,:uuid,NULL,:records,'failed','root.inventory_orchestrator')"),
                           [{'id': i, 'uuid': JOB if i == 1 else f'fixture-job-{i}', 'records': value}
                            for i, value in enumerate(records, 1)])


def test_actual_sql_safe_operation_correlation_and_done_remains_open(detector_db, config, clock):
    insert_jobs(detector_db, [reference([42]), reference([42, 43]), '{malformed', None,
                             reference([99]), reference([42], 'other.model'), reference(['x']), reference(['42']),
                             json.dumps({'_type': 'odoo_recordset', 'model': 'inventory.orchestrator', 'ids': 42})])
    results = execute_detector(detector_db)
    assert len(results) == 9
    assert results[0]['operation_id'] == '42'
    assert results[0]['business_state'] == 'done'
    assert all(row['operation_id'] == '' for row in results[1:])
    assert all(row['coverage'] == 'retained_only' for row in results)
    row = dict(results[0])
    row.update(fingerprint='fixture-sql-alert', lastReceived=clock(), status='firing')
    slack = OfflineOAuthSlack()
    workflow = InventoryWorkflow(detector_db, TENANT, config, NativeSlackNotifier(slack, config), clock)
    state = workflow.run('ingest', row)
    assert state['correlation']['operation_id'] == '42'
    assert state['status'] == 'open'
    assert 'business_success_unverified' in row['correlation_evidence']


def test_actual_sql_cap_marks_truncation_instead_of_complete_coverage(detector_db):
    insert_jobs(detector_db, [reference([42])] * 101)
    results = execute_detector(detector_db)
    assert len(results) == 100
    assert {row['coverage'] for row in results} == {'truncated'}
