import base64
import json
import os

import kubernetes.client
import kubernetes.config
from kubernetes.client.exceptions import ApiException

from keep.api.core.config import config
from keep.secretmanager.secretmanager import BaseSecretManager

# kubernetes.config.incluster_config.SERVICE_CERT_FILENAME = "/app/bla"


VERIFY_SSL_CERT = config.get("K8S_VERIFY_SSL_CERT", cast=bool, default=True)


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
        # If we need to disable SSL, let's do it
        if not VERIFY_SSL_CERT:
            self.logger.info("Disabling SSL verification")
            try:
                # we want to change the default configuration to disable SSL verification
                default_config = kubernetes.client.Configuration.get_default_copy()
                default_config.verify_ssl = False
                kubernetes.client.Configuration.set_default(default_config)
                self.api = kubernetes.client.CoreV1Api()
                # we also need to disable SSL verification in the connection pool
                # shahar: idk why this is needed, but it is
                try:
                    self.api.api_client.rest_client.pool_manager.connection_pool_kw[
                        "ca_certs"
                    ] = None
                except Exception:
                    self.logger.exception(
                        "Error disabling SSL verification in the connection pool"
                    )
                    pass
                self.logger.info("SSL verification disabled")
            except Exception:
                self.logger.exception("Error disabling SSL verification")
                self.api = kubernetes.client.CoreV1Api()
        else:
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
        secret_name = secret_name.replace("_", "-").lower()
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
            else:
                self.logger.error(
                    "Error writing secret",
                    extra={"secret_name": secret_name, "error": str(e)},
                )
                raise

    def read_secret(self, secret_name: str, is_json: bool = False) -> str | dict:
        # k8s requirements: https://kubernetes.io/docs/concepts/overview/working-with-objects/names/#names
        secret_name = secret_name.replace("_", "-").lower()
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
            self.logger.debug(
                "Error reading secret",
                extra={"secret_name": secret_name, "error": str(e)},
            )
            raise

    def delete_secret(self, secret_name: str) -> None:
        secret_name = secret_name.replace("_", "-").lower()
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
