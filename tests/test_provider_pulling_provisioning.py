"""Provisioning must honor the top-level polling switch on install and update."""

import json
from unittest.mock import Mock

import pytest
from sqlmodel import Session, create_engine, select

from keep.api.models.db.provider import Provider
from keep.providers.providers_service import ProvidersService


@pytest.mark.parametrize("source", ["env", "directory"])
@pytest.mark.parametrize(
    "pulling,expected",
    [(False, False), ("false", False), (True, True), ("true", True), (None, True)],
)
def test_provisioning_honors_pulling_on_install_and_reprovision(
    source, pulling, expected, monkeypatch, tmp_path
):
    import keep.api.core.db as db
    import keep.providers.providers_service as service

    engine = create_engine("sqlite://")
    Provider.__table__.create(engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(service, "engine", engine)
    monkeypatch.setattr(
        service.SecretManagerFactory, "get_secret_manager", lambda _: Mock()
    )
    monkeypatch.delenv("KEEP_PROVIDERS", raising=False)
    monkeypatch.delenv("KEEP_PROVIDERS_DIRECTORY", raising=False)
    definition = {
        "type": "cloudwatch",
        "authentication": {"region": "us-east-1", "webhook_only": True},
        "install_webhook": False,
    }
    if pulling is not None:
        definition["pulling_enabled"] = pulling
    if source == "env":
        monkeypatch.setenv("KEEP_PROVIDERS", json.dumps({"receiver": definition}))
    else:
        definition["name"] = "receiver"
        (tmp_path / "provider.yaml").write_text(json.dumps(definition))
        monkeypatch.setenv("KEEP_PROVIDERS_DIRECTORY", str(tmp_path))
    with monkeypatch.context() as scoped:
        create_client = Mock(side_effect=AssertionError("Unexpected AWS API access"))
        scoped.setattr(
            "keep.providers.cloudwatch_provider.cloudwatch_provider.boto3.client",
            create_client,
        )
        ProvidersService.provision_providers("provisioning-test")
        with Session(engine) as session:
            installed = session.exec(select(Provider)).one()
            first_id = installed.id
            assert installed.pulling_enabled is expected
            installed.pulling_enabled = not expected
            session.commit()
        ProvidersService.provision_providers("provisioning-test")
        with Session(engine) as session:
            updated = session.exec(select(Provider)).one()
            assert updated.id == first_id
            assert updated.pulling_enabled is expected
            assert updated.validatedScopes == {}
        create_client.assert_not_called()


@pytest.mark.parametrize("value", ["not-a-boolean", "", 0, 1, None])
def test_install_rejects_invalid_pulling_before_accessing_resources(value, monkeypatch):
    import keep.providers.providers_service as service

    create_provider = Mock(side_effect=AssertionError("Unexpected provider creation"))
    monkeypatch.setattr(service.ProvidersFactory, "get_provider", create_provider)
    with pytest.raises(ValueError, match="pulling_enabled"):
        ProvidersService.install_provider(
            tenant_id="provisioning-test",
            installed_by="operator",
            provider_id="cloudwatch",
            provider_name="receiver",
            provider_type="cloudwatch",
            provider_config={"region": "us-east-1", "webhook_only": True},
            pulling_enabled=value,
        )
    create_provider.assert_not_called()
