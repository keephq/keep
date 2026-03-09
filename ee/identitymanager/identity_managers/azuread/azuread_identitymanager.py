import os

from ee.identitymanager.identity_managers.azuread.azuread_authverifier import (
    AzureadAuthVerifier,
)
from keep.api.core.db_on_start import try_create_single_tenant
from keep.api.models.user import User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.identity_managers.db.db_identitymanager import (
    DbIdentityManager,
)
from keep.identitymanager.identitymanager import BaseIdentityManager


class AzureadIdentityManager(BaseIdentityManager):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        self.db_identity_manager = DbIdentityManager(
            tenant_id, context_manager, **kwargs
        )

    def on_start(self, app) -> None:
        azuread_tenant_id = os.environ.get("KEEP_AZUREAD_TENANT_ID")
        if azuread_tenant_id:
            try_create_single_tenant(azuread_tenant_id, create_default_user=False)
        else:
            self.logger.warning(
                "AUTH_TYPE=azuread but KEEP_AZUREAD_TENANT_ID is not set"
            )

    def get_users(self) -> list[User]:
        # we keep the azuread users in the db
        return self.db_identity_manager.get_users(self.tenant_id)

    def create_user(self, user_email: str, role: str, **kwargs) -> dict:
        return None

    def delete_user(self, user_email: str) -> dict:
        raise NotImplementedError("AzureadIdentityManager.delete_user")

    def get_auth_verifier(self, scopes) -> AzureadAuthVerifier:
        return AzureadAuthVerifier(scopes)

    def update_user(self, user_email: str, update_data: dict) -> User:
        raise NotImplementedError("AzureadIdentityManager.update_user")
