from typing import Optional

from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from keep.api.core.dependencies import SINGLE_TENANT_EMAIL, SINGLE_TENANT_UUID
from keep.api.core.rbac import Admin as AdminRole
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase


class NoAuthverifier(AuthVerifierBase):
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
        return AuthenticatedEntity(
            tenant_id=SINGLE_TENANT_UUID,
            email=SINGLE_TENANT_EMAIL,
            role=AdminRole.get_name(),
        )
