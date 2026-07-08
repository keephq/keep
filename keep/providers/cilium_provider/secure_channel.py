import grpc


def build_cilium_channel(
    endpoint: str,
    use_tls: bool = False,
    ca_certificate: str = "",
    client_certificate: str = "",
    client_key: str = "",
) -> grpc.Channel:
    """Build a gRPC channel to the Hubble relay, secured with TLS when enabled.

    When use_tls is set, the connection uses TLS; supplying client_certificate and
    client_key enables mutual TLS, and ca_certificate verifies the server (falling
    back to the system trust store when omitted).
    """
    if not use_tls:
        return grpc.insecure_channel(endpoint)
    credentials = grpc.ssl_channel_credentials(
        root_certificates=ca_certificate.encode() if ca_certificate else None,
        certificate_chain=client_certificate.encode() if client_certificate else None,
        private_key=client_key.encode() if client_key else None,
    )
    return grpc.secure_channel(endpoint, credentials)
