import json
import socket
import threading
import time
import pytest
from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider
from keep.api.models.alert import AlertSeverity


def make_provider(
    listen_address="127.0.0.1",
    port=10162,
    community="public",
    severity_mapping=None,
):
    context_manager = ContextManager(
        tenant_id="test-tenant",
        workflow_id="test-workflow",
    )

    provider_config = ProviderConfig(
        authentication={
            "listen_address": listen_address,
            "port": port,
            "community": community,
            **({"severity_mapping": severity_mapping} if severity_mapping else {}),
        }
    )

    provider = SnmpProvider(
        context_manager=context_manager,
        provider_id="snmp-test",
        config=provider_config,
    )

    provider.validate_config()
    return provider


def test_default_config_values():
    provider = make_provider()
    assert provider.authentication_config.listen_address == "127.0.0.1"
    assert provider.authentication_config.port == 10162
    assert provider.authentication_config.community == "public"


def test_invalid_severity_mapping_json():
    provider = make_provider(severity_mapping="invalid{")
    assert provider._severity_mapping == {}


def test_status_running_and_stopped():
    provider = make_provider()
    assert provider.status()["status"] == "stopped"
    provider.running = True
    assert provider.status()["status"] == "running"


def test_validate_scopes_success():
    provider = make_provider(port=19162)
    result = provider.validate_scopes()
    assert result["receive_traps"] is True


def test_validate_scopes_port_in_use():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 19163))

    try:
        provider = make_provider(port=19163)
        result = provider.validate_scopes()
        assert result["receive_traps"] is not True
    finally:
        sock.close()


def test_determine_severity_default():
    provider = make_provider()
    sev = provider._determine_severity(["1.2.3"], {})
    assert sev == AlertSeverity.WARNING


def test_determine_severity_oid_match():
    mapping = json.dumps({"1.3.6": "CRITICAL"})
    provider = make_provider(severity_mapping=mapping)
    sev = provider._determine_severity(["1.3.6.1"], {})
    assert sev == AlertSeverity.CRITICAL


def test_determine_severity_value_match():
    mapping = json.dumps({"linkDown": "INFO"})
    provider = make_provider(severity_mapping=mapping)
    sev = provider._determine_severity([], {"oid": "linkDown"})
    assert sev == AlertSeverity.INFO


def make_var_binds(pairs):
    result = []
    for oid_str, val_str in pairs:
        oid = MagicMock()
        oid.__str__ = lambda self, s=oid_str: s

        val = MagicMock()
        val.prettyPrint = lambda v=val_str: val_str
        val.__class__.__name__ = "OctetString"

        result.append((oid, val))
    return result


def test_handle_trap_pushes_alert():
    provider = make_provider()
    provider._push_alert = MagicMock()

    var_binds = make_var_binds([
        ("1.3.6.1.2.1.1.3.0", "123")
    ])

    provider._handle_trap(None, None, None, None, var_binds, None)
    provider._push_alert.assert_called_once()


def test_handle_trap_empty_var_binds():
    provider = make_provider()
    provider._push_alert = MagicMock()

    provider._handle_trap(None, None, None, None, [], None)
    provider._push_alert.assert_not_called()


def test_handle_trap_severity_mapping():
    mapping = json.dumps({"1.3.6": "CRITICAL"})
    provider = make_provider(severity_mapping=mapping)
    provider._push_alert = MagicMock()

    var_binds = make_var_binds([
        ("1.3.6.1", "val")
    ])

    provider._handle_trap(None, None, None, None, var_binds, None)

    alert = provider._push_alert.call_args[0][0]
    assert alert["severity"] == "critical"


def test_handle_trap_default_title():
    provider = make_provider()
    provider._push_alert = MagicMock()

    var_binds = make_var_binds([("1.2.3", "val")])
    provider._handle_trap(None, None, None, None, var_binds, None)

    alert = provider._push_alert.call_args[0][0]
    assert alert["title"] == "SNMP Trap Received"


def test_handle_trap_with_trap_oid_title():
    provider = make_provider()
    provider._push_alert = MagicMock()

    var_binds = make_var_binds([
        ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")
    ])

    provider._handle_trap(None, None, None, None, var_binds, None)

    alert = provider._push_alert.call_args[0][0]
    assert "1.3.6.1.6.3.1.1.5.3" in alert["title"]


def test_handle_trap_raw_data_json():
    provider = make_provider()
    provider._push_alert = MagicMock()

    var_binds = make_var_binds([("1.2.3", "value")])
    provider._handle_trap(None, None, None, None, var_binds, None)

    alert = provider._push_alert.call_args[0][0]
    parsed = json.loads(alert["raw_data"])
    assert parsed["1.2.3"] == "value"


def test_snmpv3_valid_config():
    provider = make_provider()
    provider.config.authentication.update({
        "username": "user1",
        "auth_protocol": "MD5",
        "auth_key": "authpass",
        "priv_protocol": "AES",
        "priv_key": "privpass",
    })

    provider.validate_config()
    assert provider.authentication_config.username == "user1"


def test_snmpv3_missing_auth_key():
    provider = make_provider()
    provider.config.authentication.update({
        "username": "user1",
        "auth_protocol": "MD5",
    })

    with pytest.raises(ValueError):
        provider.validate_config()


def test_snmpv3_auth_key_without_protocol():
    provider = make_provider()
    provider.config.authentication.update({
        "username": "user1",
        "auth_key": "pass",
    })

    with pytest.raises(ValueError):
        provider.validate_config()


def test_snmpv3_priv_without_auth():
    provider = make_provider()
    provider.config.authentication.update({
        "username": "user1",
        "priv_protocol": "AES",
        "priv_key": "privpass",
    })

    with pytest.raises(ValueError):
        provider.validate_config()


def test_snmpv3_invalid_auth_protocol():
    provider = make_provider()
    provider.config.authentication.update({
        "username": "user1",
        "auth_protocol": "INVALID",
    })

    with pytest.raises(ValueError):
        provider.validate_config()


def test_snmpv3_invalid_priv_protocol():
    provider = make_provider()
    provider.config.authentication.update({
        "username": "user1",
        "auth_protocol": "MD5",
        "auth_key": "pass",
        "priv_protocol": "INVALID",
    })

    with pytest.raises(ValueError):
        provider.validate_config()


@patch("keep.providers.snmp_provider.snmp_provider.config")
@patch("keep.providers.snmp_provider.snmp_provider.engine")
@patch("keep.providers.snmp_provider.snmp_provider.ntfrcv")
@patch("keep.providers.snmp_provider.snmp_provider.udp")
def test_snmpv3_user_registration(mock_udp, mock_ntfrcv, mock_engine, mock_config):
    mock_snmp_engine = MagicMock()
    mock_engine.SnmpEngine.return_value = mock_snmp_engine

    mock_snmp_engine.transportDispatcher.runDispatcher = MagicMock(side_effect=Exception)

    provider = make_provider(port=19170)
    provider.config.authentication.update({
        "username": "user1",
        "auth_protocol": "MD5",
        "auth_key": "authpass",
        "priv_protocol": "AES",
        "priv_key": "privpass",
    })

    provider.validate_config()

    provider._start_trap_receiver()

    assert mock_config.add_v3_user.called
    assert mock_config.addVacmUser.called

def test_snmpv3_auth_no_priv():
    provider = make_provider()
    provider.config.authentication.update({
        "username": "user1",
        "auth_protocol": "SHA",
        "auth_key": "authpass",
    })

    provider.validate_config()
    assert provider.authentication_config.priv_protocol is None


def test_snmpv3_no_auth_no_priv():
    provider = make_provider()
    provider.config.authentication.update({
        "username": "user1",
    })

    provider.validate_config()
    assert provider.authentication_config.auth_protocol is None


@patch("keep.providers.snmp_provider.snmp_provider.engine")
def test_start_trap_receiver_failure(mock_engine):
    mock_engine.SnmpEngine.side_effect = Exception

    provider = make_provider()
    provider.running = True
    provider._start_trap_receiver()

    assert provider.running is False


def test_start_consume_twice():
    provider = make_provider()
    provider.running = True

    with patch.object(threading, "Thread") as mock_thread:
        provider.start_consume()
        mock_thread.assert_not_called()


def test_dispose_cleans_up():
    provider = make_provider()
    provider.running = True

    dispatcher = MagicMock()
    provider.snmp_engine = MagicMock()
    provider.snmp_engine.transportDispatcher = dispatcher

    provider.dispose()

    dispatcher.jobFinished.assert_called_once_with(1)
    dispatcher.closeDispatcher.assert_called_once()
    assert provider.running is False


def test_get_logs_running():
    provider = make_provider()
    provider.running = True

    logs = provider.get_logs()
    assert any("running" in log["message"].lower() for log in logs)


def test_get_logs_stopped():
    provider = make_provider()
    logs = provider.get_logs()
    assert any("Stopped" in log["message"] for log in logs)


def test_debug_info_masks_community():
    provider = make_provider(community="secret")
    info = provider.debug_info()

    assert info["configuration"]["community"] == "***"
    assert "secret" not in str(info)

def test_query_returns_none():
    provider = make_provider()
    assert provider._query() is None


def test_notify_returns_none():
    provider = make_provider()
    assert provider._notify() is None

@patch("keep.providers.snmp_provider.snmp_provider.config")
@patch("keep.providers.snmp_provider.snmp_provider.engine")
@patch("keep.providers.snmp_provider.snmp_provider.ntfrcv")
@patch("keep.providers.snmp_provider.snmp_provider.udp")
def test_snmp_v2_community_registration(mock_udp, mock_ntfrcv, mock_engine, mock_config):
    mock_snmp_engine = MagicMock()
    mock_engine.SnmpEngine.return_value = mock_snmp_engine

    mock_snmp_engine.transportDispatcher.runDispatcher = MagicMock(side_effect=Exception)

    provider = make_provider()
    provider.validate_config()

    provider._start_trap_receiver()

    mock_config.addV1System.assert_called_once()


@patch("keep.providers.snmp_provider.snmp_provider.config")
@patch("keep.providers.snmp_provider.snmp_provider.engine")
@patch("keep.providers.snmp_provider.snmp_provider.ntfrcv")
@patch("keep.providers.snmp_provider.snmp_provider.udp")
def test_snmp_transport_and_notification_registration(mock_udp, mock_ntfrcv, mock_engine, mock_config):
    mock_snmp_engine = MagicMock()
    mock_engine.SnmpEngine.return_value = mock_snmp_engine

    mock_snmp_engine.transportDispatcher.runDispatcher = MagicMock(side_effect=Exception)

    provider = make_provider()
    provider.validate_config()

    provider._start_trap_receiver()

    assert mock_config.addTransport.called

    assert mock_ntfrcv.NotificationReceiver.called


def test_severity_keyword_detection():
    provider = make_provider()

    sev = provider._determine_severity(
        [],
        {"msg": "critical failure detected"}
    )

    assert sev == AlertSeverity.CRITICAL


def test_default_oid_severity_map():
    provider = make_provider()

    sev = provider._determine_severity(
        ["1.3.6.1.6.3.1.1.5.3"],  # linkDown
        {}
    )

    assert sev == AlertSeverity.HIGH


def test_value_parsing_fallback():
    provider = make_provider()
    provider._push_alert = MagicMock()

    class BadValue:
        def prettyPrint(self):
            raise Exception("fail")

        def __str__(self):
            return "fallback_value"

    oid = MagicMock()
    oid.__str__ = lambda self: "1.2.3"

    var_binds = [(oid, BadValue())]

    provider._handle_trap(None, None, None, None, var_binds, None)

    alert = provider._push_alert.call_args[0][0]

    parsed = json.loads(alert["raw_data"])
    assert parsed["1.2.3"] == "fallback_value"