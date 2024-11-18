import logging
import os

from fastapi import Depends, HTTPException

from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme
from keycloak import KeycloakOpenID, KeycloakOpenIDConnection
from keycloak.keycloak_uma import KeycloakUMA
from keycloak.uma_permissions import UMAPermission

logger = logging.getLogger(__name__)


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
            client_secret_key=os.environ.get("KEYCLOAK_CLIENT_SECRET"),
        )
        self.keycloak_openid_connection = KeycloakOpenIDConnection(
            server_url=self.keycloak_url,
            realm_name=self.keycloak_realm,
            client_id=self.keycloak_client_id,
            client_secret_key=os.environ.get("KEYCLOAK_CLIENT_SECRET"),
        )
        self.keycloak_uma = KeycloakUMA(connection=self.keycloak_openid_connection)
        # will be populated in on_start of the identity manager
        self.protected_resource = None

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        # verify keycloak token
        try:
            payload = self.keycloak_client.decode_token(token, validate=True)
        except Exception as e:
            if "Expired" in str(e):
                raise HTTPException(status_code=401, detail="Expired Keycloak token")
            raise HTTPException(status_code=401, detail="Invalid Keycloak token")
        tenant_id = payload.get("keep_tenant_id")
        email = payload.get("preferred_username")
        org_id = payload.get("active_organization", {}).get("id")
        org_realm = payload.get("active_organization", {}).get("name")
        if org_id is None or org_realm is None:
            logger.warning(
                "Invalid Keycloak configuration - no org information for user. Check organization mapper: https://github.com/keephq/keep/blob/main/keycloak/keep-realm.json#L93"
            )
        role = (
            payload.get("resource_access", {})
            .get(self.keycloak_client_id, {})
            .get("roles", [])
        )
        # filter out uma_protection
        role = [r for r in role if not r.startswith("uma_protection")]
        if not role:
            raise HTTPException(
                status_code=401, detail="Invalid Keycloak token - no role"
            )

        role = role[0]
        return AuthenticatedEntity(
            tenant_id,
            email,
            None,
            role,
            org_id=org_id,
            org_realm=org_realm,
            token=token,
        )

    def _authorize(self, authenticated_entity: AuthenticatedEntity) -> None:
        # use Keycloak's UMA to authorize
        try:
            permission = UMAPermission(
                resource=self.protected_resource,
                scope=self.scopes[0],  # todo: handle multiple scopes per resource
            )
            allowed = self.keycloak_uma.permissions_check(
                token=authenticated_entity.token, permissions=[permission]
            )
            if not allowed:
                raise HTTPException(status_code=401, detail="Permission check failed")
        # secure fallback
        except Exception as e:
            raise HTTPException(
                status_code=401, detail="Permission check failed - " + str(e)
            )
        return allowed

    def authorize_resource(
        self, resource_type, resource_id, authenticated_entity: AuthenticatedEntity
    ) -> None:
        # use Keycloak's UMA to authorize
        try:
            permission = UMAPermission(
                resource=resource_id,
            )
            allowed = self.keycloak_uma.permissions_check(
                token=authenticated_entity.token, permissions=[permission]
            )
            if not allowed:
                raise HTTPException(status_code=401, detail="Permission check failed")
        # secure fallback
        except Exception:
            raise HTTPException(status_code=401, detail="Permission check failed")
        return allowed
