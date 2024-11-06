import os
import secrets

from azure.graphrbac import GraphRbacManagementClient
from azure.graphrbac.models import PasswordProfile, UserCreateParameters
from azure.identity import ClientSecretCredential
from fastapi import HTTPException

from ee.identitymanager.identity_managers.azuread.azuread_authverifier import (
    AzureadAuthVerifier,
)
from keep.api.models.user import User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.identitymanager import BaseIdentityManager


class AzureadIdentityManager(BaseIdentityManager):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        self.logger.info("AzureadIdentityManager initialized")

        # Initialize Azure credentials
        self.credentials = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=os.getenv("AZURE_CLIENT_ID"),
            client_secret=os.getenv("AZURE_CLIENT_SECRET"),
        )

        # Initialize Graph client
        self.graph_client = GraphRbacManagementClient(self.credentials, tenant_id)

    def get_users(self) -> list[User]:
        users = []
        for user in self.graph_client.users.list():
            users.append(
                User(
                    email=user.mail,
                    role=user.job_title or "user",
                    name=user.display_name,
                )
            )
        return users

    def create_user(self, user_email: str, role: str, **kwargs) -> dict:
        password = secrets.token_urlsafe(32)

        user_params = UserCreateParameters(
            user_principal_name=user_email,
            account_enabled=True,
            display_name=kwargs.get("name", user_email),
            mail_nickname=user_email.split("@")[0],
            password_profile=PasswordProfile(
                password=password, force_change_password_next_login=True
            ),
            job_title=role,
        )

        user = self.graph_client.users.create(user_params)

        return {"email": user.mail, "role": role, "temporary_password": password}

    def delete_user(self, user_email: str) -> dict:
        # Find user by email
        users = list(self.graph_client.users.list(filter=f"mail eq '{user_email}'"))

        if not users:
            raise HTTPException(status_code=404, detail="User not found")

        user = users[0]
        self.graph_client.users.delete(user.object_id)

        return {"status": "success", "message": f"User {user_email} deleted"}

    def get_auth_verifier(self, scopes) -> AzureadAuthVerifier:
        return AzureadAuthVerifier(scopes)

    def _create_user_auth0(self, user_email: str, tenant_id: str, role: str) -> dict:
        # This method is not needed for Azure AD implementation
        raise NotImplementedError("This method is specific to Auth0")

    def update_user(self, user_email: str, update_data: dict) -> User:
        # Find user by email
        users = list(self.graph_client.users.list(filter=f"mail eq '{user_email}'"))

        if not users:
            raise HTTPException(status_code=404, detail="User not found")

        user = users[0]

        # Update allowed fields
        update_params = {}
        if "name" in update_data:
            update_params["display_name"] = update_data["name"]
        if "role" in update_data:
            update_params["job_title"] = update_data["role"]

        if update_params:
            self.graph_client.users.update(user.object_id, update_params)

        return User(
            email=user_email,
            role=update_data.get("role", user.job_title),
            name=update_data.get("name", user.display_name),
        )
