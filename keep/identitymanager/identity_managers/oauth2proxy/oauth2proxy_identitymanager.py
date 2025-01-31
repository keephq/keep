from keep.api.core.db import get_users as get_users_from_db
from keep.api.models.user import User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.identity_managers.oauth2proxy.oauth2proxy_authverifier import (
    Oauth2proxyAuthVerifier,
)
from keep.identitymanager.identitymanager import BaseIdentityManager


class Oauth2proxyIdentityManager(BaseIdentityManager):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        self.logger.info("Oauth2 proxy Identity Manager initialized")

    def get_users(self) -> list[User]:
        users = get_users_from_db()
        users = [
            User(
                email=f"{user.username}",
                name=user.username,
                role=user.role,
                last_login=str(user.last_sign_in) if user.last_sign_in else None,
                created_at=str(user.created_at),
            )
            for user in users
        ]
        return users

    def get_auth_verifier(self, scopes) -> Oauth2proxyAuthVerifier:
        return Oauth2proxyAuthVerifier(scopes)

    # Not implemented
    def create_user(self, **kawrgs) -> User:
        return None

    # Not implemented
    def delete_user(self, **kwargs) -> User:
        return None
