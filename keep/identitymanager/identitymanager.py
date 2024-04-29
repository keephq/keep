import abc

from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authverifierbase import AuthVerifierBase


class BaseIdentityManager(metaclass=abc.ABCMeta):
    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        self.tenant_id = tenant_id
        self.logger = context_manager.get_logger()

    @abc.abstractmethod
    def on_start(self, app) -> None:
        """
        Initialize the identity manager.
        """
        pass

    @abc.abstractmethod
    def get_users(self) -> str | dict:
        """
        Get users

        Returns:
            list: The list of users.
        """
        raise NotImplementedError(
            "get_users() method not implemented"
            " for {}".format(self.__class__.__name__)
        )

    @abc.abstractmethod
    def create_user(self, user_email, password, role) -> None:
        """
        Create a user in the identity manager.

        Args:
            user_email (str): The email of the user to create.
            tenant_id (str): The tenant id of the user to create.
            password (str): The password of the user to create.
            role (str): The role of the user to create.
        """

    @abc.abstractmethod
    def delete_user(self, username: str) -> None:
        """
        Delete a user from the identity manager.

        Args:
            username (str): The name of the user to delete.
        """
        raise NotImplementedError("delete_secret() method not implemented")

    @abc.abstractmethod
    def get_auth_verifier(self, scopes: list) -> AuthVerifierBase:
        """
        Get the authentication verifier for a token.

        Args:
            token (str): The token to verify.

        Returns:
            dict: The authentication verifier.
        """
        raise NotImplementedError(
            "get_auth_verifier() method not implemented"
            " for {}".format(self.__class__.__name__)
        )
