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
    OAUTH2PROXY = "oauth2proxy"


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
            identity_manager_type = config(
                "AUTH_TYPE", default=IdentityManagerTypes.NOAUTH.value
            )
        elif isinstance(identity_manager_type, IdentityManagerTypes):
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
            manager_type = (
                IdentityManagerFactory._backward_compatible_get_identity_manager(
                    manager_type
                )
            )
            try:
                module = importlib.import_module(
                    f"keep.identitymanager.identity_managers.{manager_type}.{manager_type}_{manager_class}"
                )
            # look for the module in ee
            except ModuleNotFoundError:
                try:
                    module = importlib.import_module(
                        f"ee.identitymanager.identity_managers.{manager_type}.{manager_type}_{manager_class}"
                    )
                except ModuleNotFoundError:
                    raise NotImplementedError(
                        f"{manager_class} for {manager_type} not implemented"
                    )
            # look for the class that contains the manager_class in its name
            for _attr in dir(module):
                if manager_class in _attr.lower() and "base" not in _attr.lower():
                    class_name = _attr
                    break
            manager_class: Type = getattr(module, class_name)
            return manager_class(*args, **kwargs)
        except (ImportError, AttributeError):
            raise NotImplementedError(
                f"{manager_class} for {manager_type} not implemented"
            )

    @staticmethod
    def _backward_compatible_get_identity_manager(
        auth_type: str = None,
    ):
        """
        Map old auth_type to new IdentityManagerTypes enum.
        """
        if auth_type.lower() == "single_tenant":
            return IdentityManagerTypes.DB.value
        elif auth_type.lower() == "no_auth":
            return IdentityManagerTypes.NOAUTH.value
        elif auth_type.lower() == "multi_tenant":
            return IdentityManagerTypes.AUTH0.value
        else:
            return auth_type.lower()
