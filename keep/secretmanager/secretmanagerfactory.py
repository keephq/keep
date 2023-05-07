import enum

from keep.secretmanager.secretmanager import BaseSecretManager


class SecretManagerTypes(enum.Enum):
    FILE = "file"
    GCP = "gcp"


class SecretManagerFactory:
    @staticmethod
    def get_secret_manager(
        secret_manager_type: SecretManagerTypes, **kwargs
    ) -> BaseSecretManager:
        if secret_manager_type == SecretManagerTypes.FILE:
            from keep.secretmanager.filesecretmanager import FileSecretManager

            return FileSecretManager(**kwargs)
        elif secret_manager_type == SecretManagerTypes.GCP:
            from keep.secretmanager.gcpsecretmanager import GcpSecretManager

            return GcpSecretManager(**kwargs)
        raise NotImplementedError(
            f"Secret manager type {str(secret_manager_type)} not implemented"
        )
