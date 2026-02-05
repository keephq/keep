import os
import pathlib
import sys

from keep.api.core.tenant_configuration import TenantConfiguration

EE_ENABLED = os.environ.get("EE_ENABLED", "false") == "true"
EE_PATH = os.environ.get(
    "EE_PATH", "../ee"
)  # Path related to the fastapi root directory

if EE_ENABLED:
    path_with_ee = (
        str(pathlib.Path(__file__).parent.resolve())
        + "/../../"  # To go to the fastapi root directory
        + EE_PATH
        + "/../"  # To go to the parent directory of the ee directory to allow imports like ee.abc.abc
    )
    sys.path.insert(0, path_with_ee)
else:
    ALGORITHM_VERBOSE_NAME = NotImplemented
    SUMMARY_GENERATOR_VERBOSE_NAME = NotImplemented
    NAME_GENERATOR_VERBOSE_NAME = NotImplemented


def is_ee_enabled_for_tenant(tenant_id: str, tenant_configuration=None) -> bool:
    if not EE_ENABLED:
        return False

    if tenant_configuration is None:
        tenant_configuration = TenantConfiguration()

    config = tenant_configuration.get_configuration(tenant_id, "ee_enabled")
    if config is None:
        return False

    return bool(config)
