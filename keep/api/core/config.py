import pathlib
from enum import Enum

from starlette.config import Config

ROOT = pathlib.Path(__file__).resolve().parent.parent  # app/
BASE_DIR = ROOT.parent  # ./

try:
    config = Config(BASE_DIR / ".env")
except FileNotFoundError:
    config = Config()


class AuthenticationType(Enum):
    MULTI_TENANT = "MULTI_TENANT"
    SINGLE_TENANT = "SINGLE_TENANT"
    KEYCLOAK = "KEYCLOAK"
    NO_AUTH = "NO_AUTH"
