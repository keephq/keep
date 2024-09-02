import os
import secrets

import jwt
from fastapi import HTTPException

from ee.identitymanager.identity_managers.auth0.auth0_authverifier import (
    Auth0AuthVerifier,
)
from ee.identitymanager.identity_managers.auth0.auth0_utils import getAuth0Client
from keep.api.models.user import User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.identitymanager import BaseIdentityManager
from keep.identitymanager.rbac import Admin as AdminRole


class Auth0IdentityManager(BaseIdentityManager):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        self.logger.info("Auth0IdentityManager initialized")
        self.domain = os.environ.get("AUTH0_DOMAIN")
        self.client_id = os.environ.get("AUTH0_CLIENT_ID")
        self.client_secret = os.environ.get("AUTH0_CLIENT_SECRET")
        self.audience = f"https://{self.domain}/api/v2/"
        self.jwks_client = jwt.PyJWKClient(
            f"https://{self.domain}/.well-known/jwks.json", cache_keys=True
        )

    def get_users(self) -> list[User]:
        return self._get_users_auth0(self.tenant_id)

    def _get_users_auth0(self, tenant_id: str) -> list[User]:
        auth0 = getAuth0Client()
        users = auth0.users.list(q=f'app_metadata.keep_tenant_id:"{tenant_id}"')
        users = [
            User(
                email=user["email"],
                name=user["name"],
                # for backwards compatibility we return admin if no role is set
                role=user.get("app_metadata", {}).get(
                    "keep_role", AdminRole.get_name()
                ),
                last_login=user.get("last_login", None),
                created_at=user["created_at"],
                picture=user["picture"],
            )
            for user in users.get("users", [])
        ]
        return users

    def create_user(self, user_email: str, role: str, **kwargs) -> dict:
        return self._create_user_auth0(user_email, self.tenant_id, role)

    def delete_user(self, user_email: str) -> dict:
        auth0 = getAuth0Client()
        users = auth0.users.list(q=f'app_metadata.keep_tenant_id:"{self.tenant_id}"')
        for user in users.get("users", []):
            if user["email"] == user_email:
                auth0.users.delete(user["user_id"])
                return {"status": "OK"}
        raise HTTPException(status_code=404, detail="User not found")

    def get_auth_verifier(self, scopes) -> Auth0AuthVerifier:
        return Auth0AuthVerifier(scopes)

    def _create_user_auth0(self, user_email: str, tenant_id: str, role: str) -> dict:
        auth0 = getAuth0Client()
        # User email can exist in 1 tenant only for now.
        users = auth0.users.list(q=f'email:"{user_email}"')
        if users.get("users", []):
            raise HTTPException(status_code=409, detail="User already exists")
        user = auth0.users.create(
            {
                "email": user_email,
                "password": secrets.token_urlsafe(13),
                "email_verified": True,
                "app_metadata": {"keep_tenant_id": tenant_id, "keep_role": role},
                "connection": os.environ.get("AUTH0_DB_NAME", "keep-users"),
            }
        )
        user_dto = User(
            email=user["email"],
            name=user["name"],
            # for backwards compatibility we return admin if no role is set
            role=user.get("app_metadata", {}).get("keep_role", AdminRole.get_name()),
            last_login=user.get("last_login", None),
            created_at=user["created_at"],
            picture=user["picture"],
        )
        return user_dto
