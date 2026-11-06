"""Workflow secret names are trimmed on write, and the delete route finds untrimmed legacy names."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from keep.api.routes import workflows


class InMemorySecretManager:
    def __init__(self, stored=None):
        self.stored = dict(stored or {})

    def read_secret(self, secret_name, is_json=False):
        value = self.stored[secret_name]
        return json.loads(value) if is_json else value

    def write_secret(self, secret_name, secret_value):
        self.stored[secret_name] = secret_value


SECRET_KEY = "tenant_wf_secrets"
ENTITY = SimpleNamespace(tenant_id="tenant")


@pytest.fixture
def secret_manager(monkeypatch):
    manager = InMemorySecretManager()
    monkeypatch.setattr(workflows, "get_workflow_by_id_db", lambda **_: MagicMock())
    monkeypatch.setattr(workflows, "ContextManager", MagicMock())
    monkeypatch.setattr(
        workflows.SecretManagerFactory, "get_secret_manager", lambda _: manager
    )
    return manager


def _stored(manager):
    return json.loads(manager.stored[SECRET_KEY])


def test_write_trims_secret_names(secret_manager):
    workflows.write_workflow_secret("wf", {"API_KEY ": "a", " TOKEN": "b"}, ENTITY)

    assert _stored(secret_manager) == {"API_KEY": "a", "TOKEN": "b"}


def test_write_updates_the_trimmed_name_instead_of_adding_a_second_secret(
    secret_manager,
):
    workflows.write_workflow_secret("wf", {"API_KEY": "old"}, ENTITY)
    workflows.write_workflow_secret("wf", {"API_KEY ": "new"}, ENTITY)

    assert _stored(secret_manager) == {"API_KEY": "new"}


def test_write_rejects_a_blank_secret_name(secret_manager):
    with pytest.raises(HTTPException) as error:
        workflows.write_workflow_secret("wf", {"  ": "a"}, ENTITY)

    assert error.value.status_code == 400
    assert SECRET_KEY not in secret_manager.stored


def test_delete_removes_a_secret_saved_with_trailing_whitespace(secret_manager):
    # Saved by a version that kept the whitespace; clients strip it from the delete URL.
    secret_manager.stored[SECRET_KEY] = json.dumps({"API_KEY ": "a", "OTHER": "b"})

    workflows.delete_workflow_secret("wf", "API_KEY", ENTITY)

    assert _stored(secret_manager) == {"OTHER": "b"}


def test_delete_unknown_secret_is_not_found(secret_manager):
    secret_manager.stored[SECRET_KEY] = json.dumps({"OTHER": "b"})

    with pytest.raises(HTTPException) as error:
        workflows.delete_workflow_secret("wf", "API_KEY", ENTITY)

    assert error.value.status_code == 404
