from keep.secretmanager.secretmanager import BaseSecretManager


class GcpSecretManager(BaseSecretManager):
    def __init__(self, **kwargs):
        super().__init__()

    def write_secret(self, secret_name: str, secret_value: str) -> None:
        return super().write_secret(secret_name, secret_value)

    def read_secret(self, secret_name: str, is_json: bool = False) -> str:
        return super().read_secret(secret_name, is_json)
