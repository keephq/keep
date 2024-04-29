import os

from fastapi import Depends, HTTPException

from keep.api.core.rbac import get_role_by_role_name
from keep.api.models.user import User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme
from keep.identitymanager.identitymanager import BaseIdentityManager
from keycloak import KeycloakOpenID


class KeycloakIdentityManager(BaseIdentityManager):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        self.logger.info("Keycloak Identity Manager initialized")

    def get_users() -> list[User]:
        # implement
        pass

    def create_user(self, user_email: str, password: str, role: str) -> dict:
        # implement
        pass

    def delete_user(user_email: str) -> dict:
        # implement
        pass

    def get_auth_verifier(self, scopes: list) -> AuthVerifierBase:
        return AuthVerifierKeycloak(scopes)


class AuthVerifierKeycloak(AuthVerifierBase):
    """Handles authentication and authorization for Keycloak"""

    def __init__(self, scopes: list[str] = []) -> None:
        super().__init__(scopes)
        self.keycloak_url = os.environ.get("KEYCLOAK_URL")
        self.keycloak_realm = os.environ.get("KEYCLOAK_REALM")
        self.keycloak_client_id = os.environ.get("KEYCLOAK_CLIENT_ID")
        self.keycloak_audience = os.environ.get("KEYCLOAK_AUDIENCE")
        if (
            not self.keycloak_url
            or not self.keycloak_realm
            or not self.keycloak_client_id
        ):
            raise Exception(
                "Missing KEYCLOAK_URL, KEYCLOAK_REALM or KEYCLOAK_CLIENT_ID environment variable"
            )

        self.keycloak_client = KeycloakOpenID(
            server_url=self.keycloak_url,
            realm_name=self.keycloak_realm,
            client_id=self.keycloak_client_id,
        )
        self.keycloak_public_key = (
            "-----BEGIN PUBLIC KEY-----\n"
            + self.keycloak_client.public_key()
            + "\n-----END PUBLIC KEY-----"
        )
        self.verify_options = {
            "verify_signature": True,
            "verify_aud": True,
            "verify_exp": True,
        }

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        # verify keycloak token
        try:
            payload = self.keycloak_client.decode_token(
                token, key=self.keycloak_public_key, options=self.verify_options
            )
            tenant_id = payload.get("keep_tenant_id")
            email = payload.get("preferred_username")
            role_name = payload.get("keep_role")
            if not role_name:
                raise HTTPException(
                    status_code=401, detail="Invalid Keycloak token - no role in token"
                )
            role = get_role_by_role_name(role_name)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid Keycloak token")

        # validate scopes
        if not role.has_scopes(self.scopes):
            raise HTTPException(
                status_code=403,
                detail="You don't have the required permissions to access this resource",
            )
        return AuthenticatedEntity(tenant_id, email, None, role_name)
