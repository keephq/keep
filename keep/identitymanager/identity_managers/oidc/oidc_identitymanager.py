import os

from keep.api.models.user import Group, Role, User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.identity_managers.oidc.oidc_authverifier import (
    OidcAuthVerifier,
)
from keep.identitymanager.identitymanager import BaseIdentityManager


class OidcIdentityManager(BaseIdentityManager):
    """
    Identity manager implementation for a generic OpenID Connect provider
    (Dex, Authentik, Zitadel, Authelia, Kanidm, Keycloak, ...).
    Only handles SSO authentication - all user management is disabled.
    """

    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)

        self.logger.info("OidcIdentityManager initialized")

        self.oidc_issuer = os.environ.get("KEEP_OIDC_ISSUER")
        self.oidc_client_id = os.environ.get("KEEP_OIDC_CLIENT_ID")

        # Only require the essential variables for SSO verification.
        # The client secret is only needed by keep-ui (NextAuth), never by the backend.
        if not all([self.oidc_issuer, self.oidc_client_id]):
            missing_vars = []
            if not self.oidc_issuer:
                missing_vars.append("KEEP_OIDC_ISSUER")
            if not self.oidc_client_id:
                missing_vars.append("KEEP_OIDC_CLIENT_ID")

            self.logger.error(
                f"Missing environment variables: {', '.join(missing_vars)}"
            )
            raise Exception(f"Missing environment variables: {', '.join(missing_vars)}")

        # Remove any trailing slash from issuer
        if self.oidc_issuer.endswith("/"):
            self.oidc_issuer = self.oidc_issuer[:-1]

        self.logger.info(
            "OIDC Identity Manager initialized for SSO authentication only"
        )

    def on_start(self, app) -> None:
        """
        Initialize the identity manager on application startup.
        No-op for SSO-only implementation.
        """
        self.logger.info("OIDC Identity Manager started (SSO authentication only)")

    @property
    def support_sso(self) -> bool:
        """Indicate that OIDC supports SSO"""
        return True

    def get_sso_providers(self) -> list[str]:
        """Get the list of SSO providers"""
        return ["oidc"]

    def get_sso_wizard_url(self, authenticated_entity: AuthenticatedEntity) -> str:
        """Get the URL for the SSO wizard - redirect to the OIDC issuer"""
        return self.oidc_issuer

    def get_users(self) -> list[User]:
        """Get all users from the OIDC provider - disabled"""
        self.logger.info("get_users called but management functions are disabled")
        return []

    def create_user(
        self,
        user_email: str,
        user_name: str,
        password: str,
        role: str,
        groups: list[str] = [],
    ) -> dict:
        """Create a new user in the OIDC provider - disabled"""
        self.logger.info("create_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}

    def update_user(self, user_email: str, update_data: dict) -> dict:
        """Update an existing user in the OIDC provider - disabled"""
        self.logger.info("update_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}

    def delete_user(self, user_email: str) -> dict:
        """Delete a user from the OIDC provider - disabled"""
        self.logger.info("delete_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}

    def get_auth_verifier(self, scopes: list) -> AuthVerifierBase:
        """Get the auth verifier for OIDC - this still works"""
        return OidcAuthVerifier(scopes)

    def get_groups(self) -> list[Group]:
        """Get all groups from the OIDC provider - disabled"""
        self.logger.info("get_groups called but management functions are disabled")
        return []

    def create_group(
        self, group_name: str, members: list[str], roles: list[str]
    ) -> None:
        """Create a new group in the OIDC provider - disabled"""
        self.logger.info("create_group called but management functions are disabled")
        return None

    def update_group(
        self, group_name: str, members: list[str], roles: list[str]
    ) -> None:
        """Update a group in the OIDC provider - disabled"""
        self.logger.info("update_group called but management functions are disabled")
        return None

    def delete_group(self, group_name: str) -> None:
        """Delete a group from the OIDC provider - disabled"""
        self.logger.info("delete_group called but management functions are disabled")
        return None

    def create_role(self, role: Role, predefined=False) -> str:
        """Create a role in the OIDC provider - disabled"""
        self.logger.info("create_role called but management functions are disabled")
        return ""

    def get_roles(self) -> list[Role]:
        """Get all roles from the OIDC provider - disabled"""
        self.logger.info("get_roles called but management functions are disabled")
        return []

    def delete_role(self, role_id: str) -> None:
        """Delete a role from the OIDC provider - disabled"""
        self.logger.info("delete_role called but management functions are disabled")
        return None
