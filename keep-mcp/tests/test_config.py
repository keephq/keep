import pytest
from keep_mcp.config import Settings


def test_defaults():
    s = Settings.from_env({})
    assert s.transport == "stdio" and s.keep_api_key is None
    assert s.keep_api_url == "http://localhost:8080"


def test_env_overrides_and_trailing_slash():
    s = Settings.from_env(
        {
            "KEEP_API_URL": "http://backend:8080/",
            "KEEP_API_KEY": "k",
            "MCP_TRANSPORT": "streamable-http",
            "MCP_PORT": "9000",
        }
    )
    assert s.keep_api_url == "http://backend:8080"
    assert s.keep_api_key == "k" and s.port == 9000


def test_invalid_transport():
    with pytest.raises(ValueError):
        Settings.from_env({"MCP_TRANSPORT": "sse"})
