from __future__ import annotations

import logging
import sys

from .config import load_settings
from .server import build_server


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    log = logging.getLogger("keep_mcp")

    if not settings.keep_api_key:
        log.error("KEEP_MCP_KEEP_API_KEY is not set; refusing to start")
        sys.exit(2)

    log.info(
        "starting keep-mcp transport=%s keep_api_url=%s",
        settings.transport,
        settings.keep_api_url,
    )

    mcp = build_server(settings)

    if settings.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = settings.http_host
        mcp.settings.port = settings.http_port
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
