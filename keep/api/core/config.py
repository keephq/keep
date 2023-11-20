import pathlib
from enum import Enum

from starlette.config import Config

ROOT = pathlib.Path(__file__).resolve().parent.parent  # app/
BASE_DIR = ROOT.parent  # ./

config = Config(BASE_DIR / ".env")


class AuthenticationType(Enum):
    MULTI_TENANT = "MULTI_TENANT"
    SINGLE_TENANT = "SINGLE_TENANT"
    NO_AUTH = "NO_AUTH"
