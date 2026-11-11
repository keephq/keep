import inspect
from unittest.mock import MagicMock

from keep.providers.kubernetes_provider.kubernetes_provider import \
    KubernetesProvider


def test_notify_declares_the_action_arguments():
    # The workflow editor builds the allowed `with` keys from this signature.
    params = inspect.signature(KubernetesProvider._notify).parameters
    for key in ("action", "kind", "name", "namespace", "pod_name", "replicas"):
        assert key in params


def test_notify_forwards_only_the_arguments_that_were_set():
    provider = MagicMock()

    KubernetesProvider._notify(
        provider,
        action="rollout_restart",
        kind="Deployment",
        name="web",
        namespace="prod",
    )

    provider._KubernetesProvider__rollout_restart.assert_called_once_with(
        kind="Deployment", name="web", namespace="prod"
    )
