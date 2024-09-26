from typing import Optional

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from keep.api.core.config import config
from keep.api.core.db import create_user, user_exists
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.rbac import get_role_by_role_name


class Oauth2proxyAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for single tenant mode"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.oauth2_proxy_user_header = config(
            "KEEP_OAUTH2_PROXY_USER_HEADER", default="x-forwarded-email"
        )
        self.oauth2_proxy_role_header = config(
            "KEEP_OAUTH2_PROXY_ROLE_HEADER", default="x-forwarded-groups"
        )
        self.auto_create_user = config(
            "KEEP_OAUTH2_PROXY_AUTO_CREATE_USER", default=True
        )
        self.role_mappings = {
            config("KEEP_OAUTH2_PROXY_ADMIN_ROLE", default=""): "admin",
            config("KEEP_OAUTH2_PROXY_NOC_ROLE", default=""): "noc",
            config("KEEP_OAUTH2_PROXY_WEBHOOK_ROLE", default=""): "webhook",
        }
        self.logger.info("Oauth2proxy Auth Verifier initialized")

    def authenticate(
        self,
        request: Request,
        api_key: str,
        authorization: Optional[HTTPAuthorizationCredentials],
        token: Optional[str],
    ) -> AuthenticatedEntity:

        # https://github.com/keephq/keep/issues/1203
        # get user name
        self.logger.info(
            f"Authenticating user with {self.oauth2_proxy_user_header} header"
        )
        user_name = request.headers.get(self.oauth2_proxy_user_header)

        if not user_name:
            raise HTTPException(
                status_code=401,
                detail=f"Unauthorized - no user in {self.oauth2_proxy_user_header} header found",
            )

        role = request.headers.get(self.oauth2_proxy_role_header)
        if not role:
            raise HTTPException(
                status_code=401,
                detail=f"Unauthorized - no role in {self.oauth2_proxy_role_header} header found",
            )

        # else, if its a list seperated by comma e.g. org:admin, org:foobar or role:admin, role:foobar
        if "," in role:
            # split the roles by comma
            roles = role.split(",")
            # trim
            roles = [r.strip() for r in roles]
        else:
            roles = [role]

        mapped_role = None
        for role in roles:
            # map the role if its a mapped one, or just use the role
            mapped_role = self.role_mappings.get(role, role)
            # will throw 403 exception if role is not found
            try:
                mapped_role = get_role_by_role_name(mapped_role)
                break
            # lets check the next role
            except HTTPException:
                continue

        # if the role is still a string, it means it was not found in get_role_by_role_name
        # so we throw a 403 exception
        if isinstance(mapped_role, str):
            raise HTTPException(
                status_code=403,
                detail=f"Role {roles} not found",
            )

        # auto provision user
        if self.auto_create_user and not user_exists(
            tenant_id=SINGLE_TENANT_UUID, username=user_name
        ):
            self.logger.info(f"Auto provisioning user: {user_name}")
            create_user(
                tenant_id=SINGLE_TENANT_UUID,
                username=user_name,
                role=mapped_role.get_name(),
                password="",
            )
            self.logger.info(f"User {user_name} created")

        self.logger.info(f"User {user_name} authenticated with role {mapped_role}")
        return AuthenticatedEntity(
            tenant_id=SINGLE_TENANT_UUID,
            email=user_name,
            role=mapped_role.get_name(),
        )
