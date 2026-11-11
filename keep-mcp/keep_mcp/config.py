import os
from dataclasses import dataclass

VALID_TRANSPORTS = ("stdio", "streamable-http")


def _csv(value: str | None) -> tuple:
    return tuple(v.strip() for v in (value or "").split(",") if v.strip())


@dataclass(frozen=True)
class Settings:
    keep_api_url: str = "http://localhost:8080"
    keep_api_key: str | None = None
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8001
    timeout: float = 30.0
    enable_writes: bool = False
    allowed_hosts: tuple = ("localhost:*", "127.0.0.1:*", "[::1]:*")
    allowed_origins: tuple = ()

    @classmethod
    def from_env(cls, env=None) -> "Settings":
        env = os.environ if env is None else env
        transport = env.get("MCP_TRANSPORT", "stdio").lower()
        if transport not in VALID_TRANSPORTS:
            raise ValueError(
                f"MCP_TRANSPORT must be one of {VALID_TRANSPORTS}, got {transport!r}"
            )
        return cls(
            keep_api_url=env.get("KEEP_API_URL", cls.keep_api_url).rstrip("/"),
            keep_api_key=env.get("KEEP_API_KEY") or None,
            transport=transport,
            host=env.get("MCP_HOST", cls.host),
            port=int(env.get("MCP_PORT", cls.port)),
            timeout=float(env.get("KEEP_API_TIMEOUT", cls.timeout)),
            enable_writes=env.get("KEEP_MCP_ENABLE_WRITES", "").lower()
            in ("1", "true", "yes"),
            allowed_hosts=_csv(env.get("MCP_ALLOWED_HOSTS")) or cls.allowed_hosts,
            allowed_origins=_csv(env.get("MCP_ALLOWED_ORIGINS")),
        )
