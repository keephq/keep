from slowapi import Limiter
from slowapi.util import get_remote_address

from keep.api.core.config import config

limiter_enabled = config("KEEP_USE_LIMITER", default="false", cast=bool)
limiter = Limiter(key_func=get_remote_address, enabled=limiter_enabled)
