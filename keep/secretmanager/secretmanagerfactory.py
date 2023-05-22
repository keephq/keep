import enum

from keep.api.core.config import config
from keep.secretmanager.secretmanager import BaseSecretManager


class SecretManagerTypes(enum.Enum):
    FILE = "file"
    GCP = "gcp"


class SecretManagerFactory:
    @staticmethod
    def get_secret_manager(
        secret_manager_type: SecretManagerTypes = None, **kwargs
    ) -> BaseSecretManager:
        if not secret_manager_type:
            secret_manager_type = SecretManagerTypes[
                config("SECRET_MANAGER_TYPE", default="FILE")
            ]
        if secret_manager_type == SecretManagerTypes.FILE:
            from keep.secretmanager.filesecretmanager import FileSecretManager

            return FileSecretManager(**kwargs)
        elif secret_manager_type == SecretManagerTypes.GCP:
            from keep.secretmanager.gcpsecretmanager import GcpSecretManager

            return GcpSecretManager(**kwargs)
        raise NotImplementedError(
            f"Secret manager type {str(secret_manager_type)} not implemented"
        )
