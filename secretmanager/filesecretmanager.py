import json
import os

from keep.secretmanager.secretmanager import BaseSecretManager


class FileSecretManager(BaseSecretManager):
    def __init__(self, context_manager, **kwargs):
        super().__init__(context_manager)
        self.directory = os.environ.get("SECRET_MANAGER_DIRECTORY", "./")

    def read_secret(self, secret_name: str, is_json: bool = False) -> str | dict:
        secret_name = os.path.join(self.directory, secret_name)
        self.logger.debug(f"Reading {secret_name}", extra={"is_json": is_json})
        with open(secret_name, "r") as f:
            file_data = f.read()
        if is_json:
            return json.loads(file_data)
        self.logger.debug(f"Read {secret_name}", extra={"is_json": is_json})
        return file_data

    def write_secret(self, secret_name: str, secret_value: str) -> None:
        path = os.path.join(self.directory, secret_name)
        # Create directory if not exist
        os.makedirs(self.directory, exist_ok=True)
        with open(path, "w") as f:
            self.logger.debug(f"Writing {secret_name}")
            try:
                f.write(secret_value)
            except Exception as e:
                self.logger.error(f"Error writing {secret_name}: {e}")
                raise
            self.logger.debug(f"Wrote {secret_name}")

    def delete_secret(self, secret_name: str) -> None:
        os.remove(os.path.join(self.directory, secret_name))
