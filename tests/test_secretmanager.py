import pytest

from keep.secretmanager.vaultsecretmanager import VaultSecretManager


class MockVault:
    def __init__(self, *args, **kwargs):
        self.data = {"data": {"data": {"value": {"a": "b"}}}}

    @property
    def secrets(self):
        return self

    @property
    def kv(self):
        return self

    @property
    def v2(self):
        return self

    def create_or_update_secret(self, *args, **kwargs):
        pass

    def read_secret_version(self, *args, **kwargs):
        return self.data

    def delete_metadata_and_all_versions(self, *args, **kwargs):
        pass


@pytest.fixture(scope="function")
def vault_secret_manager(monkeypatch, context_manager):
    monkeypatch.setenv("HASHICORP_VAULT_ADDR", "mock_addr")
    monkeypatch.setenv("HASHICORP_VAULT_TOKEN", "mock_token")
    monkeypatch.setattr("hvac.Client", MockVault)  # Replace hvac.Client with mock
    return VaultSecretManager(
        context_manager=context_manager
    )  # Assuming None is a valid context manager in your case


def test_write_secret(vault_secret_manager):
    secret_name = "test_secret"
    secret_value = '{"key": "value"}'
    vault_secret_manager.write_secret(secret_name, secret_value)
    # You might want to assert logs or other side effects if necessary


def test_read_secret(vault_secret_manager):
    secret_name = "test_secret"
    expected_value = {"a": "b"}  # Adjust based on your mock's return value
    result = vault_secret_manager.read_secret(secret_name)
    assert result == expected_value


def test_delete_secret(vault_secret_manager):
    secret_name = "test_secret"
    vault_secret_manager.delete_secret(secret_name)
    # You might want to assert logs or other side effects if necessary
