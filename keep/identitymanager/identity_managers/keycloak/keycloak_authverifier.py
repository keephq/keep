import os

from fastapi import Depends, HTTPException

from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme
from keep.identitymanager.rbac import get_role_by_role_name
from keycloak import KeycloakOpenID


class KeycloakAuthVerifier(AuthVerifierBase):
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

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        # verify keycloak token
        try:
            payload = self.keycloak_client.decode_token(token, validate=True)
            tenant_id = payload.get("keep_tenant_id")
            email = payload.get("preferred_username")
            org_id = payload.get("active_organization", {}).get("id")
            org_realm = payload.get("active_organization", {}).get("name")
            role_name = "admin"
            # TODO: add groups
            # role_name = payload.get("keep_role")
            # if not role_name:
            #    raise HTTPException(
            #        status_code=401, detail="Invalid Keycloak token - no role in token"
            #    )
            role = get_role_by_role_name(role_name)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid Keycloak token")

        # validate scopes
        if not role.has_scopes(self.scopes):
            raise HTTPException(
                status_code=403,
                detail="You don't have the required permissions to access this resource",
            )
        return AuthenticatedEntity(
            tenant_id, email, None, role_name, org_id=org_id, org_realm=org_realm
        )
