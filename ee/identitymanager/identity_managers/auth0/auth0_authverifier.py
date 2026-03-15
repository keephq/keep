import logging
import os

import jwt
import requests
from fastapi import HTTPException

from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.rbac import Admin as AdminRole

logger = logging.getLogger(__name__)


def _discover_jwks_uri(auth_domain: str) -> str:
    """Discover the JWKS URI via the OpenID Connect Discovery endpoint.

    Per the OpenID Connect Discovery 1.0 specification
    (https://openid.net/specs/openid-connect-discovery-1_0.html#rfc.section.3),
    the ``jwks_uri`` should be obtained from the provider's discovery document
    at ``{issuer}/.well-known/openid-configuration``.

    Falls back to the Auth0-style ``/.well-known/jwks.json`` path when the
    discovery document is unavailable or does not contain ``jwks_uri``.
    """
    discovery_url = f"https://{auth_domain}/.well-known/openid-configuration"
    try:
        resp = requests.get(discovery_url, timeout=10)
        resp.raise_for_status()
        discovered_uri = resp.json().get("jwks_uri")
        if discovered_uri:
            return discovered_uri
        logger.warning(
            "OpenID discovery document at %s did not contain jwks_uri, "
            "falling back to /.well-known/jwks.json",
            discovery_url,
        )
    except Exception:
        logger.warning(
            "Failed to fetch OpenID discovery document from %s, "
            "falling back to /.well-known/jwks.json",
            discovery_url,
            exc_info=True,
        )
    # Fallback: Auth0's conventional JWKS endpoint
    return f"https://{auth_domain}/.well-known/jwks.json"


# Note: cache_keys is set to True to avoid fetching the jwks keys on every request
auth_domain = os.environ.get("AUTH0_DOMAIN")
if auth_domain:
    jwks_uri = _discover_jwks_uri(auth_domain)
    jwks_client = jwt.PyJWKClient(
        jwks_uri, cache_keys=True, headers={"User-Agent": "keep-api"}
    )
else:
    jwks_client = None


class Auth0AuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for multi tenant mode"""

    def __init__(self, scopes: list[str] = []) -> None:
        # TODO: this verifier should be instantiated once and not for every endpoint/route
        #       to better cache the jwks keys
        super().__init__(scopes)
        # init once so the cache will actually work
        self.auth_domain = os.environ.get("AUTH0_DOMAIN")
        if not self.auth_domain:
            raise Exception("Missing AUTH0_DOMAIN environment variable")
        self.jwks_uri = _discover_jwks_uri(self.auth_domain)
        # Note: cache_keys is set to True to avoid fetching the jwks keys on every request
        #       but it currently caches only per-route. After moving this auth verifier to be a singleton, we can cache it globally
        self.issuer = f"https://{self.auth_domain}/"
        self.auth_audience = os.environ.get("AUTH0_AUDIENCE")

    def _verify_bearer_token(self, token) -> AuthenticatedEntity:
        from opentelemetry import trace

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("verify_bearer_token"):
            if not token:
                raise HTTPException(status_code=401, detail="No token provided 👈")

            # more than one tenant support
            if token.startswith("keepActiveTenant"):
                active_tenant, token = token.split("&")
                active_tenant = active_tenant.split("=")[1]
            else:
                active_tenant = None

            try:
                jwt_signing_key = jwks_client.get_signing_key_from_jwt(token).key
                payload = jwt.decode(
                    token,
                    jwt_signing_key,
                    algorithms="RS256",
                    audience=self.auth_audience,
                    issuer=self.issuer,
                    leeway=60,
                )
                # if active_tenant is set, we must verify its in the token
                if active_tenant:
                    active_tenant_found = False
                    for tenant in payload.get("keep_tenant_ids", []):
                        if tenant.get("tenant_id") == active_tenant:
                            active_tenant_found = True
                            break
                    if not active_tenant_found:
                        self.logger.warning(
                            "Someone tries to use a token with a tenant that is not in the token"
                        )
                        raise HTTPException(
                            status_code=401,
                            detail="Token does not contain the active tenant",
                        )
                    tenant_id = active_tenant
                else:
                    tenant_id = payload.get("keep_tenant_id")
                role_name = payload.get(
                    "keep_role", AdminRole.get_name()
                )  # default to admin for backwards compatibility
                email = payload.get("email")
                return AuthenticatedEntity(tenant_id, email, role=role_name)
            except jwt.exceptions.DecodeError:
                self.logger.exception("Failed to decode token")
                raise HTTPException(status_code=401, detail="Token is not a valid JWT")
            except Exception as e:
                self.logger.exception("Failed to validate token")
                raise HTTPException(status_code=401, detail=str(e))
