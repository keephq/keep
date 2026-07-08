from unittest.mock import patch

from keep.providers.cilium_provider.secure_channel import build_cilium_channel

PATCH_GRPC = "keep.providers.cilium_provider.secure_channel.grpc"


def test_insecure_channel_when_tls_disabled():
    with patch(PATCH_GRPC) as mock_grpc:
        channel = build_cilium_channel("localhost:4245", use_tls=False)
        mock_grpc.insecure_channel.assert_called_once_with("localhost:4245")
        mock_grpc.secure_channel.assert_not_called()
        assert channel is mock_grpc.insecure_channel.return_value


def test_mutual_tls_passes_encoded_pem():
    with patch(PATCH_GRPC) as mock_grpc:
        channel = build_cilium_channel(
            "relay:4245",
            use_tls=True,
            ca_certificate="CA_PEM",
            client_certificate="CERT_PEM",
            client_key="KEY_PEM",
        )
        mock_grpc.ssl_channel_credentials.assert_called_once_with(
            root_certificates=b"CA_PEM",
            certificate_chain=b"CERT_PEM",
            private_key=b"KEY_PEM",
        )
        mock_grpc.secure_channel.assert_called_once_with(
            "relay:4245", mock_grpc.ssl_channel_credentials.return_value
        )
        mock_grpc.insecure_channel.assert_not_called()
        assert channel is mock_grpc.secure_channel.return_value


def test_server_only_tls_omits_client_material():
    with patch(PATCH_GRPC) as mock_grpc:
        build_cilium_channel("relay:4245", use_tls=True, ca_certificate="CA_PEM")
        mock_grpc.ssl_channel_credentials.assert_called_once_with(
            root_certificates=b"CA_PEM",
            certificate_chain=None,
            private_key=None,
        )


def test_tls_without_ca_uses_system_trust():
    with patch(PATCH_GRPC) as mock_grpc:
        build_cilium_channel("relay:4245", use_tls=True)
        mock_grpc.ssl_channel_credentials.assert_called_once_with(
            root_certificates=None,
            certificate_chain=None,
            private_key=None,
        )
