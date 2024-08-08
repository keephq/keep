import json
import os

import requests
from fastapi import HTTPException
from keycloak.exceptions import KeycloakDeleteError, KeycloakGetError, KeycloakPostError
from keycloak.openid_connection import KeycloakOpenIDConnection
from keycloak.uma_permissions import UMAPermission

from keep.api.models.user import Group, PermissionEntity, ResourcePermission, Role, User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import (
    ALL_RESOURCES,
    AuthVerifierBase,
    get_all_scopes,
)
from keep.identitymanager.identity_managers.keycloak.keycloak_authverifier import (
    KeycloakAuthVerifier,
)
from keep.identitymanager.identitymanager import PREDEFINED_ROLES, BaseIdentityManager
from keycloak import KeycloakAdmin, KeycloakUMA

# Some good sources on this topic:
# 1. https://stackoverflow.com/questions/42186537/resources-scopes-permissions-and-policies-in-keycloak
# 2. MUST READ - https://www.keycloak.org/docs/24.0.4/authorization_services/
# 3. ADMIN REST API - https://www.keycloak.org/docs-api/22.0.1/rest-api/index.html
# 4. (TODO) PROTECTION API - https://www.keycloak.org/docs/latest/authorization_services/index.html#_service_protection_api


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
            self.keycloak_id_connection = KeycloakOpenIDConnection(
                server_url=os.environ["KEYCLOAK_URL"],
                client_id=os.environ["KEYCLOAK_CLIENT_ID"],
                realm_name=os.environ["KEYCLOAK_REALM"],
                client_secret_key=os.environ["KEYCLOAK_CLIENT_SECRET"],
            )
            self.keycloak_uma = KeycloakUMA(connection=self.keycloak_id_connection)
            self.admin_url = f'{os.environ["KEYCLOAK_URL"]}/admin/realms/{os.environ["KEYCLOAK_REALM"]}/clients/{self.client_id}'
            self.admin_url_without_client = f'{os.environ["KEYCLOAK_URL"]}/admin/realms/{os.environ["KEYCLOAK_REALM"]}'
            self.realm = os.environ["KEYCLOAK_REALM"]
        except Exception as e:
            self.logger.error(
                "Failed to initialize Keycloak Identity Manager: %s", str(e)
            )
            raise
        self.logger.info("Keycloak Identity Manager initialized")

    def on_start(self, app) -> None:
        for scope in get_all_scopes():
            self.logger.info("Creating scope: %s", scope)
            self.create_scope(scope)
            self.logger.info("Scope created: %s", scope)
        for resource in ALL_RESOURCES:
            self.logger.info("Creating resource: %s", resource)
            self.create_resource(resource)
            self.logger.info("Resource created: %s", resource)
        for role in PREDEFINED_ROLES:
            self.logger.info("Creating role: %s", role)
            self.create_role(role, predefined=True)
            self.logger.info("Role created: %s", role)

    def _scope_name_to_id(self, all_scopes, scope_name: str) -> str:
        # if its ":*":
        if scope_name.split(":")[1] == "*":
            scope_verb = scope_name.split(":")[0]
            scope_ids = [
                scope["id"]
                for scope in all_scopes
                if scope["name"].startswith(scope_verb)
            ]
            return scope_ids
        else:
            scope = next(
                (scope for scope in all_scopes if scope["name"] == scope_name),
                None,
            )
            return [scope["id"]]

    def create_scope_based_permission(self, role: Role, policy_id: str) -> None:
        try:
            scopes = role.scopes
            all_scopes = self.keycloak_admin.get_client_authz_scopes(self.client_id)
            scopes_ids = set()
            for scope in scopes:
                scope_ids = self._scope_name_to_id(all_scopes, scope)
                scopes_ids.update(scope_ids)
            resp = self.keycloak_admin.create_client_authz_scope_permission(
                client_id=self.client_id,
                payload={
                    "name": f"Permission for {role.name}",
                    "scopes": list(scopes_ids),
                    "policies": [policy_id],
                    "resources": [],
                    "decisionStrategy": "Affirmative".upper(),
                    "type": "scope",
                    "logic": "POSITIVE",
                },
            )
            return resp
        except KeycloakPostError as e:
            if "already exists" in str(e):
                self.logger.info("Scope based permission already exists in Keycloak")
                pass
            else:
                self.logger.error(
                    "Failed to create scope based permission in Keycloak: %s", str(e)
                )
                raise HTTPException(
                    status_code=500, detail="Failed to create scope based permission"
                )

    def create_scope(self, scope: str) -> None:
        try:
            self.keycloak_admin.create_client_authz_scopes(
                self.client_id,
                {
                    "name": scope,
                    "displayName": f"Scope for {scope}",
                },
            )
        except KeycloakPostError as e:
            self.logger.error("Failed to create scopes in Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to create scopes")

    def create_role(self, role: Role, predefined=False) -> str:
        try:
            role_name = self.keycloak_admin.create_client_role(
                self.client_id,
                {
                    "name": role.name,
                    "description": f"Role for {role.name}",
                    # we will use this to identify the role as predefined
                    "attributes": {
                        "predefined": [str(predefined).lower()],
                    },
                },
                skip_exists=True,
            )
            role_id = self.keycloak_admin.get_client_role_id(self.client_id, role_name)
            # create the role policy
            policy_id = self.create_role_policy(role_id, role.name, role.description)
            # create the scope based permission
            self.create_scope_based_permission(role, policy_id)
            return role_id
        except KeycloakPostError as e:
            if "already exists" in str(e):
                self.logger.info("Role already exists in Keycloak")
                # its ok!
                pass
            else:
                self.logger.error("Failed to create roles in Keycloak: %s", str(e))
                raise HTTPException(status_code=500, detail="Failed to create roles")

    def update_role(self, role_id: str, role: Role) -> str:
        # just update the policy
        role_id = self.keycloak_admin.get_client_role_id(self.client_id, role.name)
        scopes = role.scopes
        all_scopes = self.keycloak_admin.get_client_authz_scopes(self.client_id)
        scopes_ids = set()
        for scope in scopes:
            scope_ids = self._scope_name_to_id(all_scopes, scope)
            scopes_ids.update(scope_ids)
        # get the scope-based permission
        permissions = self.keycloak_admin.get_client_authz_permissions(self.client_id)
        permission = next(
            (
                permission
                for permission in permissions
                if permission["name"] == f"Permission for {role.name}"
            ),
            None,
        )
        if not permission:
            raise HTTPException(status_code=404, detail="Permission not found")
        permission_id = permission["id"]
        permission["scopes"] = list(scopes_ids)
        resp = self.keycloak_admin.connection.raw_put(
            f"{self.admin_url}/authz/resource-server/permission/scope/{permission_id}",
            data=json.dumps(permission),
        )
        resp.raise_for_status()
        return role_id

    def create_role_policy(self, role_id: str, role_name: str, role_description) -> str:
        try:
            resp = self.keycloak_admin.connection.raw_post(
                f"{self.admin_url}/authz/resource-server/policy/role",
                data=json.dumps(
                    {
                        "name": f"Allow {role_name} to {role_description}",
                        "description": f"Allow {role_name} to {role_description}",  # future use
                        "roles": [{"id": role_id, "required": False}],
                        "logic": "POSITIVE",
                        "fetchRoles": False,
                    }
                ),
            )
            resp.raise_for_status()
            resp = resp.json()
            return resp.get("id")
        except requests.exceptions.HTTPError as e:
            if "Conflict" in str(e):
                self.logger.info("Policy already exists in Keycloak")
                # get its id
                policies = self.get_policies()
                # find by name
                policy = next(
                    (
                        policy
                        for policy in policies
                        if policy["name"] == f"Allow {role_name} to {role_description}"
                    ),
                    None,
                )
                return policy["id"]
            else:
                self.logger.error("Failed to create policies in Keycloak: %s", str(e))
                raise HTTPException(status_code=500, detail="Failed to create policies")
        except Exception as e:
            self.logger.error("Failed to create policies in Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to create policies")

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
                # todo: should be more efficient
                groups = self.keycloak_admin.get_user_groups(user["id"])
                groups = [
                    {
                        "id": group["id"],
                        "name": group["name"],
                    }
                    for group in groups
                ]
                role = self.get_user_current_role(user_id=user.get("id"))
                user_dto = User(
                    email=user["email"],
                    name=user["firstName"],
                    role=role,
                    created_at=user.get("createdTimestamp", ""),
                    ldap=(
                        True
                        if user.get("attributes", {}).get("LDAP_ID", False)
                        else False
                    ),
                    groups=groups,
                )
                users_dto.append(user_dto)
            return users_dto
        except KeycloakGetError as e:
            self.logger.error("Failed to fetch users from Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to fetch users")

    def create_user(
        self,
        user_email: str,
        user_name: str,
        password: str,
        role: list[str],
        groups: list[str],
    ) -> dict:
        try:
            user_data = {
                "username": user_email,
                "email": user_email,
                "enabled": True,
                "firstName": user_name,
            }
            if password:
                user_data["credentials"] = [
                    {"type": "password", "value": password, "temporary": False}
                ]

            user_id = self.keycloak_admin.create_user(user_data)
            if role:
                role_id = self.keycloak_admin.get_client_role_id(self.client_id, role)
                self.keycloak_admin.assign_client_role(
                    client_id=self.client_id,
                    user_id=user_id,
                    roles=[{"id": role_id, "name": role}],
                )
            for group in groups:
                self.add_user_to_group(user_id=user_id, group=group)

            return {
                "status": "success",
                "message": "User created successfully",
                "user_id": user_id,
            }
        except KeycloakPostError as e:
            if "User exists" in str(e):
                self.logger.error(
                    "Failed to create user - user %s already exists", user_email
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"Failed to create user - user {user_email} already exists",
                )
            self.logger.error("Failed to create user in Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to create user")

    def get_user_id_by_email(self, user_email: str) -> str:
        user_id = self.keycloak_admin.get_users(query={"email": user_email})
        if not user_id:
            self.logger.error("User does not exists")
            raise HTTPException(status_code=404, detail="User does not exists")
        elif len(user_id) > 1:
            self.logger.error("Multiple users found")
            raise HTTPException(
                status_code=500, detail="Multiple users found, please contact admin"
            )
        user_id = user_id[0]["id"]
        return user_id

    def get_user_current_role(self, user_id: str) -> str:
        current_role = (
            self.keycloak_admin.connection.raw_get(
                self.admin_url_without_client + f"/users/{user_id}/role-mappings"
            )
            .json()
            .get("clientMappings", {})
            .get(self.realm, {})
            .get("mappings")
        )

        if current_role:
            # remove uma protection
            current_role = [
                role for role in current_role if role["name"] != "uma_protection"
            ]
            return current_role[0]["name"]
        else:
            return None

    def add_user_to_group(self, user_id: str, group: str):
        resp = self.keycloak_admin.connection.raw_put(
            f"{self.admin_url_without_client}/users/{user_id}/groups/{group}",
            data=json.dumps({}),
        )
        resp.raise_for_status()

    def update_user(self, user_email: str, update_data: dict) -> dict:
        try:
            user_id = self.get_user_id_by_email(user_email)
            if "role" in update_data:
                role = update_data["role"]
                # get current role and understand if needs to be updated:
                current_role = self.get_user_current_role(user_id)
                # update the role only if its different than current
                # TODO: more than one role
                if current_role != role:
                    role_id = self.keycloak_admin.get_client_role_id(
                        self.client_id, role
                    )
                    if not role_id:
                        self.logger.error("Role does not exists")
                        raise HTTPException(
                            status_code=404, detail="Role does not exists"
                        )
                    self.keycloak_admin.assign_client_role(
                        client_id=self.client_id,
                        user_id=user_id,
                        roles=[{"id": role_id, "name": role}],
                    )
            if "groups" in update_data:
                # get the current groups
                groups = self.keycloak_admin.get_user_groups(user_id)
                groups_ids = [g.get("id") for g in groups]
                # calc with groups needs to be removed and which to be added
                groups_to_remove = [
                    group_id
                    for group_id in groups_ids
                    if group_id not in update_data["groups"]
                ]

                groups_to_add = [
                    group for group in update_data["groups"] if group not in groups_ids
                ]
                # remove
                for group in groups_to_remove:
                    self.logger.info("Leaving group")
                    resp = self.keycloak_admin.connection.raw_delete(
                        f"{self.admin_url_without_client}/users/{user_id}/groups/{group}"
                    )
                    resp.raise_for_status()
                    self.logger.info("Left group")
                # add
                for group in groups_to_add:
                    self.logger.info("Joining group")
                    self.add_user_to_group(user_id=user_id, group=group)
                    self.logger.info("Joined group")
            return {"status": "success", "message": "User updated successfully"}
        except KeycloakPostError as e:
            self.logger.error("Failed to update user in Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to update user")

    def delete_user(self, user_email: str) -> dict:
        try:
            user_id = self.get_user_id_by_email(user_email)
            self.keycloak_admin.delete_user(user_id)
            # delete the policy for the user (if not implicitly deleted?)
            return {"status": "success", "message": "User deleted successfully"}
        except KeycloakDeleteError as e:
            self.logger.error("Failed to delete user from Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to delete user")

    def get_auth_verifier(self, scopes: list) -> AuthVerifierBase:
        return KeycloakAuthVerifier(scopes)

    def create_resource(self, resource_name: str, scopes: list[str] = []) -> None:
        resource = {
            "name": resource_name,
            "displayName": f"Resource for {resource_name}",
            "type": "urn:keep:resources:" + resource_name,
            "scopes": [{"name": scope} for scope in scopes],
        }
        try:
            self.keycloak_admin.create_client_authz_resource(self.client_id, resource)
        except KeycloakPostError as e:
            if "already exists" in str(e):
                self.logger.info("Resource already exists in Keycloak")
                pass
            else:
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
                member_names = [member.get("email", "") for member in members]
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

    def create_user_policy(self, perm, permission: ResourcePermission) -> None:
        # we need the user id from email:
        # TODO: this is not efficient, we should cache this
        users = self.keycloak_admin.get_users({})
        user = next(
            (user for user in users if user["email"] == perm.id),
            None,
        )
        if not user:
            raise HTTPException(status_code=400, detail="User not found")
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
                return None
        policy_id = resp.json().get("id")
        return policy_id

    def create_group_policy(self, perm, permission: ResourcePermission) -> None:
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
                    "groups": [{"id": perm.id, "extendChildren": False}],
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
            # just continue to next policy
            else:
                return None
        policy_id = resp.json().get("id")
        return policy_id

    def create_permissions(self, permissions: list[ResourcePermission]) -> None:
        # create or update
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
                            policy_id = self.create_user_policy(perm, permission)
                            if policy_id:
                                policies.append(policy_id)
                            else:
                                self.logger.info("Policy already exists in Keycloak")
                        else:
                            policy_id = self.create_group_policy(perm, permission)
                            if policy_id:
                                policies.append(policy_id)
                            else:
                                self.logger.info("Policy already exists in Keycloak")

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
                        existing_permissions["policies"] = []
                    else:
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
                    try:
                        details = json.loads(policy["description"])
                    # with Keep convention, the description should be a json
                    except json.JSONDecodeError:
                        self.logger.warning(
                            "Failed to parse policy description: %s",
                            policy["description"],
                        )
                        continue
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
        # there is two ways to do this:
        # 1. admin api
        # 2. token endpoint directly
        # we will use the admin api and put (2) on TODO
        # https://keycloak.discourse.group/t/keyycloak-authz-policy-evaluation-using-rest-api/798/2
        # https://keycloak.discourse.group/t/how-can-i-evaluate-user-permission-over-rest-api/10619

        # also, we should see how it scale with many resources
        try:
            user_id = self.keycloak_admin.get_user_id(authenticated_entity.email)
            resp = self.keycloak_admin.connection.raw_post(
                f"{self.admin_url}/authz/resource-server/policy/evaluate",
                data=json.dumps(
                    {
                        "userId": user_id,
                        "resources": [
                            {
                                "type": resource_type,
                            }
                        ],
                        "context": {"attributes": {}},
                        "clientId": self.client_id,
                    }
                ),
            )
            results = resp.json()
            results = results.get("results", [])
            allowed_resources_ids = [
                result["resource"]["name"]
                for result in results
                if result["status"] == "PERMIT"
            ]
            return allowed_resources_ids
        except Exception as e:
            self.logger.error(
                "Failed to fetch user permissions from Keycloak: %s", str(e)
            )
            raise HTTPException(
                status_code=500, detail="Failed to fetch user permissions"
            )

    def get_policies(self) -> list[dict]:
        try:
            policies = self.keycloak_admin.connection.raw_get(
                f"{self.admin_url}/authz/resource-server/policy"
            ).json()
            return policies
        except KeycloakGetError as e:
            self.logger.error("Failed to fetch policies from Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to fetch policies")

    def get_roles(self) -> list[Role]:
        """
        Get roles in the identity manager for authorization purposes.

        This method is used to retrieve the roles that have been defined
        in the identity manager. It returns a list of role objects, each
        containing the resource, scope, and user or group information.

        # TODO: Still to review if this is the correct way to fetch roles
        """
        try:
            roles = self.keycloak_admin.get_client_roles(
                self.client_id, brief_representation=False
            )
            # filter out the uma role
            roles = [role for role in roles if role["name"] != "uma_protection"]
            roles_dto = {
                role.get("id"): Role(
                    id=role.get("id"),
                    name=role["name"],
                    description=role["description"],
                    scopes=set([]),  # will populate this later
                    predefined=(
                        True
                        if role.get("attributes", {}).get("predefined", ["false"])[0]
                        == "true"
                        else False
                    ),
                )
                for role in roles
            }
            # now for each role we need to get the scopes
            policies = self.keycloak_admin.get_client_authz_policies(self.client_id)
            roles_related_policies = [
                policy
                for policy in policies
                if policy.get("config", {}).get("roles", [])
            ]
            for policy in roles_related_policies:
                role_id = json.loads(policy["config"]["roles"])[0].get("id")
                policy_id = policy["id"]
                # get dependent permissions
                dependentPolicies = self.keycloak_admin.connection.raw_get(
                    f"{self.admin_url}/authz/resource-server/policy/{policy_id}/dependentPolicies",
                ).json()
                dependentPoliciesId = dependentPolicies[0].get("id")
                scopes = self.keycloak_admin.connection.raw_get(
                    f"{self.admin_url}/authz/resource-server/policy/{dependentPoliciesId}/scopes",
                ).json()
                scope_names = [scope["name"] for scope in scopes]
                # happens only when delete role fails from some resaon
                if role_id not in roles_dto:
                    self.logger.warning("Role not found for policy, skipping")
                    continue
                roles_dto[role_id].scopes.update(scope_names)
            return list(roles_dto.values())
        except KeycloakGetError as e:
            self.logger.error("Failed to fetch roles from Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to fetch roles")

    def delete_role(self, role_id: str) -> None:
        try:
            # delete the role
            resp = self.keycloak_admin.connection.raw_delete(
                f"{self.admin_url_without_client}/roles-by-id/{role_id}",
            )
            resp.raise_for_status()
            # delete the policy
            policies = self.get_policies()
            for policy in policies:
                roles = json.loads(policy.get("config", {}).get("roles", "{}"))
                if roles and roles[0].get("id") == role_id:
                    policy_id = policy.get("id")
                    break

            if not policy_id:
                self.logger.warning("Policy not found for role deletion, skipping")
            else:
                self.logger.info("Deleteing policy id")
                self.keycloak_admin.delete_client_authz_policy(
                    self.client_id, policy_id
                )
                self.logger.info("Policy id deleted")
            # permissions gets deleted impliclty when we delete the policy
        except KeycloakDeleteError as e:
            self.logger.error("Failed to delete role from Keycloak: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to delete role")
