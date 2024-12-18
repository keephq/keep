import base64
import json
import os

import kubernetes.client
import kubernetes.config
from kubernetes.client.exceptions import ApiException

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

        body = kubernetes.client.V1Secret(
            metadata=kubernetes.client.V1ObjectMeta(name=secret_name),
            data={"value": base64.b64encode(secret_value.encode()).decode()},
        )
        try:
            self.api.create_namespaced_secret(namespace=self.namespace, body=body)
            self.logger.info(
                "Secret created/updated successfully",
                extra={"secret_name": secret_name},
            )
        except ApiException as e:
            if e.status == 409:
                # Secret exists, try to patch it
                try:
                    self.api.patch_namespaced_secret(
                        name=secret_name, namespace=self.namespace, body=body
                    )
                    self.logger.info(
                        "Secret updated successfully",
                        extra={"secret_name": secret_name},
                    )
                except kubernetes.client.exceptions.ApiException as patch_error:
                    self.logger.error(
                        "Error updating secret",
                        extra={"secret_name": secret_name, "error": str(patch_error)},
                    )
                    raise patch_error
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
