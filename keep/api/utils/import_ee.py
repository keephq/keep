import os 
import sys
import pathlib

EE_ENABLED = os.environ.get("EE_ENABLED", "false") == "true"
EE_PATH = os.environ.get("EE_PATH", "../ee")  # Path related to the fastapi root directory

if EE_ENABLED:
    path_with_ee = (
        str(pathlib.Path(__file__).parent.resolve()) + 
        "/../../" +  # To go to the fastapi root directory
        EE_PATH + 
        "/../" # To go to the parent directory of the ee directory to allow imports like ee.abc.abc
    )
    sys.path.insert(0, path_with_ee)

    from ee.experimental.incident_utils import mine_incidents_and_create_objects  # noqa
    from ee.experimental.incident_utils import ALGORITHM_VERBOSE_NAME  # noqa 
else:
    mine_incidents_and_create_objects = NotImplemented
    ALGORITHM_VERBOSE_NAME = NotImplemented
