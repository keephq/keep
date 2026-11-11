"""Inactive protocol exits native process_event before DB or formatter I/O."""
from types import SimpleNamespace

import pytest

from test_contract import TENANT
from keep.api.bl.inventory_attention_runtime import filter_inactive_inventory


OWNED = {'fingerprint': 'fixture-owned', 'labels': {'inventory_attention_owner': 'inventory-attention-v1'}}
UNRELATED = {'fingerprint': 'fixture-other', 'labels': {'team': 'fixture'}}


@pytest.mark.parametrize('payload', [OWNED, [OWNED], {'alerts': [OWNED]},
    SimpleNamespace(inventory_attention_owner='inventory-attention-v1')])
def test_inactive_actual_processing_entrypoint_performs_zero_io(monkeypatch, payload):
    from keep.api.tasks import process_event_task
    monkeypatch.delenv('INVENTORY_ATTENTION_POLICY_FILE', raising=False)
    calls = []
    def forbidden(*args, **kwargs):
        calls.append('attempted_io')
        raise AssertionError('Inactive candidate must exit before session/format/workflow')
    monkeypatch.setattr(process_event_task, 'get_session_sync', forbidden)
    monkeypatch.setattr(process_event_task.ProvidersFactory, 'get_provider_class', forbidden)
    result = process_event_task.process_event({}, TENANT, 'grafana', 'fixture', None, 'fixture', 'fixture', payload)
    assert result == []
    assert calls == []


@pytest.mark.parametrize('payload,expected', [
    ([OWNED, UNRELATED], [UNRELATED]),
    ({'title': 'fixture', 'alerts': [OWNED, UNRELATED]}, {'title': 'fixture', 'alerts': [UNRELATED]}),
    (UNRELATED, UNRELATED),
    ({'labels': None, 'name': 'legacy'}, {'labels': None, 'name': 'legacy'}),
])
def test_inactive_mixed_batch_preserves_other_native_payloads(monkeypatch, payload, expected):
    monkeypatch.delenv('INVENTORY_ATTENTION_POLICY_FILE', raising=False)
    assert filter_inactive_inventory(TENANT, payload) == expected


def test_actual_oac_routing_excludes_only_owned_signal_from_generic_workflow():
    import os
    from pathlib import Path
    import celpy
    import yaml
    root = Path(os.environ.get('OAC_CANDIDATE_ROOT', '/tmp/inventory-pipeline-oac'))
    if not root.is_dir():
        pytest.skip('OAC candidate source required')
    def expression(filename):
        definition = yaml.safe_load((root / 'workflows/keep' / filename).read_text())
        return definition['workflow']['triggers'][0]['cel']
    environment = celpy.Environment()
    generic = environment.program(environment.compile(expression('grafana-alerts.yaml')))
    inventory = environment.program(environment.compile(expression('inventory-attention.yaml')))
    for marker, expected_generic, expected_inventory in [
        (None, True, False), ('unrelated-team', True, False), ('inventory-attention-v1', False, True),
    ]:
        payload = {'source': ['grafana']}
        if marker is not None:
            payload['inventory_attention_owner'] = marker
        activation = celpy.json_to_cel(payload)
        assert bool(generic.evaluate(activation)) is expected_generic
        assert bool(inventory.evaluate(activation)) is expected_inventory
