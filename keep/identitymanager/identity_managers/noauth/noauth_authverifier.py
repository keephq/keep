from typing import Optional

from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from keep.api.core.dependencies import SINGLE_TENANT_EMAIL, SINGLE_TENANT_UUID
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.rbac import Admin as AdminRole


class NoAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for single tenant mode"""

    def _verify_bearer_token(self, token: str) -> AuthenticatedEntity:
        return AuthenticatedEntity(
            tenant_id=SINGLE_TENANT_UUID,
            email=SINGLE_TENANT_EMAIL,
            role=AdminRole.get_name(),
        )

    def _verify_api_key(
        self,
        request: Request,
        api_key: str,
        authorization: Optional[HTTPAuthorizationCredentials],
    ) -> AuthenticatedEntity:
        """
        # https://github.com/keephq/keep/issues/1203
        if self.impersonation:
            # get user name
            user_name = request.headers.get(self.impersonation_user_header)
            role = request.headers.get(self.impersonation_role_header)

            # auto provision user
            if self.impersonation_auto_create_user and not user_exists(user_name):
                self.logger.info(f"Auto provisioning user: {user_name}")
                create_user(
                    tenant_id=SINGLE_TENANT_UUID, email=
                    user_name, role, password="") # password is not used in noauth
                self.logger.info(f"User {user_name} created")

            return AuthenticatedEntity(
                tenant_id=SINGLE_TENANT_UUID,
                email=user_name,
                role=role,
            )
        """

        return AuthenticatedEntity(
            tenant_id=SINGLE_TENANT_UUID,
            email=SINGLE_TENANT_EMAIL,
            role=AdminRole.get_name(),
        )
