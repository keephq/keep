import os

from fastapi import Depends, HTTPException
from keycloak.exceptions import KeycloakDeleteError, KeycloakGetError, KeycloakPostError

from keep.api.core.rbac import get_role_by_role_name
from keep.api.models.user import User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme
from keep.identitymanager.identitymanager import BaseIdentityManager
from keycloak import KeycloakAdmin, KeycloakOpenID


class KeycloakIdentityManager(BaseIdentityManager):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        try:
            self.keycloak_admin = KeycloakAdmin(
                server_url=os.environ["KEYCLOAK_URL"] + "/admin",
                username=os.environ.get("KEYCLOAK_ADMIN_USER"),
                password=os.environ.get("KEYCLOAK_ADMIN_PASSWORD"),
                realm_name=os.environ["KEYCLOAK_REALM"],
                verify=True,
            )
        except Exception as e:
            self.logger.error(
                "Failed to initialize Keycloak Identity Manager: %s", str(e)
            )
            raise
        self.logger.info("Keycloak Identity Manager initialized")

    def get_users(self) -> list[User]:
        try:
            users = self.keycloak_admin.get_users({})
            # we want only users with 'keep_role' attribute so we know they are related to Keep
            # todo: created_at for users spinned up
            users = [
                user for user in users if "keep_role" in user.get("attributes", {})
            ]
            return [
                User(
                    email=user["email"],
                    name=user["username"],
                    role=user["attributes"]["keep_role"][0],
                    created_at=user.get("createdTimestamp", ""),
                )
                for user in users
            ]
        except KeycloakGetError as e:
            self.logger.error("Failed to fetch users from Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to fetch users")

    def create_user(self, user_email: str, password: str, role: str) -> dict:
        try:
            # if this is user/password - create user with password
            if password:
                user_id = self.keycloak_admin.create_user(
                    {
                        "username": user_email,
                        "enabled": True,
                        "credentials": [
                            {"type": "password", "value": password, "temporary": False}
                        ],
                        "attributes": {"keep_role": [role]},
                    }
                )
            # else - sso, saml, etc
            else:
                user_id = self.keycloak_admin.create_user(
                    {
                        "username": user_email,
                        "enabled": True,
                        "attributes": {"keep_role": [role]},
                    }
                )
            # TODO: assign real roles self.keycloak_admin.assign_client_role(elf.keycloak_admin.assign_client_role(user_id, client_id=self.keycloak_admin.client_id, roles=[{"id": role_id, "name": role}])
            return {
                "status": "success",
                "message": "User created successfully",
                "user_id": user_id,
            }
        except KeycloakPostError as e:
            self.logger.error("Failed to create user in Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to create user")

    def delete_user(self, user_email: str) -> dict:
        try:
            user_id = self.keycloak_admin.get_user_id(username=user_email)
            self.keycloak_admin.delete_user(user_id)
            return {"status": "success", "message": "User deleted successfully"}
        except KeycloakDeleteError as e:
            self.logger.error("Failed to delete user from Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to delete user")

    def get_auth_verifier(self, scopes: list) -> AuthVerifierBase:
        return KeycloakAuthVerifier(scopes)


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
