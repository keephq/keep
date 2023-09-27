import abc
import logging


class BaseStorageManager(metaclass=abc.ABCMeta):
    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)

    @abc.abstractmethod
    def get_file(self, tenant_id, filename, create_if_not_exist=False) -> str:
        """
        Get a file.
        Args:
            tenant_id (str): The tenant id.
            filename (str): The name of the file to get.
        Raises:
            NotImplementedError
        Returns:
            str: The content of the file.
        """
        raise NotImplementedError("get_file() method not implemented")

    @abc.abstractmethod
    def get_files(self, tenant_id) -> list[str]:
        """
        List all files.
        Raises:
            NotImplementedError
        Returns:
            list[str]: A list of files.
        """
        raise NotImplementedError("get_files() method not implemented")

    @abc.abstractmethod
    def store_file(self, tenant_id, file_name, file_content):
        """
        Store a file.
        Args:
            tenant_id (str): The tenant id.
            file_name (str): The name of the file to store.
            file_content (str): The content of the file to store.
        """
        raise NotImplementedError("store_file() method not implemented")
