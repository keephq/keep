"""Tests for TLS/mTLS options on the Centreon provider (issue #3340).

The provider talks to an on-prem Centreon over HTTPS, which commonly uses a
self-signed or internal-CA certificate. These tests cover the verify switch and
the CA / client-certificate wiring through to the underlying requests call.
"""

import os
from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.centreon_provider.centreon_provider import CentreonProvider
from keep.providers.models.provider_config import ProviderConfig

REQUESTS_GET = "keep.providers.centreon_provider.centreon_provider.requests.get"

CA_PEM = "-----BEGIN CERTIFICATE-----\nca-content\n-----END CERTIFICATE-----\n"
CLIENT_PEM = "-----BEGIN CERTIFICATE-----\nclient-content\n-----END CERTIFICATE-----\n"
KEY_PEM = "-----BEGIN PRIVATE KEY-----\nkey-content\n-----END PRIVATE KEY-----\n"


def _make_provider(**auth):
    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "host_url": "https://centreon.internal",
            "api_token": "token",
            **auth,
        },
        name="test-centreon",
    )
    return CentreonProvider(context_manager, "centreon", config)


def _capturing_get():
    """A requests.get replacement that records the TLS kwargs and reads the
    temporary cert files while they still exist (they are removed after the call)."""
    captured = {}

    def fake_get(url, headers=None, **kwargs):
        captured["verify"] = kwargs.get("verify", "UNSET")
        captured["cert"] = kwargs.get("cert")
        verify = kwargs.get("verify")
        if isinstance(verify, str):
            captured["verify_path"] = verify
            with open(verify) as fh:
                captured["ca_content"] = fh.read()
        cert = kwargs.get("cert")
        if cert:
            captured["cert_paths"] = cert
            with open(cert[0]) as fh:
                captured["client_cert_content"] = fh.read()
            with open(cert[1]) as fh:
                captured["client_key_content"] = fh.read()
        response = MagicMock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = []
        return response

    return fake_get, captured


def test_verify_true_by_default():
    provider = _make_provider()
    fake_get, captured = _capturing_get()
    with patch(REQUESTS_GET, side_effect=fake_get):
        provider.validate_scopes()
    # requests default verify is True, so no explicit override is passed
    assert captured["verify"] == "UNSET"
    assert captured["cert"] is None


def test_verify_false_skips_tls_verification():
    provider = _make_provider(verify=False)
    fake_get, captured = _capturing_get()
    with patch(REQUESTS_GET, side_effect=fake_get):
        provider.validate_scopes()
    assert captured["verify"] is False


def test_ca_certificate_passed_as_file_path():
    provider = _make_provider(ca_certificate=CA_PEM)
    fake_get, captured = _capturing_get()
    with patch(REQUESTS_GET, side_effect=fake_get):
        provider.validate_scopes()
    assert isinstance(captured["verify"], str)
    assert captured["ca_content"] == CA_PEM


def test_verify_false_takes_precedence_over_ca_certificate():
    provider = _make_provider(verify=False, ca_certificate=CA_PEM)
    fake_get, captured = _capturing_get()
    with patch(REQUESTS_GET, side_effect=fake_get):
        provider.validate_scopes()
    assert captured["verify"] is False


def test_client_certificate_enables_mutual_tls():
    provider = _make_provider(client_certificate=CLIENT_PEM, client_key=KEY_PEM)
    fake_get, captured = _capturing_get()
    with patch(REQUESTS_GET, side_effect=fake_get):
        provider.validate_scopes()
    assert captured["cert"] is not None
    assert captured["client_cert_content"] == CLIENT_PEM
    assert captured["client_key_content"] == KEY_PEM


def test_client_certificate_without_key_is_ignored():
    provider = _make_provider(client_certificate=CLIENT_PEM)
    fake_get, captured = _capturing_get()
    with patch(REQUESTS_GET, side_effect=fake_get):
        provider.validate_scopes()
    assert captured["cert"] is None


def test_temp_cert_files_are_cleaned_up():
    provider = _make_provider(
        ca_certificate=CA_PEM, client_certificate=CLIENT_PEM, client_key=KEY_PEM
    )
    fake_get, captured = _capturing_get()
    with patch(REQUESTS_GET, side_effect=fake_get):
        provider.validate_scopes()
    # paths existed during the call but must be removed afterwards
    assert not os.path.exists(captured["verify_path"])
    for path in captured["cert_paths"]:
        assert not os.path.exists(path)
