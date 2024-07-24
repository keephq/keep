import os

from fastapi import HTTPException
from keycloak.exceptions import KeycloakDeleteError, KeycloakGetError, KeycloakPostError
from keycloak.uma_permissions import UMAPermission

from keep.api.models.user import User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.identitymanager import BaseIdentityManager
from keycloak import KeycloakAdmin, KeycloakOpenID, KeycloakUMA

from .keycloak_authverifier import KeycloakAuthVerifier


class KeycloakIdentityManager(BaseIdentityManager):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        self.server_url = os.environ.get("KEYCLOAK_URL")
        try:
            self.keycloak_admin = KeycloakAdmin(
                server_url=os.environ["KEYCLOAK_URL"] + "/admin",
                username=os.environ.get("KEYCLOAK_ADMIN_USER"),
                password=os.environ.get("KEYCLOAK_ADMIN_PASSWORD"),
                realm_name=os.environ["KEYCLOAK_REALM"],
                verify=True,
            )
            keycloak_openid = KeycloakOpenID(
                server_url=os.environ["KEYCLOAK_URL"],
                realm_name=os.environ["KEYCLOAK_REALM"],
                client_id=os.environ["KEYCLOAK_CLIENT_ID"],
                client_secret_key=os.environ["KEYCLOAK_CLIENT_SECRET"],
            )
            self.keycloak_uma = KeycloakUMA(connection=keycloak_openid)
        except Exception as e:
            self.logger.error(
                "Failed to initialize Keycloak Identity Manager: %s", str(e)
            )
            raise
        self.logger.info("Keycloak Identity Manager initialized")

    @property
    def support_sso(self) -> bool:
        return True

    def get_sso_providers(self) -> list[str]:
        return []

    def get_sso_wizard_url(self, authenticated_entity: AuthenticatedEntity) -> str:
        tenant_realm = authenticated_entity.org_realm
        org_id = authenticated_entity.org_id
        return f"{self.server_url}realms/{tenant_realm}/wizard/?org_id={org_id}/#iss={self.server_url}/realms/{tenant_realm}"

    def get_users(self) -> list[User]:
        try:
            users = self.keycloak_admin.get_users({})
            users = [user for user in users if "firstName" in user]

            users_dto = []
            for user in users:
                role = user.get("attributes", {}).get("keep_role", ["admin"])[0]
                user_dto = User(
                    email=user["email"],
                    name=user["firstName"],
                    role=role,
                    created_at=user.get("createdTimestamp", ""),
                )
                users_dto.append(user_dto)
            return users_dto
        except KeycloakGetError as e:
            self.logger.error("Failed to fetch users from Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to fetch users")

    def create_user(self, user_email: str, password: str, role: str) -> dict:
        try:
            user_data = {
                "username": user_email,
                "enabled": True,
                "attributes": {"keep_role": [role]},
            }
            if password:
                user_data["credentials"] = [
                    {"type": "password", "value": password, "temporary": False}
                ]

            user_id = self.keycloak_admin.create_user(user_data)
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

    def create_resource(
        self, resource_id: str, resource_name: str, scopes: list[str]
    ) -> None:
        resource = {
            "name": resource_name,
            "type": "urn:your-app:resources:" + resource_name,
            "uris": ["/" + resource_name + "/" + resource_id],
            "scopes": [{"name": scope} for scope in scopes],
        }
        try:
            self.keycloak_admin.create_client_authz_resource(
                os.environ["KEYCLOAK_CLIENT_ID"], resource
            )
        except KeycloakPostError as e:
            self.logger.error("Failed to create resource in Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to create resource")

    def delete_resource(self, resource_id: str) -> None:
        try:
            resources = self.keycloak_admin.get_client_authz_resources(
                os.environ["KEYCLOAK_CLIENT_ID"]
            )
            for resource in resources:
                if resource["uris"] == ["/resource/" + resource_id]:
                    self.keycloak_admin.delete_client_authz_resource(
                        os.environ["KEYCLOAK_CLIENT_ID"], resource["id"]
                    )
        except KeycloakDeleteError as e:
            self.logger.error("Failed to delete resource from Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to delete resource")

    def check_permission(
        self, resource_id: str, scope: str, authenticated_entity: AuthenticatedEntity
    ) -> None:
        try:
            permission = UMAPermission(resource=resource_id, scope=scope)
            has_permission = self.keycloak_uma.permissions_check(
                token=authenticated_entity.access_token, permissions=[permission]
            )

            if not has_permission:
                self.logger.info(
                    "Permission denied for resource_id: %s, scope: %s",
                    resource_id,
                    scope,
                )
                raise HTTPException(status_code=403, detail="Permission denied")

            self.logger.info(
                "Permission check successful for resource_id: %s, scope: %s",
                resource_id,
                scope,
            )

        except Exception as e:
            self.logger.error("Failed to check permissions in Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to check permissions")
