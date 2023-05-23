import json
import os

from keep.secretmanager.secretmanager import BaseSecretManager


class FileSecretManager(BaseSecretManager):
    def __init__(self, **kwargs):
        super().__init__()
        self.directory = os.environ.get("SECRET_MANAGER_DIRECTORY", "./")

    def read_secret(self, path: str, is_json: bool = False) -> str | dict:
        path = os.path.join(self.directory, path)
        self.logger.debug(f"Reading {path}", extra={"is_json": is_json})
        with open(path, "r") as f:
            file_data = f.read()
        if is_json:
            return json.loads(file_data)
        self.logger.debug(f"Read {path}", extra={"is_json": is_json})
        return file_data

    def write_secret(self, path: str, secret_value: str) -> None:
        path = os.path.join(self.directory, path)
        with open(path, "w") as f:
            f.write(secret_value)

    def list_secrets(self, prefix: str) -> list[str]:
        lst = os.listdir(self.directory)
        if prefix:
            lst = [x for x in lst if x.startswith(prefix)]
        return lst
