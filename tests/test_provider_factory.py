import inspect
from datetime import datetime
from typing import Optional, Union
from unittest.mock import patch

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.provider import Provider
from keep.providers.providers_factory import ProvidersFactory


@pytest.fixture
def isolated_provider_factory_caches(monkeypatch):
    monkeypatch.setattr(ProvidersFactory, "_loaded_providers_cache", None)
    monkeypatch.setattr(ProvidersFactory, "_loaded_deduplication_rules_cache", None)


class TestProviderFactoryMethodParam:
    def test_get_method_param_type_simple(self):
        param = inspect.Parameter(
            "test", inspect.Parameter.POSITIONAL_ONLY, annotation=str
        )
        assert ProvidersFactory._get_method_param_type(param) == "str"

    def test_get_method_param_type_union(self):
        param = inspect.Parameter(
            "test", inspect.Parameter.POSITIONAL_ONLY, annotation=Union[str, int]
        )
        assert ProvidersFactory._get_method_param_type(param) == "str"

    def test_get_method_param_type_union_with_pipe(self):
        param = inspect.Parameter(
            "test", inspect.Parameter.POSITIONAL_ONLY, annotation=int | str
        )
        assert ProvidersFactory._get_method_param_type(param) == "int"

    def test_get_method_param_type_optional(self):
        param = inspect.Parameter(
            "test", inspect.Parameter.POSITIONAL_ONLY, annotation=Optional[str]
        )
        assert ProvidersFactory._get_method_param_type(param) == "str"

    def test_get_method_param_type_optional_with_union(self):
        param = inspect.Parameter(
            "test", inspect.Parameter.POSITIONAL_ONLY, annotation=Union[None, int]
        )
        assert ProvidersFactory._get_method_param_type(param) == "int"

    def test_get_method_param_type_without_annotation(self):
        param = inspect.Parameter("test", inspect.Parameter.POSITIONAL_ONLY)
        assert ProvidersFactory._get_method_param_type(param) == "str"


def test_provider_factory_is_using_config_key_from_db(db_session):
    custom_configuration_key = "custom_secret_name"
    provider = Provider(
        id="test_provider_id",
        tenant_id=SINGLE_TENANT_UUID,
        name="test_provider",
        type="grafana",
        installed_by="test_user",
        installation_time=datetime.now(),
        configuration_key=custom_configuration_key,
        validatedScopes=True,
        pulling_enabled=False,
    )
    db_session.add(provider)
    db_session.commit()

    with patch('keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager') as mock_secret_manager:
        mock_secret_manager.return_value.read_secret.return_value = {"key": "value"}
        ProvidersFactory.get_installed_providers(tenant_id=SINGLE_TENANT_UUID)
        assert mock_secret_manager.return_value.read_secret.call_args[1]['secret_name'] == custom_configuration_key


def test_zabbix_default_fingerprint_fields_and_rule(isolated_provider_factory_caches):
    assert ProvidersFactory._loaded_providers_cache is None
    assert ProvidersFactory._loaded_deduplication_rules_cache is None

    providers = ProvidersFactory.get_all_providers(ignore_cache_file=True)
    zabbix_provider = next(
        provider for provider in providers if provider.type == "zabbix"
    )

    assert zabbix_provider.default_fingerprint_fields == ["id"]

    default_rules = ProvidersFactory.get_default_deduplication_rules()
    zabbix_rule = next(rule for rule in default_rules if rule.provider_type == "zabbix")

    assert zabbix_rule.fingerprint_fields == ["id"]
