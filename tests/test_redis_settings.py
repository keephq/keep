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

    def test_sentinel_credentials_forwarded_to_sentinel_kwargs(self):
        import arq.connections

        with patch.dict(
            os.environ,
            {
                "REDIS_SENTINEL_ENABLED": "true",
                "REDIS_SENTINEL_HOSTS": "10.0.0.1:26379,10.0.0.2:26379",
                "REDIS_SENTINEL_SERVICE_NAME": "mymaster",
                "REDIS_PASSWORD": "secret_sentinel_password",
                "REDIS_USERNAME": "sentinel_user",
            },
            clear=True,
        ):
            settings = get_redis_settings()
            assert settings.sentinel is True
            assert settings.password == "secret_sentinel_password"
            assert settings.username == "sentinel_user"

            # Verify arq.connections.Sentinel subclass injects credentials into sentinel_kwargs
            client = arq.connections.Sentinel(
                settings.host,
                password=settings.password,
                username=settings.username,
            )
            assert client.sentinel_kwargs.get("password") == "secret_sentinel_password"
            assert client.sentinel_kwargs.get("username") == "sentinel_user"
            assert client.connection_kwargs.get("password") == "secret_sentinel_password"
            assert client.connection_kwargs.get("username") == "sentinel_user"
