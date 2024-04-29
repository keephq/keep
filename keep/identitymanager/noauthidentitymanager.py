from fastapi import Depends

from keep.api.core.dependencies import SINGLE_TENANT_EMAIL, SINGLE_TENANT_UUID
from keep.api.core.rbac import Admin as AdminRole
from keep.api.models.user import User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme
from keep.identitymanager.identitymanager import BaseIdentityManager


class NoAuthIdentityManager(BaseIdentityManager):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        self.logger.info("DB Identity Manager initialized")

    def get_users() -> list[User]:
        return []

    def create_user(self, secret_name: str, secret_value: str) -> None:
        return

    def delete_user(user_email: str) -> dict:
        return

    def get_auth_verifier(self, scopes) -> AuthVerifierBase:
        return NoAuthVerifier(scopes)


class NoAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for single tenant mode"""

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        return AuthenticatedEntity(
            tenant_id=SINGLE_TENANT_UUID,
            email=SINGLE_TENANT_EMAIL,
            api_key_name=None,
            role=AdminRole.get_name(),
        )

    def _verify_api_key(self, api_key: str) -> AuthenticatedEntity:
        return AuthenticatedEntity(
            tenant_id=SINGLE_TENANT_UUID,
            email=SINGLE_TENANT_EMAIL,
            api_key_name="single_tenant_api_key",  # just a placeholder
            role=AdminRole.get_name(),
        )
