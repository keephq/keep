import os
import secrets

import jwt
from fastapi import HTTPException

from keep.api.core.rbac import Admin as AdminRole
from keep.api.core.rbac import get_role_by_role_name
from keep.api.models.user import User
from keep.api.utils.auth0_utils import getAuth0Client
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.identitymanager import BaseIdentityManager

# Note: cache_keys is set to True to avoid fetching the jwks keys on every request
auth_domain = os.environ.get("AUTH0_DOMAIN")
if auth_domain:
    jwks_uri = f"https://{auth_domain}/.well-known/jwks.json"
    jwks_client = jwt.PyJWKClient(jwks_uri, cache_keys=True)
else:
    jwks_client = None


class Auth0IdentityManager(BaseIdentityManager):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        self.logger.info("Auth0IdentityManager initialized")

    def get_users(self) -> list[User]:
        auth0 = getAuth0Client()
        users = auth0.users.list(q=f'app_metadata.keep_tenant_id:"{self.tenant_id}"')
        users = [
            User(
                email=user["email"],
                name=user["name"],
                # for backwards compatibility we return admin if no role is set
                role=user.get("app_metadata", {}).get(
                    "keep_role", AdminRole.get_name()
                ),
                last_login=user.get("last_login", None),
                created_at=user["created_at"],
                picture=user["picture"],
            )
            for user in users.get("users", [])
        ]
        return users

    def create_user(self, user_email: str, role: str) -> dict:
        auth0 = getAuth0Client()
        # User email can exist in 1 tenant only for now.
        users = auth0.users.list(q=f'email:"{user_email}"')
        if users.get("users", []):
            raise HTTPException(status_code=409, detail="User already exists")
        user = auth0.users.create(
            {
                "email": user_email,
                "password": secrets.token_urlsafe(13),
                "email_verified": True,
                "app_metadata": {"keep_tenant_id": self.tenant_id, "keep_role": role},
                "connection": "keep-users",  # TODO: move to env
            }
        )
        user_dto = User(
            email=user["email"],
            name=user["name"],
            # for backwards compatibility we return admin if no role is set
            role=user.get("app_metadata", {}).get("keep_role", AdminRole.get_name()),
            last_login=user.get("last_login", None),
            created_at=user["created_at"],
            picture=user["picture"],
        )
        return user_dto

    def delete_user(self, user_email: str) -> dict:
        auth0 = getAuth0Client()
        users = auth0.users.list(q=f'app_metadata.keep_tenant_id:"{self.tenant_id}"')
        for user in users.get("users", []):
            if user["email"] == user_email:
                auth0.users.delete(user["user_id"])
                return {"status": "OK"}
        raise HTTPException(status_code=404, detail="User not found")

    def get_auth_verifier(self, scopes) -> AuthVerifierBase:
        return Auth0AuthVerifier(scopes)


class Auth0AuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for multi tenant mode"""

    def __init__(self, scopes: list[str] = []) -> None:
        # TODO: this verifier should be instansiate once and not for every endpoint/route
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
                tenant_id = payload.get("keep_tenant_id")
                role_name = payload.get(
                    "keep_role", AdminRole.get_name()
                )  # default to admin for backwards compatibility
                email = payload.get("email")
                role = get_role_by_role_name(role_name)
                # validate scopes
                if not role.has_scopes(self.scopes):
                    raise HTTPException(
                        status_code=403,
                        detail="You don't have the required permissions to access this resource",
                    )
                return AuthenticatedEntity(tenant_id, email, role=role_name)
            # authorization error
            except HTTPException:
                raise
            except jwt.exceptions.DecodeError:
                self.logger.exception("Failed to decode token")
                raise HTTPException(status_code=401, detail="Token is not a valid JWT")
            except Exception as e:
                self.logger.exception("Failed to validate token")
                raise HTTPException(status_code=401, detail=str(e))
