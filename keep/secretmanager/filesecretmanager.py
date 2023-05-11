import json

from keep.secretmanager.secretmanager import BaseSecretManager


class FileSecretManager(BaseSecretManager):
    def __init__(self, **kwargs):
        super().__init__()

    def read_secret(self, path: str, is_json: bool = False) -> str | dict:
        with open(path, "r") as f:
            file_data = f.read()
        if is_json:
            return json.loads(file_data)
        return file_data

    def write_secret(self, path: str, secret_value: str) -> None:
        with open(path, "w") as f:
            f.write(secret_value)
