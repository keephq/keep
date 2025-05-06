import logging
import os

from fastapi import Depends, HTTPException

from keep.api.core.config import config
from keep.api.core.db import create_tenant, get_tenants
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme
from keep.identitymanager.rbac import Roles
from keycloak import KeycloakOpenID, KeycloakOpenIDConnection
from keycloak.connection import ConnectionManager
from keycloak.keycloak_uma import KeycloakUMA
from keycloak.uma_permissions import UMAPermission

logger = logging.getLogger(__name__)


# PATCH TO MONKEYPATCH KEYCLOAK VERIFY BUG
# https://github.com/marcospereirampj/python-keycloak/issues/645

original_init = ConnectionManager.__init__


def patched_init(
    self,
    base_url: str,
    headers: dict = None,
    timeout: int = 60,
    verify: bool = None,
    proxies: dict = None,
):
    if verify is None:
        verify = os.environ.get("KEYCLOAK_VERIFY_CERT", "true").lower() == "true"
        logger.warning(
            "Using KEYCLOAK_VERIFY_CERT environment variable to set verify. ",
            extra={"KEYCLOAK_VERIFY_CERT": verify},
        )

    if headers is None:
        headers = {}
    original_init(self, base_url, headers, timeout, verify, proxies)


ConnectionManager.__init__ = patched_init


class KeycloakAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for Keycloak"""

    def __init__(self, scopes: list[str] = []) -> None:
        super().__init__(scopes)
        self.keycloak_url = os.environ.get("KEYCLOAK_URL")
        self.keycloak_realm = os.environ.get("KEYCLOAK_REALM")
        self.keycloak_client_id = os.environ.get("KEYCLOAK_CLIENT_ID")
        self.keycloak_audience = os.environ.get("KEYCLOAK_AUDIENCE")
        self.keycloak_verify_cert = (
            os.environ.get("KEYCLOAK_VERIFY_CERT", "true").lower() == "true"
        )
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
            verify=self.keycloak_verify_cert,
        )
        self.keycloak_openid_connection = KeycloakOpenIDConnection(
            server_url=self.keycloak_url,
            realm_name=self.keycloak_realm,
            client_id=self.keycloak_client_id,
            client_secret_key=os.environ.get("KEYCLOAK_CLIENT_SECRET"),
            verify=self.keycloak_verify_cert,
        )
        self.keycloak_uma = KeycloakUMA(connection=self.keycloak_openid_connection)
        # will be populated in on_start of the identity manager
        self.protected_resource = None
        self.roles_from_groups = config(
            "KEYCLOAK_ROLES_FROM_GROUPS", default=False, cast=bool
        )
        self.groups_claims = config("KEYCLOAK_GROUPS_CLAIM", default="groups")
        self.groups_claims_admin = config(
            "KEYCLOAK_GROUPS_CLAIM_ADMIN", default="admin"
        )
        self.groups_claims_noc = config("KEYCLOAK_GROUPS_CLAIM_NOC", default="noc")
        self.groups_claims_webhook = config(
            "KEYCLOAK_GROUPS_CLAIM_WEBHOOK", default="webhook"
        )
        self.groups_org_prefix = config(
            "KEYCLOAK_GROUPS_ORG_PREFIX", default="keep"
        ).lower()
        self.keycloak_roles = {
            self.groups_claims_admin: Roles.ADMIN,
            self.groups_claims_noc: Roles.NOC,
            self.groups_claims_webhook: Roles.WEBHOOK,
        }
        if self.roles_from_groups:
            self.keycloak_multi_org = True
        else:
            self.keycloak_multi_org = False

        self._tenants = []

    @property
    def tenants(self):
        if not self._tenants:
            tenants = get_tenants()
            self._tenants = {
                tenant.name: {
                    "tenant_id": tenant.id,
                    "tenant_logo_url": tenant.configuration.get("logo_url"),
                }
                for tenant in tenants
            }

        return self._tenants

    def get_org_name_by_tenant_id(self, tenant_id):
        for org_name, org_tenant_id in self.tenants.items():
            if org_tenant_id.get("tenant_id") == tenant_id:
                return org_name

        self.logger.error("Tenant id not found", extra={"tenant_id": tenant_id})
        raise Exception("Org not found")

    def _check_if_group_represents_org(self, group_name: str):
        # if must start with the group prefix
        if not group_name.startswith(
            self.groups_org_prefix
        ) and not group_name.startswith("/" + self.groups_org_prefix):
            return False

        # TODO: dynamic roles + orgs

        # admin
        if self.groups_claims_admin in group_name:
            return True

        # noc
        if self.groups_claims_noc in group_name:
            return True

        # webhook
        if self.groups_claims_webhook in group_name:
            return True

        # if not, its not a group that represents an org
        return False

    def _get_org_name(self, group_name):
        # first, keycloak groups starts with "/"
        if group_name.startswith("/"):
            group_name = group_name[1:]

        # second, trim the role
        org_name = "-".join(group_name.split("-")[0:-1])

        return org_name

    def _get_role_in_org(self, user_groups, org_name):
        # for the org_name (e.g. keep-org-a) iterate over the groups and find the role
        # e.g. /org-a-admin, /org-a-noc, /org-a-webhook
        # we want to iterate from the "strongest" to the "weakest" role
        for role, keep_role in self.keycloak_roles.items():
            for group in user_groups:
                group_lower = group.lower()
                if org_name in group_lower and role in group_lower:
                    return keep_role.value
        return None

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        # verify keycloak token
        try:
            # more than one tenant support
            if token.startswith("keepActiveTenant"):
                active_tenant, token = token.split("&")
                active_tenant = active_tenant.split("=")[1]
            else:
                active_tenant = None
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

        # this allows more than one tenant to be configured in the same keycloak realm
        # todo: support dynamic roles
        user_orgs = {}
        if self.roles_from_groups:
            self.logger.info("Using roles from groups")
            # get roles from groups
            # e.g.
            # "group-keeps": [
            # "/ORG-A-USERS",
            # "/ORG-B-USERS",
            # "/org-users"
            # ],
            groups = payload.get(self.groups_claims, [])
            groups_that_represent_orgs = []
            # first, create tenants if they are not exists (should be happen once, new group)
            for group in groups:
                # first, check if its an org group (e.g. keep-org-a)
                group_lower = group.lower()
                if self._check_if_group_represents_org(group_name=group_lower):
                    # check if its the configuration
                    org_name = self._get_org_name(group_lower)
                    groups_that_represent_orgs.append(group_lower)
                    if org_name not in self.tenants:
                        self.logger.info("Creating tenant")
                        org_tenant_id = create_tenant(tenant_name=org_name)
                        # so it won't be
                        self.tenants[org_name] = {
                            "tenant_id": org_tenant_id,
                            "tenant_logo_url": None,
                        }
                        self.logger.info("Tenant created")
                    # this will be returned to the UI
                    user_orgs[org_name] = self.tenants.get(org_name)

            # TODO: fix
            if active_tenant:
                # get the active_tenant grou
                org_name = self.get_org_name_by_tenant_id(active_tenant)
                tenant_id = active_tenant
                role = self._get_role_in_org(groups, org_name)
                if not role:
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid Keycloak token - could not find any group that represents the org and the role",
                    )
            # if no active tenant, we take the first
            else:
                current_tenant_group = groups_that_represent_orgs[0]
                org_name = self._get_org_name(current_tenant_group)
                tenant_id = self.tenants.get(org_name).get("tenant_id")
                if self.groups_claims_admin in current_tenant_group:
                    role = "admin"
                elif self.groups_claims_noc in current_tenant_group:
                    role = "noc"
                elif self.groups_claims_webhook in current_tenant_group:
                    role = "webhook"
                else:
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid Keycloak token - no role in groups",
                    )
        # Keycloak single tenant
        else:
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

        # finally, check if the role is in the allowed roles
        authenticated_entity = AuthenticatedEntity(
            tenant_id,
            email,
            None,
            role,
            org_id=org_id,
            org_realm=org_realm,
            token=token,
        )
        if user_orgs:
            authenticated_entity.user_orgs = user_orgs

        return authenticated_entity

    def _authorize(self, authenticated_entity: AuthenticatedEntity) -> None:

        # multi org does not support UMA for now:
        if self.keycloak_multi_org:
            return super()._authorize(authenticated_entity)

        # for single tenant Keycloaks, use Keycloak's UMA to authorize
        try:
            permission = UMAPermission(
                resource=self.protected_resource,
                scope=self.scopes[0],  # todo: handle multiple scopes per resource
            )
            self.logger.info(f"Checking permission {permission}")
            allowed = self.keycloak_uma.permissions_check(
                token=authenticated_entity.token, permissions=[permission]
            )
            self.logger.info(f"Permission check result: {allowed}")
            if not allowed:
                raise HTTPException(status_code=403, detail="Permission check failed")
        # secure fallback
        except Exception as e:
            raise HTTPException(
                status_code=403, detail="Permission check failed - " + str(e)
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
