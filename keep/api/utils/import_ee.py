import os 
import sys
import pathlib

ee_enabled = os.environ.get("EE_ENABLED", "false") == "true"
if ee_enabled or 1:
    path_with_ee = (
        str(pathlib.Path(__file__).parent.resolve()) + "/../../../ee/experimental"
    )
    sys.path.insert(0, path_with_ee)
    from incident_utils import mine_incidents_and_create_objects  # noqa
    from incident_utils import ALGORITHM_VERBOSE_NAME  # noqa 
else:
    mine_incidents_and_create_objects = NotImplemented
    ALGORITHM_VERBOSE_NAME = NotImplemented