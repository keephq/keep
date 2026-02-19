# https://slowapi.readthedocs.io/en/latest/#fastapi
import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

from keep.api.core.config import config

logger = logging.getLogger(__name__)
limiter_enabled = config("KEEP_USE_LIMITER", default="false", cast=bool)
default_limit = config("KEEP_LIMIT_CONCURRENCY", default="100/minute", cast=str)

logger.warning(f"Rate limiter is {'enabled' if limiter_enabled else 'disabled'}")

limiter = Limiter(
    key_func=get_remote_address, enabled=limiter_enabled, default_limits=[default_limit]
)
