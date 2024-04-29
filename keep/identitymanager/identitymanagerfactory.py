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
        tenant_id: str = None,
        context_manager: ContextManager = None,
        identity_manager_type: IdentityManagerTypes = None,
        **kwargs,
    ) -> BaseIdentityManager:
        if not identity_manager_type:
            identity_manager_type = IdentityManagerTypes[
                config("AUTH_TYPE", default=IdentityManagerTypes.NOAUTH)
            ].value.lower()
        else:
            # Cast to lower to avoid case sensitivity
            identity_manager_type = identity_manager_type.lower()

        # backward compatibility - cast old values to new ones
        if identity_manager_type == "no_auth":
            identity_manager_type = "noauth"  # new
        elif identity_manager_type == "multi_tenant":
            identity_manager_type = "auth0"  # new
        elif identity_manager_type == "single_tenant":
            identity_manager_type = "db"  # new
        elif identity_manager_type == "keycloak":
            identity_manager_type = "keycloak"
        # new values are allowed
        elif identity_manager_type in IdentityManagerTypes.__members__:
            pass
        else:
            raise ValueError(f"Invalid AUTH_TYPE: {identity_manager_type}")

        # Auth0 (multi tenant)
        if identity_manager_type == IdentityManagerTypes.AUTH0.value:
            from keep.identitymanager.auth0identitymanager import Auth0IdentityManager

            return Auth0IdentityManager(tenant_id, context_manager, **kwargs)
        # Database (single tenant)
        elif identity_manager_type == IdentityManagerTypes.DB.value:
            from keep.identitymanager.dbidentitymanager import DBIdentityManager

            return DBIdentityManager(tenant_id, context_manager, **kwargs)
        # Keycloak (multi tenant)
        elif identity_manager_type == IdentityManagerTypes.KEYCLOAK.value:
            from keep.identitymanager.keycloakidentitymanager import (
                KeycloakIdentityManager,
            )

            return KeycloakIdentityManager(tenant_id, context_manager, **kwargs)
        # No Auth (no authentication)
        elif identity_manager_type == IdentityManagerTypes.NOAUTH.value:
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

        # Auth0 (multi tenant)
        if auth_type == IdentityManagerTypes.AUTH0.value:
            from keep.identitymanager.auth0identitymanager import Auth0AuthVerifier

            return Auth0AuthVerifier(scopes)
        # Database (single tenant)
        elif auth_type == IdentityManagerTypes.DB.value:
            from keep.identitymanager.dbidentitymanager import DBAuthVerifier

            return DBAuthVerifier(scopes)
        # Keycloak (multi tenant)
        elif auth_type == IdentityManagerTypes.KEYCLOAK.value:
            from keep.identitymanager.keycloakidentitymanager import (
                KeycloakAuthVerifier,
            )

            return KeycloakAuthVerifier(scopes)
        # No Auth (no authentication)
        elif auth_type == IdentityManagerTypes.NOAUTH.value:
            from keep.identitymanager.noauthidentitymanager import NoAuthVerifier

            return NoAuthVerifier(scopes)

        raise NotImplementedError(
            f"Identity manager type {str(auth_type)} not implemented"
        )
