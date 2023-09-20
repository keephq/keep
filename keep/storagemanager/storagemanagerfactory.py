import enum

from keep.api.core.config import config
from keep.storagemanager.storagemanager import BaseStorageManager


class StorageManagerTypes(enum.Enum):
    FILESYSTEM = "filesystem"
    GCP = "gcp"


class StorageManagerFactory:
    @staticmethod
    def get_file_manager(
        storage_manager_type: StorageManagerTypes = None, **kwargs
    ) -> BaseStorageManager:
        if not storage_manager_type:
            storage_manager_type = StorageManagerTypes[
                config("STORAGE_MANAGER_TYPE", default="FILESYSTEM").upper()
            ]
        if storage_manager_type == StorageManagerTypes.FILESYSTEM:
            from keep.storagemanager.filesystemstoragemanager import (
                FilesystemStorageManager,
            )

            return FilesystemStorageManager(**kwargs)
        elif storage_manager_type == StorageManagerTypes.GCP:
            from keep.storagemanager.gcpstoragemanager import GcpStorageManager

            return GcpStorageManager(**kwargs)

        raise NotImplementedError(
            f"Storage manager type {str(storage_manager_type)} not implemented"
        )
