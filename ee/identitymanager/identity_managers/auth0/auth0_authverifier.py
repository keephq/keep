import os

import jwt
from fastapi import HTTPException

from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.rbac import Admin as AdminRole

# Note: cache_keys is set to True to avoid fetching the jwks keys on every request
auth_domain = os.environ.get("AUTH0_DOMAIN")
if auth_domain:
    jwks_uri = f"https://{auth_domain}/.well-known/jwks.json"
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
        self.jwks_uri = f"https://{self.auth_domain}/.well-known/jwks.json"
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
