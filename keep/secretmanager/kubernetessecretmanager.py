import base64
import json
import os

import kubernetes.client
import kubernetes.config
from kubernetes.client.rest import ApiException

from keep.secretmanager.secretmanager import BaseSecretManager


class KubernetesSecretManager(BaseSecretManager):
    def __init__(self, context_manager, **kwargs):
        super().__init__(context_manager)
        # Initialize Kubernetes configuration (Assuming it's already set up properly)
        self.namespace = os.environ.get("K8S_NAMESPACE", "default")
        self.logger.info(
            "Using K8S Secret Manager", extra={"namespace": self.namespace}
        )
        # kubernetes.config.load_config()  # when running locally
        kubernetes.config.load_incluster_config()
        self.api = kubernetes.client.CoreV1Api()

    def write_secret(self, secret_name: str, secret_value: str) -> None:
        """
        Writes a secret to the Kubernetes Secret.

        Args:
            secret_name (str): The name of the secret.
            secret_value (str): The value of the secret.
        Raises:
            ApiException: If an error occurs while writing the secret.
        """
        # k8s requirements: https://kubernetes.io/docs/concepts/overview/working-with-objects/names/#names
        secret_name = secret_name.replace("_", "-")
        self.logger.info("Writing secret", extra={"secret_name": secret_name})

        try:
            body = kubernetes.client.V1Secret(
                metadata=kubernetes.client.V1ObjectMeta(name=secret_name),
                data={"value": base64.b64encode(secret_value.encode()).decode()},
            )
            self.api.create_namespaced_secret(namespace=self.namespace, body=body)
            self.logger.info(
                "Secret created/updated successfully",
                extra={"secret_name": secret_name},
            )
        except ApiException as e:
            self.logger.error(
                "Error writing secret",
                extra={"secret_name": secret_name, "error": str(e)},
            )
            raise

    def read_secret(self, secret_name: str, is_json: bool = False) -> str | dict:
        # k8s requirements: https://kubernetes.io/docs/concepts/overview/working-with-objects/names/#names
        secret_name = secret_name.replace("_", "-")
        self.logger.info("Getting secret", extra={"secret_name": secret_name})
        try:
            response = self.api.read_namespaced_secret(
                name=secret_name, namespace=self.namespace
            )
            secret_data = base64.b64decode(response.data.get("value", "")).decode()
            if is_json:
                secret_data = json.loads(secret_data)
            self.logger.info(
                "Got secret successfully", extra={"secret_name": secret_name}
            )
            return secret_data
        except ApiException as e:
            self.logger.error(
                "Error reading secret",
                extra={"secret_name": secret_name, "error": str(e)},
            )
            raise

    def list_secrets(self, prefix: str) -> list:
        """
        List all secrets in the Kubernetes Secret with the given prefix.

        Args:
            prefix (str): The prefix to filter secrets by.

        Returns:
            list: A list of secret names.
        """
        self.logger.info("Listing secrets", extra={"prefix": prefix})
        try:
            secrets = self.api.list_namespaced_secret(namespace=self.namespace)
            secret_names = [secret.metadata.name for secret in secrets.items]
            filtered_secrets = [
                name for name in secret_names if name.startswith(prefix)
            ]
            self.logger.info("Listed secrets successfully", extra={"prefix": prefix})
            return filtered_secrets
        except ApiException as e:
            self.logger.error(
                "Error listing secrets", extra={"prefix": prefix, "error": str(e)}
            )
            raise

    def delete_secret(self, secret_name: str) -> None:
        self.logger.info("Deleting secret", extra={"secret_name": secret_name})
        try:
            self.api.delete_namespaced_secret(
                name=secret_name, namespace=self.namespace, body={}
            )
            self.logger.info(
                "Deleted secret successfully", extra={"secret_name": secret_name}
            )
        except ApiException as e:
            self.logger.error(
                "Error deleting secret",
                extra={"secret_name": secret_name, "error": str(e)},
            )
            raise
