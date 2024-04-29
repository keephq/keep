import os

import jwt
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from keep.api.core.db import create_user as create_user_in_db
from keep.api.core.db import delete_user as delete_user_from_db
from keep.api.core.db import get_user
from keep.api.core.db import get_users as get_users_from_db
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.core.rbac import Admin as AdminRole
from keep.api.core.rbac import get_role_by_role_name
from keep.api.models.user import User
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.identitymanager import BaseIdentityManager


class DBIdentityManager(BaseIdentityManager):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        self.logger.info("DB Identity Manager initialized")

    def on_start(self, app) -> None:
        """
        Initialize the identity manager.
        """
        # This is a special method that is called when the identity manager is
        # initialized. It is used to set up the identity manager with the FastAPI
        self.logger.info("Adding signin endpoint")

        @app.post("/signin")
        def signin(body: dict):
            # validate the user/password
            user = get_user(body.get("username"), body.get("password"))
            if not user:
                return JSONResponse(
                    status_code=401,
                    content={"message": "Invalid username or password"},
                )
            # generate a JWT secret
            jwt_secret = os.environ.get("KEEP_JWT_SECRET")
            if not jwt_secret:
                self.logger.info("missing KEEP_JWT_SECRET environment variable")
                raise HTTPException(status_code=401, detail="Missing JWT secret")
            token = jwt.encode(
                {
                    "email": user.username,
                    "tenant_id": SINGLE_TENANT_UUID,
                    "role": user.role,
                },
                jwt_secret,
                algorithm="HS256",
            )
            # return the token
            return {
                "accessToken": token,
                "tenantId": SINGLE_TENANT_UUID,
                "email": user.username,
                "role": user.role,
            }

        self.logger.info("Added signin endpoint")

    def get_users() -> list[User]:
        users = get_users_from_db()
        users = [
            User(
                email=f"{user.username}",
                name=user.username,
                role=user.role,
                last_login=str(user.last_sign_in),
                created_at=str(user.created_at),
            )
            for user in users
        ]
        return users

    def create_user(self, user_email: str, password: str, role: str) -> dict:
        try:
            user = create_user_in_db(self.tenant_id, user_email, password, role)
            return User(
                email=user_email,
                name=user_email,
                role=role,
                last_login=None,
                created_at=str(user.created_at),
            )
        except Exception:
            raise HTTPException(status_code=409, detail="User already exists")

    def delete_user(user_email: str) -> dict:
        try:
            delete_user_from_db(user_email)
            return {"status": "OK"}
        except Exception:
            raise HTTPException(status_code=404, detail="User not found")

    def get_auth_verifier(self, scopes) -> AuthVerifierBase:
        return DBAuthVerifier(scopes)


class DBAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for single tenant mode"""

    def _verify_bearer_token(self, token: str) -> AuthenticatedEntity:
        # validate the token
        jwt_secret = os.environ.get("KEEP_JWT_SECRET")
        if not jwt_secret:
            raise HTTPException(status_code=401, detail="Missing JWT secret")

        try:
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms="HS256",
            )
            tenant_id = payload.get("tenant_id")
            email = payload.get("email")
            role_name = payload.get(
                "role", AdminRole.get_name()
            )  # default to admin for backwards compatibility
            role = get_role_by_role_name(role_name)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid JWT token")
        # validate scopes
        if not role.has_scopes(self.scopes):
            raise HTTPException(
                status_code=403,
                detail="You don't have the required permissions to access this resource",
            )
        return AuthenticatedEntity(tenant_id, email, None, role_name)
