import logging
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address

from keep.api.core.config import config

logger = logging.getLogger(__name__)

LIMITER_ENABLED = config("KEEP_USE_LIMITER", default="false", cast=bool)
DEFAULT_RATE_LIMIT = config("KEEP_RATE_LIMIT_DEFAULT", default="100/minute", cast=str)

# Redis strongly recommended for real deployments:
# redis://localhost:6379/0
# redis://:password@host:6379/0
RATE_LIMIT_STORAGE_URI = config("KEEP_RATE_LIMIT_STORAGE_URI", default="memory://", cast=str)

TRUST_X_FORWARDED_FOR = config("KEEP_TRUST_X_FORWARDED_FOR", default="true", cast=bool)

logger.warning("Rate limiter is %s", "enabled" if LIMITER_ENABLED else "disabled")


def get_real_ip(request) -> str:
    """
    Determine client IP safely-ish behind proxies.
    Only use X-Forwarded-For if you actually trust your proxy layer.
    """
    if TRUST_X_FORWARDED_FOR:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_real_ip,
    enabled=LIMITER_ENABLED,
    default_limits=[DEFAULT_RATE_LIMIT],
    storage_uri=RATE_LIMIT_STORAGE_URI,
    headers_enabled=True,
)