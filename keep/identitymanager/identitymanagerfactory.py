import enum
import importlib
import os
from typing import Type

from keep.api.core.config import config
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.identitymanager import BaseIdentityManager


class IdentityManagerTypes(enum.Enum):
    """
    Enum class representing different types of identity managers.
    """

    AUTH0 = "auth0"
    KEYCLOAK = "keycloak"
    DB = "db"
    NOAUTH = "noauth"


class IdentityManagerFactory:
    """
    Factory class for creating identity managers and authentication verifiers.
    """

    @staticmethod
    def get_identity_manager(
        tenant_id: str = None,
        context_manager: ContextManager = None,
        identity_manager_type: IdentityManagerTypes = None,
        **kwargs,
    ) -> BaseIdentityManager:
        """
        Get an instance of the identity manager based on the specified type.

        Args:
            tenant_id (str, optional): The ID of the tenant.
            context_manager (ContextManager, optional): The context manager instance.
            identity_manager_type (IdentityManagerTypes, optional): The type of identity manager to create.
            **kwargs: Additional keyword arguments to pass to the identity manager.

        Returns:
            BaseIdentityManager: An instance of the specified identity manager.
        """
        if not identity_manager_type:
            identity_manager_type = IdentityManagerTypes[
                config("AUTH_TYPE", default=IdentityManagerTypes.NOAUTH)
            ].value.lower()
        else:
            identity_manager_type = identity_manager_type.value.lower()

        return IdentityManagerFactory._load_manager(
            identity_manager_type,
            "identitymanager",
            tenant_id,
            context_manager,
            **kwargs,
        )

    @staticmethod
    def get_auth_verifier(scopes: list[str] = []) -> AuthVerifierBase:
        """
        Get an instance of the authentication verifier.

        Args:
            scopes (list[str], optional): A list of scopes for the auth verifier.

        Returns:
            AuthVerifierBase: An instance of the authentication verifier.
        """
        auth_type = os.environ.get(
            "AUTH_TYPE", IdentityManagerTypes.NOAUTH.value
        ).lower()
        return IdentityManagerFactory._load_manager(auth_type, "authverifier", scopes)

    @staticmethod
    def _load_manager(manager_type: str, manager_class: str, *args, **kwargs):
        """
        Load and instantiate a manager class based on the specified type and class.

        Args:
            manager_type (str): The type of manager to load.
            manager_class (str): The class of manager to load.
            *args: Positional arguments to pass to the manager constructor.
            **kwargs: Keyword arguments to pass to the manager constructor.

        Returns:
            The instantiated manager object.

        Raises:
            NotImplementedError: If the specified manager type or class is not implemented.
        """
        try:
            module = importlib.import_module(
                f"keep.identitymanager.identity_managers.{manager_type}.{manager_type}_{manager_class}"
            )
            class_name = f"{manager_type.capitalize()}{manager_class.capitalize()}"
            manager_class: Type = getattr(module, class_name)
            return manager_class(*args, **kwargs)
        except (ImportError, AttributeError):
            raise NotImplementedError(
                f"{manager_class.capitalize()} for {manager_type} not implemented"
            )
