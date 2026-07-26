from typing import ClassVar

from uvicorn.workers import UvicornWorker


class CustomUvicornWorker(UvicornWorker):
    CONFIG_KWARGS: ClassVar[dict[str, str]] = {"lifespan": "on"}
