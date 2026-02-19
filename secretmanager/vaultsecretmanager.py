# Builtins
import json
import os

# 3rd-party
import hvac

# Internals
from keep.secretmanager.secretmanager import BaseSecretManager


class VaultSecretManager(BaseSecretManager):
    HASHICORP_VAULT_ADDR = os.environ.get(
        "HASHICORP_VAULT_ADDR", "http://localhost:8200"
    )
    HASHICORP_VALUT_NAMESPACE = os.environ.get("HASHICORP_VALUT_NAMESPACE", "default")

    def __init__(self, context_manager, **kwargs):
        super().__init__(context_manager)
        vault_token = os.environ.get("HASHICORP_VAULT_TOKEN")
        vault_use_k8s = os.environ.get("HASHICORP_VAULT_USE_K8S", False)
        if vault_token:
            self.client = hvac.Client(
                url=self.HASHICORP_VAULT_ADDR,
                namespace=self.HASHICORP_VALUT_NAMESPACE,
                token=vault_token,
            )
        elif vault_use_k8s:
            k8s_role = os.environ.get("HASHICORP_VAULT_K8S_ROLE")
            if not k8s_role:
                raise Exception(
                    "HASHICORP_VAULT_K8S_ROLE is required when using k8s auth method"
                )
            from hvac.api.auth_methods import Kubernetes

            self.client = hvac.Client(
                url=self.HASHICORP_VAULT_ADDR, namespace=self.HASHICORP_VALUT_NAMESPACE
            )
            f = open("/var/run/secrets/kubernetes.io/serviceaccount/token")
            jwt = f.read()
            Kubernetes(self.client.adapter).login(role=k8s_role, jwt=jwt)
        else:
            raise Exception("Unsupported vault login method")
        self.logger.info("Using Vault Secret Manager")

    def write_secret(self, secret_name: str, secret_value: str) -> None:
        self.logger.info("Writing secret", extra={"secret_name": secret_name})
        self.client.secrets.kv.v2.create_or_update_secret(
            path=secret_name, secret={"value": secret_value}
        )
        self.logger.info(
            "Secret created/updated successfully", extra={"secret_name": secret_name}
        )

    def read_secret(self, secret_name: str, is_json: bool = False) -> str | dict:
        self.logger.info("Getting secret", extra={"secret_name": secret_name})
        secret = self.client.secrets.kv.v2.read_secret_version(path=secret_name)
        self.logger.info(
            "Secret retrieved successfully", extra={"secret_name": secret_name}
        )
        secret_value = secret["data"]["data"].get("value")
        if is_json: 
            try:
                secret_value = json.loads(secret_value)
            except json.JSONDecodeError as e:
                self.logger.error("Failed to parse secret as JSON", extra={"secret_name": secret_name, "error": str(e)})
                raise
        return secret_value

    def delete_secret(self, secret_name: str) -> None:
        self.logger.info("Deleting secret", extra={"secret_name": secret_name})
        self.client.secrets.kv.delete_metadata_and_all_versions(secret_name)
        self.logger.info(
            "Secret deleted successfully", extra={"secret_name": secret_name}
        )
