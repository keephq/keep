"""CloudWatch capability validation must not change customer resources."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from keep.providers.cloudwatch_provider.cloudwatch_provider import CloudwatchProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_service import ProvidersService


@pytest.fixture
def aws_clients():
    clients = {name: Mock() for name in ("sts", "iam", "cloudwatch", "logs", "sns")}
    clients["sts"].get_caller_identity.return_value = {
        "Arn": "arn:aws:iam::123456789012:user/keep-test",
        "Account": "123456789012",
    }
    clients["iam"].simulate_principal_policy.side_effect = PermissionError("denied")
    clients["cloudwatch"].describe_alarms.return_value = {
        "MetricAlarms": [{"AlarmName": "existing-alarm", "Threshold": 5}]
    }
    clients["logs"].describe_queries.return_value = {"queries": []}
    with patch(
        "keep.providers.cloudwatch_provider.cloudwatch_provider.boto3.client",
        side_effect=lambda service, **kwargs: clients[service],
    ) as create_client:
        yield clients, create_client


def provider(**authentication):
    return CloudwatchProvider(
        context_manager=SimpleNamespace(tenant_id="scope-validation-test"),
        provider_id="cloudwatch-test",
        config=ProviderConfig(authentication={"region": "us-east-1", **authentication}),
    )


def test_scope_validation_never_writes_alarms_or_starts_queries(aws_clients):
    clients, _ = aws_clients
    scopes = ProvidersService.validate_scopes(provider())
    assert scopes["cloudwatch:DescribeAlarms"] is True
    clients["cloudwatch"].put_metric_alarm.assert_not_called()
    clients["logs"].start_query.assert_not_called()
    assert isinstance(scopes["cloudwatch:PutMetricAlarm"], str)
    assert isinstance(scopes["logs:StartQuery"], str)


def test_simulation_denial_is_not_overridden_by_probes(aws_clients):
    clients, create_client = aws_clients
    clients["iam"].simulate_principal_policy.side_effect = None
    clients["iam"].simulate_principal_policy.return_value = {
        "EvaluationResults": [
            {
                "EvalActionName": scope.name,
                "EvalDecision": "allowed" if scope.mandatory else "implicitDeny",
            }
            for scope in CloudwatchProvider.PROVIDER_SCOPES
        ]
    }
    scopes = ProvidersService.validate_scopes(provider())
    assert scopes["cloudwatch:PutMetricAlarm"] is False
    assert scopes["logs:StartQuery"] is False
    assert {call.args[0] for call in create_client.call_args_list} == {"sts", "iam"}


def test_get_query_results_uses_existing_query_without_starting_one(aws_clients):
    clients, _ = aws_clients
    clients["logs"].describe_queries.return_value = {
        "queries": [{"queryId": "existing-query"}]
    }
    scopes = ProvidersService.validate_scopes(provider())
    assert scopes["logs:GetQueryResults"] is True
    assert isinstance(scopes["logs:StartQuery"], str)
    clients["logs"].get_query_results.assert_called_once_with(queryId="existing-query")
    clients["logs"].start_query.assert_not_called()


def test_receiver_only_validation_and_disposal_do_not_create_aws_clients(aws_clients):
    _, create_client = aws_clients
    receiver = provider(webhook_only=True)
    assert receiver.authentication_config.webhook_only is True
    assert ProvidersService.validate_scopes(receiver) == {}
    receiver.dispose()
    create_client.assert_not_called()
    # Receiver-only instances must not change the class-level API-mode contract.
    assert any(scope.mandatory for scope in provider().PROVIDER_SCOPES)


@pytest.mark.parametrize("operation", ["query", "setup"])
def test_receiver_only_rejects_aws_operations_before_creating_clients(
    aws_clients, operation
):
    _, create_client = aws_clients
    receiver = provider(webhook_only=True)
    with pytest.raises(ValueError, match="webhook_only"):
        if operation == "query":
            receiver._query(log_group="unused", query="fields @message")
        else:
            receiver.setup_webhook(
                "tenant", "https://keep.example/events", "unused-key"
            )
    create_client.assert_not_called()


def test_update_receiver_only_provider_keeps_identity_without_aws_calls(aws_clients):
    """Exercise the service path which always validates scopes on reprovision."""
    import datetime
    import json

    from sqlmodel import Session, create_engine

    from keep.api.models.db.provider import Provider

    _, create_client = aws_clients
    engine = create_engine("sqlite://")
    Provider.__table__.create(engine)
    with Session(engine) as session:
        existing = Provider(
            id="existing-provider-id",
            tenant_id="scope-validation-test",
            name="existing-provider",
            type="cloudwatch",
            installed_by="original-operator",
            installation_time=datetime.datetime(2026, 1, 1),
            configuration_key="existing-configuration-key",
            validatedScopes={},
            pulling_enabled=False,
            provider_metadata={},
        )
        session.add(existing)
        session.commit()
        secret_manager = Mock()
        with patch(
            "keep.providers.providers_service.SecretManagerFactory.get_secret_manager",
            return_value=secret_manager,
        ):
            result = ProvidersService.update_provider(
                tenant_id="scope-validation-test",
                provider_id="existing-provider-id",
                provider_info={
                    "region": "us-east-1",
                    "webhook_only": True,
                    "pulling_enabled": False,
                },
                updated_by="test-operator",
                session=session,
            )
        session.refresh(existing)
        assert existing.id == "existing-provider-id"
        assert existing.pulling_enabled is False
        assert existing.validatedScopes == result["validatedScopes"] == {}
        write = secret_manager.write_secret.call_args.kwargs
        assert write["secret_name"] == "existing-configuration-key"
        assert (
            json.loads(write["secret_value"])["authentication"]["webhook_only"] is True
        )
    create_client.assert_not_called()


def test_api_mode_preserves_explicit_credential_client_configuration(aws_clients):
    _, create_client = aws_clients
    instance = provider(
        access_key="synthetic-access-key",
        access_key_secret="synthetic-secret",
        session_token="synthetic-session-token",
    )
    ProvidersService.validate_scopes(instance)
    for call in create_client.call_args_list:
        assert call.kwargs == {
            "aws_access_key_id": "synthetic-access-key",
            "aws_secret_access_key": "synthetic-secret",
            "aws_session_token": "synthetic-session-token",
            "region_name": "us-east-1",
        }


def test_receiver_only_preserves_native_formatting_and_sns_confirmation(aws_clients):
    import json

    _, create_client = aws_clients
    receiver = provider(webhook_only=True)
    event = {
        "Type": "Notification",
        "Message": json.dumps(
            {
                "AlarmName": "example-alarm",
                "AlarmArn": "arn:aws:cloudwatch:us-east-1:123456789012:alarm:example-alarm",
                "NewStateValue": "OK",
                "StateChangeTime": "2026-01-01T00:00:00+00:00",
            }
        ),
    }
    alert = receiver._format_alert(event, receiver)
    assert alert.source == ["cloudwatch"]
    assert alert.status == "resolved"
    with patch(
        "keep.providers.cloudwatch_provider.cloudwatch_provider.requests.get"
    ) as confirm:
        assert (
            receiver._format_alert(
                {
                    "Type": "SubscriptionConfirmation",
                    "SubscribeURL": "https://sns.us-east-1.amazonaws.com/example-confirmation",
                },
                receiver,
            )
            is None
        )
    confirm.assert_called_once_with(
        "https://sns.us-east-1.amazonaws.com/example-confirmation"
    )
    create_client.assert_not_called()
