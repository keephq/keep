"""Tests for keep.api.bl.mapping_rules_provisioning.provision_mapping_rules_from_env.

Mirrors the structure of tests/test_workflowstore.py — uses real in-memory SQLite
sessions (via the `db_session` fixture from tests/conftest.py) rather than
patching DB helpers, because the provisioning module operates on SQLModel
sessions directly (same pattern as the existing MappingRule REST routes).
"""

import os

import pytest
from sqlmodel import Session, select

import keep.api.core.db as db
from keep.api.bl.mapping_rules_provisioning import provision_mapping_rules_from_env
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.mapping import MappingRule

FIXTURE_DIR_ONE = "./tests/provision/mapping_rules_1"
FIXTURE_DIR_TWO = "./tests/provision/mapping_rules_2"
FIXTURE_DIR_INVALID = "./tests/provision/mapping_rules_invalid"
FIXTURE_DIR_EMPTY = "./tests/provision/mapping_rules_empty"
FIXTURE_DIR_MISSING = "./tests/provision/mapping_rules_does_not_exist"
FIXTURE_DIR_SAME_NAME = "./tests/provision/mapping_rules_same_name"
FIXTURE_DIR_WITH_NOISE = "./tests/provision/mapping_rules_with_noise"


def _all_mapping_rules(tenant_id=SINGLE_TENANT_UUID) -> list[MappingRule]:
    with Session(db.engine) as session:
        return session.exec(
            select(MappingRule).where(MappingRule.tenant_id == tenant_id)
        ).all()


def _provisioned_mapping_rules(tenant_id=SINGLE_TENANT_UUID) -> list[MappingRule]:
    with Session(db.engine) as session:
        return session.exec(
            select(MappingRule).where(
                MappingRule.tenant_id == tenant_id,
                MappingRule.is_provisioned == True,  # noqa: E712
            )
        ).all()


def test_creates_new_rule(monkeypatch, db_session):
    """Empty DB + manifest dir → rule is created and marked provisioned."""
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_ONE)

    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    rules = _provisioned_mapping_rules()
    assert len(rules) == 1
    rule = rules[0]
    assert rule.name == "example-prometheus-mapping"
    assert rule.is_provisioned is True
    assert rule.provisioned_file.endswith("prometheus-alerts.yaml")
    assert rule.type == "csv"
    assert rule.matchers == [["namespace"]]
    assert len(rule.rows) == 2
    assert rule.rows[0]["namespace"] == "monitoring"
    assert rule.created_by == "system"


def test_provisions_multiple_rules(monkeypatch, db_session):
    """Two manifests in dir → both rules provisioned."""
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_TWO)

    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    rules = _provisioned_mapping_rules()
    names = sorted(r.name for r in rules)
    assert names == ["example-cloudwatch-mapping", "example-prometheus-mapping"]


def test_is_idempotent(monkeypatch, db_session):
    """Running provisioning twice does not create duplicates."""
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_TWO)

    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)
    first_ids = sorted(r.id for r in _provisioned_mapping_rules())
    assert len(first_ids) == 2

    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)
    second_ids = sorted(r.id for r in _provisioned_mapping_rules())

    assert first_ids == second_ids


def test_adopts_existing_ui_rule_with_matching_name(monkeypatch, db_session):
    """A UI-created rule (is_provisioned=False) with the same name as a manifest
    gets adopted: is_provisioned flips to True, content overwritten, DB id
    preserved, AND fields not in the manifest schema (disabled / override /
    condition) reset to model defaults — the manifest is the source of truth.
    """
    with Session(db.engine) as session:
        ui_rule = MappingRule(
            tenant_id=SINGLE_TENANT_UUID,
            name="example-prometheus-mapping",
            description="created via UI",
            priority=99,
            matchers=[["something-different"]],
            type="csv",
            rows=[{"x": "y"}],
            created_by="ui-user@example.com",
            is_provisioned=False,
            # Fields NOT in MappingRuleDtoIn — should be reset on adoption
            disabled=True,
            override=False,
            condition="some.ui.set.condition",
        )
        session.add(ui_rule)
        session.commit()
        ui_rule_id = ui_rule.id

    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_ONE)
    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    rules = _all_mapping_rules()
    assert len(rules) == 1  # adopted, not duplicated
    adopted = rules[0]
    assert adopted.id == ui_rule_id  # DB id preserved
    assert adopted.is_provisioned is True
    assert adopted.matchers == [["namespace"]]  # overwritten from manifest
    assert adopted.priority == 0  # overwritten from manifest
    assert adopted.updated_by == "system"
    # Fields not in MappingRuleDtoIn reset to model defaults
    assert adopted.disabled is False
    assert adopted.override is True
    assert adopted.condition is None


def test_same_name_manifests_do_not_create_duplicate(monkeypatch, db_session):
    """Two manifests in the same directory with the same `name` field result in
    exactly one DB row (the second manifest acts as an in-batch update). Guards
    against duplicate creation when SQLAlchemy autoflush is disabled.
    """
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_SAME_NAME)

    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    rules = _all_mapping_rules()
    assert len(rules) == 1, (
        f"expected 1 rule (duplicate names collapsed), got {len(rules)}: "
        f"{[(r.name, r.priority) for r in rules]}"
    )
    # b-second.yaml sorts after a-first.yaml; final state is the second manifest's
    assert rules[0].name == "duplicate-name-mapping"
    assert rules[0].priority == 99
    assert rules[0].rows[0]["namespace"] == "default"


def test_non_yaml_files_in_directory_are_ignored(monkeypatch, db_session):
    """Non-`.yaml`/`.yml` files (e.g. README, .gitkeep, .txt) in the directory
    are silently skipped — they don't raise, don't block, don't get parsed.
    """
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_WITH_NOISE)

    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    rules = _provisioned_mapping_rules()
    # Only the one .yaml file in the dir produces a rule; notes.txt is skipped
    assert len(rules) == 1
    assert rules[0].name == "example-prometheus-mapping"


def test_updates_existing_provisioned_rule(monkeypatch, db_session):
    """A previously-provisioned rule gets its content refreshed from the manifest."""
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_ONE)
    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    first = _provisioned_mapping_rules()[0]
    original_id = first.id

    # Pretend the DB content drifted (simulating someone editing via UI directly)
    with Session(db.engine) as session:
        rule = session.exec(
            select(MappingRule).where(MappingRule.id == original_id)
        ).first()
        rule.priority = 42
        session.add(rule)
        session.commit()

    # Re-run provisioning — should reset priority back to manifest value (0)
    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    refreshed = _provisioned_mapping_rules()
    assert len(refreshed) == 1
    assert refreshed[0].id == original_id
    assert refreshed[0].priority == 0


def test_deprovisions_when_manifest_file_disappears(monkeypatch, db_session):
    """A rule provisioned from a file that's no longer in the directory is deleted."""
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_TWO)
    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)
    assert len(_provisioned_mapping_rules()) == 2

    # Swap to a dir containing only one of the two manifests (by name)
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_ONE)
    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    remaining = _provisioned_mapping_rules()
    assert len(remaining) == 1
    assert remaining[0].name == "example-prometheus-mapping"


def test_deprovisions_all_when_env_unset(monkeypatch, db_session):
    """Unsetting KEEP_MAPPINGS_DIRECTORY deletes all currently-provisioned rules."""
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_TWO)
    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)
    assert len(_provisioned_mapping_rules()) == 2

    monkeypatch.delenv("KEEP_MAPPINGS_DIRECTORY")
    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    assert len(_provisioned_mapping_rules()) == 0


def test_leaves_unrelated_ui_rules_untouched(monkeypatch, db_session):
    """A UI rule whose name does NOT match any manifest is left alone."""
    with Session(db.engine) as session:
        ui_rule = MappingRule(
            tenant_id=SINGLE_TENANT_UUID,
            name="some-ui-only-rule-not-in-manifests",
            priority=5,
            matchers=[["unrelated"]],
            type="csv",
            rows=[{"unrelated": "yes"}],
            created_by="ui-user@example.com",
            is_provisioned=False,
        )
        session.add(ui_rule)
        session.commit()
        ui_rule_id = ui_rule.id

    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_ONE)
    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    # UI rule still exists, still not provisioned
    with Session(db.engine) as session:
        rule = session.exec(
            select(MappingRule).where(MappingRule.id == ui_rule_id)
        ).first()
        assert rule is not None
        assert rule.is_provisioned is False
        assert rule.priority == 5

    all_rules = _all_mapping_rules()
    assert len(all_rules) == 2  # the UI rule + the provisioned one


def test_raises_when_directory_missing(monkeypatch, db_session):
    """Pointing KEEP_MAPPINGS_DIRECTORY at a non-existent path raises FileNotFoundError."""
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_MISSING)
    with pytest.raises(FileNotFoundError):
        provision_mapping_rules_from_env(SINGLE_TENANT_UUID)


def test_invalid_manifest_does_not_break_valid_one(monkeypatch, db_session):
    """A malformed manifest is logged and skipped; valid manifests in the same dir still provision."""
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_INVALID)

    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    rules = _provisioned_mapping_rules()
    assert len(rules) == 1
    assert rules[0].name == "valid-mapping"


def test_noop_when_env_unset_and_no_provisioned_rules(monkeypatch, db_session):
    """Calling with no env and no provisioned rules in DB is a clean no-op."""
    monkeypatch.delenv("KEEP_MAPPINGS_DIRECTORY", raising=False)
    # No rules to start with
    assert len(_all_mapping_rules()) == 0

    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)

    assert len(_all_mapping_rules()) == 0


def test_empty_directory_deprovisions_existing(monkeypatch, db_session):
    """An empty dir is treated like 'no manifests' — existing provisioned rules deleted."""
    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_ONE)
    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)
    assert len(_provisioned_mapping_rules()) == 1

    monkeypatch.setenv("KEEP_MAPPINGS_DIRECTORY", FIXTURE_DIR_EMPTY)
    provision_mapping_rules_from_env(SINGLE_TENANT_UUID)
    assert len(_provisioned_mapping_rules()) == 0
