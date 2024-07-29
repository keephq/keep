import abc
import logging

from keep.api.models.user import ResourcePermission
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase


class BaseIdentityManager(metaclass=abc.ABCMeta):
    def __init__(self, tenant_id, context_manager: ContextManager = None, **kwargs):
        self.tenant_id = tenant_id
        if context_manager:
            self.logger = context_manager.get_logger()
        else:
            self.logger = logging.getLogger(__name__)

    # default identity manager does not support sso
    @property
    def support_sso(self) -> bool:
        return False

    def get_sso_providers(self) -> list[str]:
        raise NotImplementedError(
            "get_sso_providers() method not implemented"
            " for {}".format(self.__class__.__name__)
        )

    def get_sso_wizard_url(self, authenticated_entity: AuthenticatedEntity) -> str:
        raise NotImplementedError(
            "get_sso_wizard_url() method not implemented"
            " for {}".format(self.__class__.__name__)
        )

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

    def get_groups(self) -> str | dict:
        """
        Get groups

        Returns:
            list: The list of groups.
        """
        raise NotImplementedError(
            "get_groups() method not implemented"
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

    def create_resource(
        self, resource_id: str, resource_name: str, scopes: list[str]
    ) -> None:
        """
        Create a resource in the identity manager for authorization purposes.

        This method is used to define a new resource that can be protected by
        the authorization system. It allows specifying the resource's unique
        identifier, name, and associated scopes, which are used to control
        access to the resource.

        Args:
            resource_id (str): The unique identifier of the resource.
            resource_name (str): The human-readable name of the resource.
            scopes (list): A list of scopes associated with the resource,
                           defining the types of actions that can be performed.
        """
        pass

    def delete_resource(self, resource_id: str) -> None:
        """
        Delete a resource from the identity manager's authorization system.

        This method removes a previously created resource from the authorization
        system. After deletion, the resource will no longer be available for
        permission checks or access control.

        Args:
            resource_id (str): The unique identifier of the resource to be deleted.
        """
        pass

    def check_permission(
        self, resource_id: str, scope: str, authenticated_entity: AuthenticatedEntity
    ) -> None:
        """
        Check if the authenticated entity has permission to access the resource.

        This method is a crucial part of the authorization process. It verifies
        whether the given authenticated entity has the necessary permissions to
        perform a specific action (defined by the scope) on a particular resource.

        Args:
            resource_id (str): The unique identifier of the resource being accessed.
            scope (str): The specific action or permission being checked.
            authenticated_entity (AuthenticatedEntity): The entity (user or service)
                                                        requesting access.

        Raises:
            HTTPException: If the authenticated entity does not have the required
                           permission, an exception with a 403 status code should
                           be raised.
        """
        pass

    def create_permissions(self, permissions: list[ResourcePermission]) -> None:
        """
        Create permissions in the identity manager for authorization purposes.

        This method is used to define new permissions that can be used to control
        access to resources. It allows specifying the resources, scopes, and users
        or groups associated with each permission.

        Args:
            permissions (list): A list of permission objects, each containing the
                                resource, scope, and user or group information.
        """
        pass

    def get_permissions(self) -> list[ResourcePermission]:
        """
        Get permissions in the identity manager for authorization purposes.

        This method is used to retrieve the permissions that have been defined
        in the identity manager. It returns a list of permission objects, each
        containing the resource, scope, and user or group information.

        Args:
            resource_ids (list): A list of resource IDs for which to retrieve
                                 permissions.

        Returns:
            list: A list of permission objects.
        """
        pass

    def get_user_permission_on_resource_type(
        self, resource_type: str, authenticated_entity: AuthenticatedEntity
    ) -> list[ResourcePermission]:
        """
        Get permissions for a specific user on a specific resource type.

        Args:
            resource_type (str): The type of resource for which to retrieve permissions.
            user_id (str): The ID of the user for which to retrieve permissions.

        Returns:
            list: A list of permission objects.
        """
        pass
