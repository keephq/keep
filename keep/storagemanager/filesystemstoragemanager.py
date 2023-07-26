import json
import os

from keep.storagemanager.storagemanager import BaseStorageManager


class FilesystemStorageManager(BaseStorageManager):
    def __init__(self, **kwargs):
        super().__init__()
        self.directory = os.environ.get(
            "STORAGE_MANAGER_DIRECTORY", "./examples/alerts/"
        )

    def get_files(self, tenant_id) -> list[str]:
        """
        List all files.

        Returns:
            list[str]: A list of files.
        """
        files = []
        for file in os.listdir(self.directory):
            if file.endswith(".yaml") or file.endswith(".yml"):
                with open(os.path.join(self.directory, file), "r") as f:
                    f_raw = f.read()
                files.append(f_raw)
        return files
