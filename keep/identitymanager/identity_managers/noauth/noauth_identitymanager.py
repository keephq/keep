from keep.api.models.user import User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.identity_managers.noauth.noauth_authverifier import (
    NoAuthVerifier,
)
from keep.identitymanager.identitymanager import BaseIdentityManager


class NoAuthIdentityManager(BaseIdentityManager):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        self.logger.info("DB Identity Manager initialized")

    def get_users(self) -> list[User]:
        return []

    def create_user(self, user_email, user_name, password, role, groups=[]) -> None:
        return

    def delete_user(self, user_email: str) -> dict:
        return {}

    def get_auth_verifier(self, scopes) -> AuthVerifierBase:
        return NoAuthVerifier(scopes)
