import os
from unittest.mock import patch
import unittest

from keep.api.core.dependencies import get_pusher_client


class TestPusherDependencies(unittest.TestCase):
    """
    Unit tests for get_pusher_client handling of host, port, ssl,
    and internal/external overrides to fix client/server divergence (Issue #6856).
    """

    def test_get_pusher_client_disabled(self):
        with patch.dict(
            os.environ,
            {
                "PUSHER_DISABLED": "true",
                "PUSHER_APP_ID": "12345",
                "PUSHER_APP_KEY": "app-key",
                "PUSHER_APP_SECRET": "app-secret",
            },
            clear=True,
        ):
            client = get_pusher_client()
            assert client is None

    def test_get_pusher_client_missing_credentials(self):
        with patch.dict(
            os.environ,
            {
                "PUSHER_DISABLED": "false",
                "PUSHER_APP_ID": "12345",
                # missing key and secret
            },
            clear=True,
        ):
            client = get_pusher_client()
            assert client is None

    def test_get_pusher_client_relative_path_returns_none_safely(self):
        """
        When PUSHER_HOST is configured as a relative path (e.g. /websocket for client ingress)
        and no internal host is provided, backend should return None safely rather than
        crashing with InvalidURL.
        """
        with patch.dict(
            os.environ,
            {
                "PUSHER_DISABLED": "false",
                "PUSHER_APP_ID": "12345",
                "PUSHER_APP_KEY": "app-key",
                "PUSHER_APP_SECRET": "app-secret",
                "PUSHER_HOST": "/websocket",
            },
            clear=True,
        ):
            client = get_pusher_client()
            assert client is None

    def test_get_pusher_client_internal_override(self):
        """
        PUSHER_HOST_INTERNAL should override PUSHER_HOST (e.g. frontend uses /websocket,
        backend uses internal service name).
        """
        with patch.dict(
            os.environ,
            {
                "PUSHER_DISABLED": "false",
                "PUSHER_APP_ID": "12345",
                "PUSHER_APP_KEY": "app-key",
                "PUSHER_APP_SECRET": "app-secret",
                "PUSHER_HOST": "/websocket",
                "PUSHER_HOST_INTERNAL": "keep-websocket-server",
                "PUSHER_PORT": "6001",
            },
            clear=True,
        ):
            client = get_pusher_client()
            assert client is not None
            assert client._pusher_client.host == "keep-websocket-server"
            assert client._pusher_client.port == 6001

    def test_get_pusher_client_private_override(self):
        """
        PUSHER_HOST_PRIVATE should override PUSHER_HOST.
        """
        with patch.dict(
            os.environ,
            {
                "PUSHER_DISABLED": "false",
                "PUSHER_APP_ID": "12345",
                "PUSHER_APP_KEY": "app-key",
                "PUSHER_APP_SECRET": "app-secret",
                "PUSHER_HOST": "public-proxy.domain.com",
                "PUSHER_HOST_PRIVATE": "soketi-svc",
            },
            clear=True,
        ):
            client = get_pusher_client()
            assert client is not None
            assert client._pusher_client.host == "soketi-svc"

    def test_get_pusher_client_host_with_port(self):
        """
        Hostname specified with port (e.g. keep-websocket:6001) should parse cleanly
        without duplicating port in URL.
        """
        with patch.dict(
            os.environ,
            {
                "PUSHER_DISABLED": "false",
                "PUSHER_APP_ID": "12345",
                "PUSHER_APP_KEY": "app-key",
                "PUSHER_APP_SECRET": "app-secret",
                "PUSHER_HOST": "keep-websocket:6001",
            },
            clear=True,
        ):
            client = get_pusher_client()
            assert client is not None
            assert client._pusher_client.host == "keep-websocket"
            assert client._pusher_client.port == 6001

    def test_get_pusher_client_http_url(self):
        """
        Full HTTP URL should parse host, port, and default ssl to False.
        """
        with patch.dict(
            os.environ,
            {
                "PUSHER_DISABLED": "false",
                "PUSHER_APP_ID": "12345",
                "PUSHER_APP_KEY": "app-key",
                "PUSHER_APP_SECRET": "app-secret",
                "PUSHER_HOST": "http://keep-websocket:6001",
            },
            clear=True,
        ):
            client = get_pusher_client()
            assert client is not None
            assert client._pusher_client.host == "keep-websocket"
            assert client._pusher_client.port == 6001
            assert client._pusher_client.ssl is False

    def test_get_pusher_client_https_url(self):
        """
        Full HTTPS URL should parse host, port, and default ssl to True.
        """
        with patch.dict(
            os.environ,
            {
                "PUSHER_DISABLED": "false",
                "PUSHER_APP_ID": "12345",
                "PUSHER_APP_KEY": "app-key",
                "PUSHER_APP_SECRET": "app-secret",
                "PUSHER_HOST": "https://soketi.domain.com:8443/ws",
            },
            clear=True,
        ):
            client = get_pusher_client()
            assert client is not None
            assert client._pusher_client.host == "soketi.domain.com"
            assert client._pusher_client.port == 8443
            assert client._pusher_client.ssl is True

    def test_get_pusher_client_host_with_path_segment(self):
        """
        Host with path segment (e.g. soketi-svc/websocket) should extract hostname cleanly.
        """
        with patch.dict(
            os.environ,
            {
                "PUSHER_DISABLED": "false",
                "PUSHER_APP_ID": "12345",
                "PUSHER_APP_KEY": "app-key",
                "PUSHER_APP_SECRET": "app-secret",
                "PUSHER_HOST": "soketi-svc/websocket",
                "PUSHER_PORT": "6001",
            },
            clear=True,
        ):
            client = get_pusher_client()
            assert client is not None
            assert client._pusher_client.host == "soketi-svc"
            assert client._pusher_client.port == 6001

    def test_get_pusher_client_internal_port_and_ssl_overrides(self):
        """
        PUSHER_PORT_INTERNAL and PUSHER_USE_SSL_INTERNAL override standard env vars.
        """
        with patch.dict(
            os.environ,
            {
                "PUSHER_DISABLED": "false",
                "PUSHER_APP_ID": "12345",
                "PUSHER_APP_KEY": "app-key",
                "PUSHER_APP_SECRET": "app-secret",
                "PUSHER_HOST": "localhost",
                "PUSHER_PORT": "6001",
                "PUSHER_USE_SSL": "false",
                "PUSHER_PORT_INTERNAL": "8443",
                "PUSHER_USE_SSL_INTERNAL": "true",
            },
            clear=True,
        ):
            client = get_pusher_client()
            assert client is not None
            assert client._pusher_client.port == 8443
            assert client._pusher_client.ssl is True

    def test_get_pusher_client_invalid_app_id_handling(self):
        """
        Invalid PUSHER_APP_ID (non-numeric) logs a warning and returns None.
        """
        with patch.dict(
            os.environ,
            {
                "PUSHER_DISABLED": "false",
                "PUSHER_APP_ID": "invalid-non-numeric-app-id",
                "PUSHER_APP_KEY": "app-key",
                "PUSHER_APP_SECRET": "app-secret",
                "PUSHER_HOST": "localhost",
            },
            clear=True,
        ):
            client = get_pusher_client()
            assert client is None
