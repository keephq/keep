"""
Tests for keep/api/redis_settings.py

Coverage:
- Existing behaviour (direct Redis, Sentinel without auth) is unchanged.
- Sentinel credentials propagation (issue #6886):
    1. Sentinel + REDIS_PASSWORD -> sentinel credentials include that password.
    2. Sentinel + REDIS_SENTINEL_PASSWORD -> takes precedence over REDIS_PASSWORD
       for sentinels; data-node password is still REDIS_PASSWORD.
    3. Sentinel + no password -> sentinel_kwargs is None (backward compat).
    4. Sentinel disabled -> plain RedisSettings returned, sentinel_kwargs absent.
    5. Sentinel username override via REDIS_SENTINEL_USERNAME.
    6. sentinel_kwargs never contains None values.
    7. REDIS_SSL=true alone leaves sentinel_kwargs as None.
    8. REDIS_SENTINEL_SSL=true sets ssl=True in sentinel_kwargs.
    9. Patched create_pool forwards sentinel_kwargs to Sentinel() and credentials to master.
    10. Delegation to original create_pool for non-sentinel and sentinel-without-credentials.
    11. arq.create_pool, arq.connections.create_pool, and arq.worker.create_pool are all patched.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Base RedisSettings tests (unchanged behaviour)
# ---------------------------------------------------------------------------


class TestGetRedisSettings:
    def test_default_redis_db(self):
        with patch.dict(os.environ, {}, clear=True):
            from keep.api.redis_settings import get_redis_settings

            settings = get_redis_settings()
            assert settings.database == 0

    def test_custom_redis_db(self):
        with patch.dict(os.environ, {"REDIS_DB": "7"}, clear=True):
            from keep.api.redis_settings import get_redis_settings

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
            from keep.api.redis_settings import get_redis_settings

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
            from keep.api.redis_settings import get_redis_settings

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
            from keep.api.redis_settings import get_redis_settings

            settings = get_redis_settings()
            assert settings.database == 5
            assert settings.ssl is True


# ---------------------------------------------------------------------------
# Sentinel-kwargs tests
# ---------------------------------------------------------------------------


class TestSentinelKwargs:
    """Tests for the sentinel_kwargs authentication fix (issue #6886)."""

    _BASE_SENTINEL_ENV = {
        "REDIS_SENTINEL_ENABLED": "true",
        "REDIS_SENTINEL_HOSTS": "sentinel-1:26379,sentinel-2:26379",
        "REDIS_SENTINEL_SERVICE_NAME": "mymaster",
    }

    def test_sentinel_with_redis_password_includes_password_in_sentinel_kwargs(
        self,
    ):
        """Sentinel enabled + REDIS_PASSWORD set -> sentinel_kwargs.password is set."""
        env = {**self._BASE_SENTINEL_ENV, "REDIS_PASSWORD": "secret"}
        with patch.dict(os.environ, env, clear=True):
            from keep.api.redis_settings import (
                _SentinelAwareRedisSettings,
                get_redis_settings,
            )

            settings = get_redis_settings()

        assert isinstance(settings, _SentinelAwareRedisSettings)
        sk = settings._sentinel_kwargs
        assert sk is not None, "sentinel_kwargs should not be None when password is set"
        assert sk.get("password") == "secret"
        assert settings.password == "secret"

    def test_sentinel_password_overrides_redis_password_for_sentinels(self):
        """REDIS_SENTINEL_PASSWORD takes precedence; data-node uses REDIS_PASSWORD."""
        env = {
            **self._BASE_SENTINEL_ENV,
            "REDIS_PASSWORD": "data-secret",
            "REDIS_SENTINEL_PASSWORD": "sentinel-secret",
        }
        with patch.dict(os.environ, env, clear=True):
            from keep.api.redis_settings import (
                _SentinelAwareRedisSettings,
                get_redis_settings,
            )

            settings = get_redis_settings()

        assert isinstance(settings, _SentinelAwareRedisSettings)
        sk = settings._sentinel_kwargs
        assert sk is not None
        assert (
            sk.get("password") == "sentinel-secret"
        ), "Sentinel nodes must use REDIS_SENTINEL_PASSWORD"
        assert (
            settings.password == "data-secret"
        ), "Master/data-node must still use REDIS_PASSWORD"

    def test_sentinel_without_password_has_no_sentinel_kwargs(self):
        """Sentinel enabled + no password -> sentinel_kwargs is None."""
        with patch.dict(os.environ, self._BASE_SENTINEL_ENV, clear=True):
            from keep.api.redis_settings import (
                _SentinelAwareRedisSettings,
                get_redis_settings,
            )

            settings = get_redis_settings()

        assert isinstance(settings, _SentinelAwareRedisSettings)
        assert (
            settings._sentinel_kwargs is None
        ), "sentinel_kwargs must be None when no credentials are configured"

    def test_non_sentinel_returns_plain_redis_settings(self):
        """Sentinel disabled -> plain RedisSettings without _sentinel_kwargs."""
        with patch.dict(os.environ, {}, clear=True):
            from arq.connections import RedisSettings

            from keep.api.redis_settings import (
                _SentinelAwareRedisSettings,
                get_redis_settings,
            )

            settings = get_redis_settings()

        assert isinstance(settings, RedisSettings)
        assert not isinstance(settings, _SentinelAwareRedisSettings)
        assert (
            not hasattr(settings, "_sentinel_kwargs")
            or settings._sentinel_kwargs is None
        )

    def test_sentinel_username_overrides_redis_username_for_sentinels(self):
        """REDIS_SENTINEL_USERNAME takes precedence for sentinel auth."""
        env = {
            **self._BASE_SENTINEL_ENV,
            "REDIS_USERNAME": "data-user",
            "REDIS_SENTINEL_USERNAME": "sentinel-user",
            "REDIS_PASSWORD": "shared-secret",
        }
        with patch.dict(os.environ, env, clear=True):
            from keep.api.redis_settings import (
                _SentinelAwareRedisSettings,
                get_redis_settings,
            )

            settings = get_redis_settings()

        assert isinstance(settings, _SentinelAwareRedisSettings)
        sk = settings._sentinel_kwargs
        assert sk is not None
        assert sk.get("username") == "sentinel-user"
        assert settings.username == "data-user"

    def test_sentinel_kwargs_does_not_contain_none_values(self):
        """Only non-empty values should appear in sentinel_kwargs."""
        env = {**self._BASE_SENTINEL_ENV, "REDIS_PASSWORD": "pw"}
        with patch.dict(os.environ, env, clear=True):
            from keep.api.redis_settings import get_redis_settings

            settings = get_redis_settings()

        sk = settings._sentinel_kwargs
        if sk is not None:
            for key, val in sk.items():
                assert val is not None, f"sentinel_kwargs[{key!r}] must not be None"
                assert val != "", f"sentinel_kwargs[{key!r}] must not be empty"

    def test_redis_ssl_alone_gives_sentinel_kwargs_none(self):
        """REDIS_SSL=true alone configures master SSL but leaves sentinel_kwargs as None."""
        env = {
            **self._BASE_SENTINEL_ENV,
            "REDIS_SSL": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            from keep.api.redis_settings import get_redis_settings

            settings = get_redis_settings()

        assert settings.ssl is True
        assert settings._sentinel_kwargs is None

    def test_redis_sentinel_ssl_gives_ssl_true(self):
        """REDIS_SENTINEL_SSL=true sets ssl=True inside sentinel_kwargs."""
        env = {
            **self._BASE_SENTINEL_ENV,
            "REDIS_SENTINEL_SSL": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            from keep.api.redis_settings import get_redis_settings

            settings = get_redis_settings()

        assert settings._sentinel_kwargs is not None
        assert settings._sentinel_kwargs.get("ssl") is True

    def test_sentinel_settings_preserve_connection_parameters(self):
        with patch.dict(os.environ, self._BASE_SENTINEL_ENV, clear=True):
            from keep.api.redis_settings import get_redis_settings

            settings = get_redis_settings()

        assert settings.conn_timeout == 60
        assert settings.conn_retries == 10
        assert settings.conn_retry_delay == 10

    def test_all_create_pool_functions_are_patched(self):
        """arq.create_pool, arq.connections.create_pool, and arq.worker.create_pool are all patched."""
        import arq
        import arq.connections as arq_connections
        import arq.worker as arq_worker

        from keep.api.redis_settings import _apply_sentinel_patch

        _apply_sentinel_patch()

        assert arq.create_pool is arq_connections.create_pool
        assert arq_worker.create_pool is arq_connections.create_pool
        assert hasattr(arq_connections, "_keep_orig_create_pool")
        assert arq_connections.create_pool is not arq_connections._keep_orig_create_pool

    @pytest.mark.asyncio
    async def test_patched_create_pool_passes_sentinel_kwargs_to_sentinel_constructor(
        self,
    ):
        """The monkey-patched create_pool must forward sentinel_kwargs to Sentinel()."""
        import arq.connections as arq_connections

        from keep.api.redis_settings import (
            _apply_sentinel_patch,
            _SentinelAwareRedisSettings,
        )

        _apply_sentinel_patch()

        sentinel_hosts = [("sentinel-1", 26379), ("sentinel-2", 26379)]
        settings = _SentinelAwareRedisSettings(
            host=sentinel_hosts,
            sentinel=True,
            sentinel_master="mymaster",
            password="data-secret",
            conn_retries=0,
        )
        settings.set_sentinel_kwargs({"password": "sentinel-secret"})

        mock_master_redis = MagicMock()
        mock_master_redis.ping = AsyncMock(return_value=True)

        with patch("redis.asyncio.sentinel.Sentinel") as mock_sentinel_cls:
            mock_sentinel_instance = mock_sentinel_cls.return_value
            mock_sentinel_instance.master_for = MagicMock(
                return_value=mock_master_redis
            )

            pool = await arq_connections.create_pool(settings)

            assert mock_sentinel_cls.called, "Sentinel() was never called"
            call_kwargs = mock_sentinel_cls.call_args.kwargs
            assert call_kwargs.get("sentinel_kwargs") == {"password": "sentinel-secret"}
            assert call_kwargs.get("password") == "data-secret"
            assert mock_sentinel_instance.master_for.called
            assert pool is mock_master_redis

    @pytest.mark.asyncio
    async def test_delegation_to_original_create_pool_for_non_sentinel_and_unauthenticated(
        self,
    ):
        """Sentinel-without-credentials and non-sentinel settings delegate to the ORIGINAL arq create_pool."""
        import arq.connections as arq_connections
        from arq.connections import RedisSettings

        from keep.api.redis_settings import (
            _apply_sentinel_patch,
            _SentinelAwareRedisSettings,
        )

        _apply_sentinel_patch()

        direct_settings = RedisSettings(host="localhost", port=6379)
        sentinel_no_auth_settings = _SentinelAwareRedisSettings(
            host=[("sentinel-1", 26379)],
            sentinel=True,
            sentinel_master="mymaster",
            sentinel_kwargs=None,
        )

        with patch(
            "redis.asyncio.sentinel.Sentinel"
        ) as mock_sentinel_cls, patch.object(
            arq_connections,
            "_keep_orig_create_pool",
            new_callable=AsyncMock,
        ) as mock_orig_cp:
            mock_orig_cp.return_value = MagicMock()

            # Direct connection delegates to original create_pool
            await arq_connections.create_pool(direct_settings)
            assert mock_orig_cp.called
            assert mock_orig_cp.call_args[0][0] is direct_settings
            assert not mock_sentinel_cls.called

            mock_orig_cp.reset_mock()

            # Sentinel without credentials delegates to original create_pool
            await arq_connections.create_pool(sentinel_no_auth_settings)
            assert mock_orig_cp.called
            assert mock_orig_cp.call_args[0][0] is sentinel_no_auth_settings
            assert not mock_sentinel_cls.called
