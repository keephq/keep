"""Tests for keep.api.bl.correlation_rules_provisioning.provision_correlation_rules_from_env.

Mirrors tests/test_mapping_rules_provisioning.py by using the real in-memory SQLite
`db_session` fixture from tests/conftest.py rather than patching DB helpers, and
drives the provisioner through the KEEP_CORRELATION_RULES env var (a JSON array of
specs matching the POST /rules schema), the same way deduplication rules are
provisioned from env.
"""

import json

from sqlmodel import Session, select

import keep.api.core.db as db
from keep.api.bl.correlation_rules_provisioning import (
    provision_correlation_rules_from_env,
)
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.rule import Rule

ENV_VAR = "KEEP_CORRELATION_RULES"


def _spec(name, cel_query='severity == "critical"', **overrides):
    spec = {
        "ruleName": name,
        "celQuery": cel_query,
        "sqlQuery": {"sql": "severity = :severity", "params": {"severity": "critical"}},
        "timeframeInSeconds": 600,
        "timeUnit": "seconds",
        "groupingCriteria": [],
        "createOn": "any",
        "resolveOn": "never",
        "threshold": 1,
    }
    spec.update(overrides)
    return spec


def _set_env(monkeypatch, *specs):
    monkeypatch.setenv(ENV_VAR, json.dumps(list(specs)))


def _provisioned_rules():
    return [rule for rule in db.get_rules(SINGLE_TENANT_UUID) if rule.is_provisioned]


def _all_rules():
    with Session(db.engine) as session:
        return session.exec(
            select(Rule).where(Rule.tenant_id == SINGLE_TENANT_UUID)
        ).all()


def test_creates_new_rule(monkeypatch, db_session):
    """Empty DB + one spec in env -> rule created and marked provisioned."""
    _set_env(monkeypatch, _spec("critical-alerts-correlation"))

    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)

    rules = _provisioned_rules()
    assert len(rules) == 1
    rule = rules[0]
    assert rule.name == "critical-alerts-correlation"
    assert rule.is_provisioned is True
    assert rule.definition_cel == 'severity == "critical"'
    assert rule.definition == {
        "sql": "severity = :severity",
        "params": {"severity": "critical"},
    }
    assert rule.timeframe == 600
    assert rule.created_by == "system"


def test_provisions_multiple_rules(monkeypatch, db_session):
    _set_env(monkeypatch, _spec("rule-a"), _spec("rule-b"))

    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)

    names = sorted(rule.name for rule in _provisioned_rules())
    assert names == ["rule-a", "rule-b"]


def test_is_idempotent(monkeypatch, db_session):
    """Running provisioning twice does not create duplicates."""
    _set_env(monkeypatch, _spec("rule-a"), _spec("rule-b"))

    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)
    first_ids = sorted(str(rule.id) for rule in _provisioned_rules())
    assert len(first_ids) == 2

    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)
    second_ids = sorted(str(rule.id) for rule in _provisioned_rules())

    assert first_ids == second_ids


def test_updates_existing_provisioned_rule(monkeypatch, db_session):
    """A previously-provisioned rule gets its content refreshed from the env, id preserved."""
    _set_env(monkeypatch, _spec("rule-a", timeframeInSeconds=600))
    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)
    original = _provisioned_rules()[0]
    original_id = original.id

    # Simulate drift (someone edited the rule directly)
    with Session(db.engine) as session:
        rule = session.exec(select(Rule).where(Rule.id == original_id)).first()
        rule.timeframe = 42
        session.add(rule)
        session.commit()

    # Re-provision with the env value -> timeframe reset to 600
    _set_env(monkeypatch, _spec("rule-a", timeframeInSeconds=600))
    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)

    refreshed = _provisioned_rules()
    assert len(refreshed) == 1
    assert refreshed[0].id == original_id
    assert refreshed[0].timeframe == 600


def test_deprovisions_rule_removed_from_env(monkeypatch, db_session):
    _set_env(monkeypatch, _spec("rule-a"), _spec("rule-b"))
    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)
    assert len(_provisioned_rules()) == 2

    _set_env(monkeypatch, _spec("rule-a"))
    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)

    remaining = _provisioned_rules()
    assert len(remaining) == 1
    assert remaining[0].name == "rule-a"


def test_deprovisions_all_when_env_unset(monkeypatch, db_session):
    _set_env(monkeypatch, _spec("rule-a"), _spec("rule-b"))
    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)
    assert len(_provisioned_rules()) == 2

    monkeypatch.delenv(ENV_VAR)
    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)

    assert len(_provisioned_rules()) == 0


def test_leaves_ui_rules_untouched(monkeypatch, db_session):
    """A UI-created rule (is_provisioned=False) is never deleted or modified."""
    ui_rule = db.create_rule(
        tenant_id=SINGLE_TENANT_UUID,
        name="ui-only-rule",
        definition={"sql": "1=1", "params": {}},
        timeframe=300,
        timeunit="seconds",
        definition_cel='source == "grafana"',
        created_by="ui-user@example.com",
    )
    ui_rule_id = ui_rule.id

    _set_env(monkeypatch, _spec("provisioned-rule"))
    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)

    all_rules = _all_rules()
    assert len(all_rules) == 2
    ui = next(rule for rule in all_rules if rule.id == ui_rule_id)
    assert ui.is_provisioned is False
    assert ui.timeframe == 300


def test_invalid_cel_is_skipped(monkeypatch, db_session):
    """A spec with an unparseable celQuery is skipped; valid specs still provision."""
    _set_env(
        monkeypatch,
        _spec("valid-rule"),
        _spec("broken-rule", cel_query="severity == "),
    )

    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)

    rules = _provisioned_rules()
    assert len(rules) == 1
    assert rules[0].name == "valid-rule"


def test_missing_required_field_is_skipped(monkeypatch, db_session):
    """A spec missing a required field is skipped; valid specs still provision."""
    incomplete = _spec("incomplete-rule")
    del incomplete["timeframeInSeconds"]
    _set_env(monkeypatch, _spec("valid-rule"), incomplete)

    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)

    rules = _provisioned_rules()
    assert len(rules) == 1
    assert rules[0].name == "valid-rule"


def test_reads_from_json_file_path(monkeypatch, tmp_path, db_session):
    """KEEP_CORRELATION_RULES pointing at a .json file is loaded from disk."""
    path = tmp_path / "correlation_rules.json"
    path.write_text(json.dumps([_spec("from-file-rule")]))
    monkeypatch.setenv(ENV_VAR, str(path))

    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)

    rules = _provisioned_rules()
    assert len(rules) == 1
    assert rules[0].name == "from-file-rule"


def test_noop_when_env_unset_and_no_provisioned_rules(monkeypatch, db_session):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert len(_all_rules()) == 0

    provision_correlation_rules_from_env(SINGLE_TENANT_UUID)

    assert len(_all_rules()) == 0
