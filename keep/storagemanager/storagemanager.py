import abc
import logging


class BaseStorageManager(metaclass=abc.ABCMeta):
    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)

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
