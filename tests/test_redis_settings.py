import os
from unittest.mock import patch

from keep.api.redis_settings import get_redis_settings


class TestGetRedisSettings:
    def test_default_redis_db(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = get_redis_settings()
            assert settings.database == 0

    def test_custom_redis_db(self):
        with patch.dict(os.environ, {"REDIS_DB": "7"}, clear=True):
            settings = get_redis_settings()
            assert settings.database == 7

    def test_redis_db_with_sentinel(self):
        with patch.dict(
            os.environ,
            {
                "REDIS_SENTINEL_ENABLED": "true",
                "REDIS_SENTINEL_HOSTS": "localhost:26379",
                "REDIS_SENTINEL_SERVICE_NAME": "mymaster",
                "REDIS_DB": "3",
            },
            clear=True,
        ):
            settings = get_redis_settings()
            assert settings.database == 3
            assert settings.sentinel is True

    def test_redis_db_defaults_to_zero_with_sentinel(self):
        with patch.dict(
            os.environ,
            {
                "REDIS_SENTINEL_ENABLED": "true",
                "REDIS_SENTINEL_HOSTS": "localhost:26379",
                "REDIS_SENTINEL_SERVICE_NAME": "mymaster",
            },
            clear=True,
        ):
            settings = get_redis_settings()
            assert settings.database == 0
            assert settings.sentinel is True

    def test_redis_db_with_ssl(self):
        with patch.dict(
            os.environ,
            {
                "REDIS_SSL": "true",
                "REDIS_DB": "5",
            },
            clear=True,
        ):
            settings = get_redis_settings()
            assert settings.database == 5
            assert settings.ssl is True
