import logging
import os


from keep.api.models.user import Group, Role, User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.identity_managers.okta.okta_authverifier import OktaAuthVerifier
from keep.identitymanager.identitymanager import BaseIdentityManager

logger = logging.getLogger(__name__)


class OktaIdentityManager(BaseIdentityManager):
    """
    Identity manager implementation for Okta.
    Authentication works but management functions are disabled.
    """

    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        self.okta_domain = os.environ.get("OKTA_DOMAIN")
        self.okta_issuer = os.environ.get("OKTA_ISSUER")
        self.okta_client_id = os.environ.get("OKTA_CLIENT_ID")
        self.okta_client_secret = os.environ.get("OKTA_CLIENT_SECRET")
        
        # API token is not required for basic authentication
        self.okta_api_token = os.environ.get("OKTA_API_TOKEN")
        
        if not all([self.okta_domain, self.okta_issuer, self.okta_client_id, self.okta_client_secret]):
            missing_vars = []
            if not self.okta_domain:
                missing_vars.append("OKTA_DOMAIN")
            if not self.okta_issuer:
                missing_vars.append("OKTA_ISSUER")
            if not self.okta_client_id:
                missing_vars.append("OKTA_CLIENT_ID")
            if not self.okta_client_secret:
                missing_vars.append("OKTA_CLIENT_SECRET")
            
            self.logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
            raise Exception(f"Missing environment variables: {', '.join(missing_vars)}")
        
        # Remove any trailing slash from issuer
        if self.okta_issuer.endswith("/"):
            self.okta_issuer = self.okta_issuer[:-1]
            
        self.logger.info("Okta Identity Manager initialized (management functions disabled)")
    
    def on_start(self, app) -> None:
        """
        Initialize the identity manager on application startup.
        No-op for this minimal implementation.
        """
        self.logger.info("Okta Identity Manager started (roles creation disabled)")
    
    @property
    def support_sso(self) -> bool:
        """Indicate that Okta supports SSO"""
        return True
    
    def get_sso_providers(self) -> list[str]:
        """Get the list of SSO providers"""
        return ["okta"]
    
    def get_sso_wizard_url(self, authenticated_entity: AuthenticatedEntity) -> str:
        """Get the URL for the SSO wizard"""
        tenant_id = authenticated_entity.tenant_id
        return f"{self.okta_issuer}/sso/{tenant_id}"
    
    def get_users(self) -> list[User]:
        """Get all users from Okta - disabled"""
        self.logger.info("get_users called but management functions are disabled")
        return []

    def create_user(self, user_email: str, user_name: str, password: str, role: str, groups: list[str] = []) -> dict:
        """Create a new user in Okta - disabled"""
        self.logger.info("create_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}

    def update_user(self, user_email: str, update_data: dict) -> dict:
        """Update an existing user in Okta - disabled"""
        self.logger.info("update_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}
    
    def delete_user(self, user_email: str) -> dict:
        """Delete a user from Okta - disabled"""
        self.logger.info("delete_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}
    
    def get_auth_verifier(self, scopes: list) -> AuthVerifierBase:
        """Get the auth verifier for Okta - this still works"""
        return OktaAuthVerifier(scopes)
    
    def get_groups(self) -> list[Group]:
        """Get all groups from Okta - disabled"""
        self.logger.info("get_groups called but management functions are disabled")
        return []
    
    def create_group(self, group_name: str, members: list[str], roles: list[str]) -> None:
        """Create a new group in Okta - disabled"""
        self.logger.info("create_group called but management functions are disabled")
        return None
    
    def update_group(self, group_name: str, members: list[str], roles: list[str]) -> None:
        """Update an existing group in Okta - disabled"""
        self.logger.info("update_group called but management functions are disabled")
        return None
    
    def delete_group(self, group_name: str) -> None:
        """Delete a group from Okta - disabled"""
        self.logger.info("delete_group called but management functions are disabled")
        return None
    
    def create_role(self, role: Role, predefined=False) -> str:
        """Create a role in Okta - disabled"""
        self.logger.info("create_role called but management functions are disabled")
        return ""
    
    def get_roles(self) -> list[Role]:
        """Get all roles from Okta - disabled"""
        self.logger.info("get_roles called but management functions are disabled")
        return []
    
    def delete_role(self, role_id: str) -> None:
        """Delete a role from Okta - disabled"""
        self.logger.info("delete_role called but management functions are disabled")
        return None 