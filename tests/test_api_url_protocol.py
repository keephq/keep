import os
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient
from keep.api import api
from keep.exceptions.config_exception import ConfigException


def set_env(lines: List[str]):
    env_file = Path(__file__).parent / ".env"
    with open(env_file, "w") as f:
        f.write("\n".join(lines))


def test_get_app_lc_host():
    env_file = Path(__file__).parent / ".env"
    env_file.touch()
    list_lines = ["KEEP_API_URL=http://example.com", "KEEP_HOST=0.0.0.0", "PORT=8080"]
    set_env(list_lines)
    a = TestClient(api.get_app())


def test_get_app_not_lc_host_raise_exception():
    env_file = Path(__file__).parent.parent / ".env"
    env_file.touch()
    list_lines = ["KEEP_API_URL=http://example.com", "KEEP_HOST=8.8.8.8", "PORT=8080"]
    set_env(list_lines)
    with pytest.raises(ConfigException) as exc_info:
        a = TestClient(api.get_app())
    env_file.unlink()
