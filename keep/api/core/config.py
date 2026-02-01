import pathlib

from starlette.config import Config

ROOT = pathlib.Path(__file__).resolve().parent.parent  # app/
BASE_DIR = ROOT.parent  # ./

try:
    config = Config(BASE_DIR / ".env")
except FileNotFoundError:
    config = Config()
