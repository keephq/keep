import enum
import os

from keep.api.core.config import AuthenticationType, config
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.identitymanager import BaseIdentityManager


class IdentityManagerTypes(enum.Enum):
    AUTH0 = "auth0"
    KEYCLOAK = "keycloak"
    DB = "db"
    NOAUTH = "noauth"


class IdentityManagerFactory:
    @staticmethod
    def get_identity_manager(
        tenant_id: str,
        context_manager: ContextManager,
        identity_manager_type: IdentityManagerTypes = None,
        **kwargs,
    ) -> BaseIdentityManager:
        if not identity_manager_type:
            identity_manager_type = IdentityManagerTypes[
                config("AUTH_TYPE", default=IdentityManagerTypes.NOAUTH).upper()
            ]
        # Auth0 (multi tenant)
        if identity_manager_type == IdentityManagerTypes.AUTH0:
            from keep.identitymanager.auth0identitymanager import Auth0IdentityManager

            return Auth0IdentityManager(tenant_id, context_manager, **kwargs)
        # Database (single tenant)
        elif identity_manager_type == IdentityManagerTypes.DB:
            from keep.identitymanager.dbidentitymanager import DBIdentityManager

            return DBIdentityManager(tenant_id, context_manager, **kwargs)
        # Keycloak (multi tenant)
        elif identity_manager_type == IdentityManagerTypes.KEYCLOAK:
            from keep.identitymanager.keycloakidentitymanager import (
                KeycloakIdentityManager,
            )

            return KeycloakIdentityManager(tenant_id, context_manager, **kwargs)
        # No Auth (no authentication)
        elif identity_manager_type == IdentityManagerTypes.NOAUTH:
            from keep.identitymanager.noauthidentitymanager import NoAuthIdentityManager

            return NoAuthIdentityManager(tenant_id, context_manager, **kwargs)

        # If the identity manager type is not implemented
        raise NotImplementedError(
            f"Identity manager type {str(identity_manager_type)} not implemented"
        )

    @staticmethod
    def get_auth_verifier(scopes: list[str] = []) -> AuthVerifierBase:
        # Took the implementation from here:
        #   https://github.com/auth0-developer-hub/api_fastapi_python_hello-world/blob/main/application/json_web_token.py

        # Basically it's a factory function that returns the appropriate verifier based on the auth type

        # Determine the authentication type from the environment variable
        auth_type = os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)

        # backward compatibility - cast old values to new ones
        if auth_type == "NO_AUTH":
            auth_type = "noauth"
        elif auth_type == "MULTI_TENANT":
            auth_type = "auth0"
        elif auth_type == "SINGLE_TENANT":
            auth_type = "db"
        elif auth_type == "KEYCLOAK":
            auth_type = "keycloak"
        else:
            raise ValueError(f"Invalid AUTH_TYPE: {auth_type}")

        identity_manager = IdentityManagerFactory.get_identity_manager(
            None, None, auth_type
        )

        return identity_manager.get_auth_verifier(scopes)
