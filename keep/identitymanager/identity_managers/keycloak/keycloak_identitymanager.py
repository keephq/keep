import json
import os

from fastapi import HTTPException
from keycloak.exceptions import KeycloakDeleteError, KeycloakGetError, KeycloakPostError
from keycloak.uma_permissions import UMAPermission

from keep.api.models.user import Group, PermissionEntity, ResourcePermission, User
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
            self.client_id = self.keycloak_admin.get_client_id(
                os.environ["KEYCLOAK_CLIENT_ID"]
            )
            keycloak_openid = KeycloakOpenID(
                server_url=os.environ["KEYCLOAK_URL"],
                realm_name=os.environ["KEYCLOAK_REALM"],
                client_id=os.environ["KEYCLOAK_CLIENT_ID"],
                client_secret_key=os.environ["KEYCLOAK_CLIENT_SECRET"],
            )
            self.keycloak_uma = KeycloakUMA(connection=keycloak_openid)
            self.admin_url = f'{os.environ["KEYCLOAK_URL"]}/admin/realms/{os.environ["KEYCLOAK_REALM"]}/clients/{self.client_id}'
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
        self, resource_id: str, resource_name: str, scopes: list[str] = []
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

    def check_permissions(
        self,
        resource_ids: list[str],
        scope: str,
        authenticated_entity: AuthenticatedEntity,
    ) -> None:
        try:
            permissions = [
                UMAPermission(resource=resource_id, scope=scope)
                for resource_id in resource_ids
            ]
            has_permission = self.keycloak_uma.permissions_check(
                token=authenticated_entity.access_token,
                permissions=permissions,
            )

            if not has_permission:
                self.logger.info(
                    "Permission denied for resource_ids: %s, scope: %s",
                    resource_ids,
                    scope,
                )
                raise HTTPException(status_code=403, detail="Permission denied")

            self.logger.info(
                "Permission check successful for resource_ids: %s, scope: %s",
                resource_ids,
                scope,
            )
        except Exception as e:
            self.logger.error("Failed to check permissions in Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to check permissions")

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

    def get_groups(self) -> list[dict]:
        try:
            groups = self.keycloak_admin.get_groups(
                query={"briefRepresentation": False}
            )
            result = []
            for group in groups:
                group_id = group["id"]
                group_name = group["name"]
                roles = group.get("clientRoles", {}).get("keep", [])

                # Fetch members for each group
                members = self.keycloak_admin.get_group_members(group_id)
                member_names = [member.get("username", "") for member in members]
                member_count = len(members)

                result.append(
                    Group(
                        id=group_id,
                        name=group_name,
                        roles=roles,
                        memberCount=member_count,
                        members=member_names,
                    )
                )
            return result
        except KeycloakGetError as e:
            self.logger.error("Failed to fetch groups from Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to fetch groups")

    def create_permissions(self, permissions: list[ResourcePermission]) -> None:
        try:
            existing_permissions = self.keycloak_admin.get_client_authz_permissions(
                self.client_id,
            )
            existing_permission_names_to_permissions = {
                permission["name"]: permission for permission in existing_permissions
            }
            for permission in permissions:
                # 1. first, create the resource if its not already created
                resp = self.keycloak_admin.create_client_authz_resource(
                    self.client_id,
                    {
                        "name": permission.resource_id,
                        "displayName": permission.resource_name,
                        "type": permission.resource_type,
                        "scopes": [],
                    },
                    skip_exists=True,
                )
                # 2. create the policy if it doesn't exist:
                policies = []
                for perm in permission.permissions:
                    try:
                        if perm.type == "user":
                            # we need the user id from email:
                            # TODO: this is not efficient, we should cache this
                            users = self.keycloak_admin.get_users({})
                            user = next(
                                (user for user in users if user["email"] == perm.id),
                                None,
                            )
                            if not user:
                                raise HTTPException(
                                    status_code=400, detail="User not found"
                                )
                            resp = self.keycloak_admin.connection.raw_post(
                                f"{self.admin_url}/authz/resource-server/policy/user",
                                data=json.dumps(
                                    {
                                        "name": f"Allow user {user.get('id')} to access resource type {permission.resource_type} with name {permission.resource_name}",
                                        "description": json.dumps(
                                            {
                                                "user_id": user.get("id"),
                                                "user_email": user.get("email"),
                                                "resource_id": permission.resource_id,
                                            }
                                        ),
                                        "logic": "POSITIVE",
                                        "users": [user.get("id")],
                                    }
                                ),
                            )
                            try:
                                resp.raise_for_status()
                            # 409 is ok, it means the policy already exists
                            except Exception as e:
                                if resp.status_code != 409:
                                    raise e
                                # just continue to next policy
                                else:
                                    continue
                            policy_id = resp.json().get("id")
                            policies.append(policy_id)
                        else:
                            resp = self.keycloak_admin.connection.raw_post(
                                f"{self.admin_url}/authz/resource-server/policy/group",
                                data=json.dumps(
                                    {
                                        "name": f"Allow group {perm.id} to access resource type {permission.resource_type} with name {permission.resource_name}",
                                        "description": json.dumps(
                                            {
                                                "group_id": perm.id,
                                                "resource_id": permission.resource_id,
                                            }
                                        ),
                                        "logic": "POSITIVE",
                                        "groups": [
                                            {"id": perm.id, "extendChildren": False}
                                        ],
                                        "groupsClaim": "",
                                    }
                                ),
                            )
                            try:
                                resp.raise_for_status()
                            # 409 is ok, it means the policy already exists
                            except Exception as e:
                                if resp.status_code != 409:
                                    raise e
                                else:
                                    continue
                            policy_id = resp.json().get("id")
                            policies.append(policy_id)
                    except KeycloakPostError as e:
                        if "already exists" in str(e):
                            self.logger.info("Policy already exists in Keycloak")
                            # its ok!
                            pass
                        else:
                            self.logger.error(
                                "Failed to create policy in Keycloak: %s", str(e)
                            )
                            raise HTTPException(
                                status_code=500, detail="Failed to create policy"
                            )
                    except Exception as e:
                        self.logger.error(
                            "Failed to create policy in Keycloak: %s", str(e)
                        )
                        raise HTTPException(
                            status_code=500, detail="Failed to create policy"
                        )

                # 3. Finally, create the resource
                # 3.0 try to get the resource based permission
                permission_name = f"Permission on resource type {permission.resource_type} with name {permission.resource_name}"
                if existing_permission_names_to_permissions.get(permission_name):
                    # update the permission
                    existing_permissions = existing_permission_names_to_permissions[
                        permission_name
                    ]
                    existing_permission_id = existing_permissions["id"]
                    # if no new policies, continue
                    if not policies:
                        continue
                    # add the new policies
                    associated_policies = self.keycloak_admin.get_client_authz_permission_associated_policies(
                        self.client_id, existing_permission_id
                    )
                    existing_permissions["policies"] = [
                        policy["id"] for policy in associated_policies
                    ]
                    existing_permissions["policies"].extend(policies)
                    # update the policy to include the new policy
                    resp = self.keycloak_admin.connection.raw_put(
                        f"{self.admin_url}/authz/resource-server/permission/resource/{existing_permission_id}",
                        data=json.dumps(existing_permissions),
                    )
                    resp.raise_for_status()
                else:
                    # 3.2 else, create it
                    self.keycloak_admin.create_client_authz_resource_based_permission(
                        self.client_id,
                        {
                            "type": "resource",
                            "name": f"Permission on resource type {permission.resource_type} with name {permission.resource_name}",
                            "scopes": [],
                            "policies": policies,
                            "resources": [
                                permission.resource_id,
                            ],
                            "decisionStrategy": "Affirmative".upper(),
                        },
                    )
        except KeycloakPostError as e:
            if "already exists" in str(e):
                self.logger.info("Permission already exists in Keycloak")
                raise HTTPException(status_code=409, detail="Permission already exists")
            else:
                self.logger.error(
                    "Failed to create permissions in Keycloak: %s", str(e)
                )
                raise HTTPException(
                    status_code=500, detail="Failed to create permissions"
                )
        except Exception as e:
            self.logger.error("Failed to create permissions in Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to create permissions")

    def get_permissions(self) -> list[ResourcePermission]:
        try:
            resources = self.keycloak_admin.get_client_authz_resources(self.client_id)
            resources_to_policies = {}
            permissions = self.keycloak_admin.get_client_authz_permissions(
                self.client_id
            )
            for permission in permissions:
                permission_id = permission["id"]
                associated_policies = (
                    self.keycloak_admin.get_client_authz_permission_associated_policies(
                        self.client_id, permission_id
                    )
                )
                for policy in associated_policies:
                    details = json.loads(policy["description"])
                    resource_id = details["resource_id"]
                    if resource_id not in resources_to_policies:
                        resources_to_policies[resource_id] = []
                    if policy.get("type") == "user":
                        resources_to_policies[resource_id].append(
                            {"id": details.get("user_email"), "type": "user"}
                        )
                    else:
                        resources_to_policies[resource_id].append(
                            {"id": details["group_id"], "type": "group"}
                        )
            permissions_dto = []
            for resource in resources:
                resource_id = resource["name"]
                resource_name = resource["displayName"]
                resource_type = resource["type"]
                permissions_dto.append(
                    ResourcePermission(
                        resource_id=resource_id,
                        resource_name=resource_name,
                        resource_type=resource_type,
                        permissions=[
                            PermissionEntity(
                                id=policy["id"],
                                type=policy["type"],
                            )
                            for policy in resources_to_policies.get(resource_id, [])
                        ],
                    )
                )
            return permissions_dto
        except KeycloakGetError as e:
            self.logger.error("Failed to fetch permissions from Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to fetch permissions")

    def get_user_permission_on_resource_type(
        self, resource_type: str, authenticated_entity: AuthenticatedEntity
    ) -> list[ResourcePermission]:
        """
        Get permissions for a specific user on a specific resource type.

        Args:
            resource_type (str): The type of resource for which to retrieve permissions.
            user_id (str): The ID of the user for which to retrieve permissions.

        Returns:
            list: A list of permission objects.
        """
        pass
