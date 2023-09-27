import json
import os

from keep.storagemanager.storagemanager import BaseStorageManager


class FilesystemStorageManager(BaseStorageManager):
    def __init__(self, **kwargs):
        super().__init__()
        self.directory = os.environ.get("STORAGE_MANAGER_DIRECTORY", "./storage/")
        # Create it
        if not os.path.exists(self.directory):
            try:
                os.makedirs(self.directory)
            except OSError:
                raise Exception(
                    "Could not create storage directory {}".format(self.directory)
                )

    def get_files(self, tenant_id) -> list[str]:
        """
        List all files.

        Returns:
            list[str]: A list of files.
        """
        files = []
        tenant_directory = os.path.join(self.directory, tenant_id)
        if not os.path.exists(tenant_directory):
            try:
                os.makedirs(tenant_directory)
            except OSError:
                raise Exception(
                    "Could not create tenant directory {}".format(tenant_directory)
                )

        for file in os.listdir(tenant_directory):
            if file.endswith(".yaml") or file.endswith(".yml"):
                with open(os.path.join(tenant_directory, file), "r") as f:
                    f_raw = f.read()
                files.append(f_raw)
        return files

    def store_file(self, tenant_id, file_name, file_content: dict | str):
        if isinstance(file_content, dict):
            file_content = json.dumps(file_content, default=str)

        tenant_directory = os.path.join(self.directory, tenant_id)
        os.makedirs(
            tenant_directory, exist_ok=True
        )  # Create tenant directory if not exist

        full_path = os.path.join(tenant_directory, file_name)
        with open(full_path, "w") as f:
            f.write(file_content)

    def get_file(self, tenant_id, filename, create_if_not_exist=False) -> str:
        """
        Get a file.
        Args:
            tenant_id (str): The tenant id.
            filename (str): The name of the file to get.
        Returns:
            str: The content of the file.
        """
        full_path = os.path.join(self.directory, tenant_id, filename)
        if not os.path.exists(full_path):
            if create_if_not_exist:
                self.store_file(tenant_id, filename, {})
            else:
                raise Exception("File {} does not exist".format(full_path))
        with open(full_path, "r") as f:
            f_raw = f.read()
        return f_raw
