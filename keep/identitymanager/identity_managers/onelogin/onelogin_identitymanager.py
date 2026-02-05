import os


from keep.api.models.user import Group, Role, User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.identity_managers.onelogin.onelogin_authverifier import OneLoginAuthVerifier
from keep.identitymanager.identitymanager import BaseIdentityManager


class OneLoginIdentityManager(BaseIdentityManager):
    """
    Identity manager implementation for OneLogin SSO.
    Only handles SSO authentication - all user management is disabled.
    """

    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)

        self.logger.info("OneLoginIdentityManager initialized")

        self.onelogin_issuer = os.environ.get("ONELOGIN_ISSUER")
        self.onelogin_client_id = os.environ.get("ONELOGIN_CLIENT_ID")
        self.onelogin_client_secret = os.environ.get("ONELOGIN_CLIENT_SECRET")

        # Only require the essential variables for SSO
        if not all([self.onelogin_issuer, self.onelogin_client_id, self.onelogin_client_secret]):
            missing_vars = []
            if not self.onelogin_issuer:
                missing_vars.append("ONELOGIN_ISSUER")
            if not self.onelogin_client_id:
                missing_vars.append("ONELOGIN_CLIENT_ID")
            if not self.onelogin_client_secret:
                missing_vars.append("ONELOGIN_CLIENT_SECRET")

            self.logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
            raise Exception(f"Missing environment variables: {', '.join(missing_vars)}")

        # Remove any trailing slash from issuer
        if self.onelogin_issuer.endswith("/"):
            self.onelogin_issuer = self.onelogin_issuer[:-1]

        self.logger.info("OneLogin Identity Manager initialized for SSO authentication only")

    def on_start(self, app) -> None:
        """
        Initialize the identity manager on application startup.
        No-op for SSO-only implementation.
        """
        self.logger.info("OneLogin Identity Manager started (SSO authentication only)")

    @property
    def support_sso(self) -> bool:
        """Indicate that OneLogin supports SSO"""
        return True

    def get_sso_providers(self) -> list[str]:
        """Get the list of SSO providers"""
        return ["onelogin"]

    def get_sso_wizard_url(self, authenticated_entity: AuthenticatedEntity) -> str:
        """Get the URL for the SSO wizard - redirect to OneLogin login"""
        return f"{self.onelogin_issuer}/auth"

    def get_users(self) -> list[User]:
        """Get all users from OneLogin - disabled"""
        self.logger.info("get_users called but management functions are disabled")
        return []

    def create_user(self, user_email: str, user_name: str, password: str, role: str, groups: list[str] = []) -> dict:
        """Create a new user in OneLogin - disabled"""
        self.logger.info("create_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}

    def update_user(self, user_email: str, update_data: dict) -> dict:
        """Update an existing user in OneLogin - disabled"""
        self.logger.info("update_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}

    def delete_user(self, user_email: str) -> dict:
        """Delete a user from OneLogin - disabled"""
        self.logger.info("delete_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}

    def get_auth_verifier(self, scopes: list) -> AuthVerifierBase:
        """Get the auth verifier for OneLogin - this still works"""
        return OneLoginAuthVerifier(scopes)

    def get_groups(self) -> list[Group]:
        """Get all groups from OneLogin - disabled"""
        self.logger.info("get_groups called but management functions are disabled")
        return []

    def create_group(self, group_name: str, members: list[str], roles: list[str]) -> None:
        """Create a new group in OneLogin - disabled"""
        self.logger.info("create_group called but management functions are disabled")
        return None

    def update_group(self, group_name: str, members: list[str], roles: list[str]) -> None:
        """Update an existing group in OneLogin - disabled"""
        self.logger.info("update_group called but management functions are disabled")
        return None

    def delete_group(self, group_name: str) -> None:
        """Delete a group from OneLogin - disabled"""
        self.logger.info("delete_group called but management functions are disabled")
        return None

    def create_role(self, role: Role, predefined=False) -> str:
        """Create a role in OneLogin - disabled"""
        self.logger.info("create_role called but management functions are disabled")
        return ""

    def get_roles(self) -> list[Role]:
        """Get all roles from OneLogin - disabled"""
        self.logger.info("get_roles called but management functions are disabled")
        return []

    def delete_role(self, role_id: str) -> None:
        """Delete a role from OneLogin - disabled"""
        self.logger.info("delete_role called but management functions are disabled")
        return None
