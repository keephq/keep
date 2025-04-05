import hashlib
import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
import redis

from keep.api.consts import REDIS_DB, REDIS_HOST, REDIS_PORT
from keep.providers.providers_service import ProvidersService


@pytest.fixture
def tenant_id():
    return "test_tenant"


@pytest.fixture
def hash_value():
    return "test_hash"


def test_write_provisioned_hash_redis(tenant_id, hash_value):
    """Test writing hash to Redis when Redis is enabled"""
    with patch("keep.providers.providers_service.REDIS", True), patch(
        "redis.Redis"
    ) as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        ProvidersService.write_provisioned_hash(tenant_id, hash_value)

        mock_redis.assert_called_once_with(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB
        )
        mock_redis_instance.set.assert_called_once_with(
            f"{tenant_id}_providers_hash", hash_value
        )


def test_write_provisioned_hash_secret_manager(tenant_id, hash_value):
    """Test writing hash to secret manager when Redis is disabled"""
    mock_secret_manager = MagicMock()

    with patch("keep.providers.providers_service.REDIS", False), patch(
        "keep.providers.providers_service.SecretManagerFactory.get_secret_manager"
    ) as mock_get_secret_manager:
        mock_get_secret_manager.return_value = mock_secret_manager

        ProvidersService.write_provisioned_hash(tenant_id, hash_value)

        mock_secret_manager.write_secret.assert_called_once_with(
            secret_name=f"{tenant_id}_providers_hash", secret_value=hash_value
        )


def test_get_provisioned_hash_redis_success(tenant_id, hash_value):
    """Test getting hash from Redis successfully"""
    with patch("keep.providers.providers_service.REDIS", True), patch(
        "redis.Redis"
    ) as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = hash_value.encode()
        mock_redis.return_value.__enter__.return_value = mock_redis_instance

        result = ProvidersService.get_provisioned_hash(tenant_id)

        assert result == hash_value
        mock_redis_instance.get.assert_called_once_with(f"{tenant_id}_providers_hash")


def test_get_provisioned_hash_redis_error(tenant_id, hash_value):
    """Test falling back to secret manager when Redis fails"""
    mock_secret_manager = MagicMock()
    mock_secret_manager.read_secret.return_value = hash_value

    with patch("keep.providers.providers_service.REDIS", True), patch(
        "redis.Redis"
    ) as mock_redis, patch(
        "keep.providers.providers_service.SecretManagerFactory.get_secret_manager"
    ) as mock_get_secret_manager:
        mock_redis.return_value.__enter__.side_effect = redis.RedisError("Test error")
        mock_get_secret_manager.return_value = mock_secret_manager

        result = ProvidersService.get_provisioned_hash(tenant_id)

        assert result == hash_value
        mock_secret_manager.read_secret.assert_called_once_with(
            f"{tenant_id}_providers_hash"
        )


def test_get_provisioned_hash_secret_manager_success(tenant_id, hash_value):
    """Test getting hash from secret manager successfully"""
    mock_secret_manager = MagicMock()
    mock_secret_manager.read_secret.return_value = hash_value

    with patch("keep.providers.providers_service.REDIS", False), patch(
        "keep.providers.providers_service.SecretManagerFactory.get_secret_manager"
    ) as mock_get_secret_manager:
        mock_get_secret_manager.return_value = mock_secret_manager

        result = ProvidersService.get_provisioned_hash(tenant_id)

        assert result == hash_value
        mock_secret_manager.read_secret.assert_called_once_with(
            f"{tenant_id}_providers_hash"
        )


def test_get_provisioned_hash_secret_manager_error(tenant_id):
    """Test handling secret manager error"""
    mock_secret_manager = MagicMock()
    mock_secret_manager.read_secret.side_effect = Exception("Secret not found")

    with patch("keep.providers.providers_service.REDIS", False), patch(
        "keep.providers.providers_service.SecretManagerFactory.get_secret_manager"
    ) as mock_get_secret_manager:
        mock_get_secret_manager.return_value = mock_secret_manager

        result = ProvidersService.get_provisioned_hash(tenant_id)

        assert result is None


def test_calculate_provider_hash_json():
    """Test calculating hash from JSON input"""
    json_input = '{"provider": "test"}'
    expected_hash = hashlib.sha256(json.dumps(json_input).encode("utf-8")).hexdigest()

    result = ProvidersService.calculate_provider_hash(
        provisioned_providers_json=json_input
    )

    assert result == expected_hash


def test_calculate_provider_hash_directory():
    """Test calculating hash from directory input"""
    test_dir = "/test/providers"
    yaml_content = "provider: test"

    with patch("os.listdir") as mock_listdir, patch("os.path.join") as mock_join, patch(
        "builtins.open", mock_open(read_data=yaml_content)
    ):
        mock_listdir.return_value = ["provider1.yaml", "provider2.yml", "other.txt"]
        mock_join.side_effect = lambda *args: f"{args[0]}/{args[1]}"

        result = ProvidersService.calculate_provider_hash(
            provisioned_providers_dir=test_dir
        )

        expected_data = [yaml_content, yaml_content]  # Two YAML files
        expected_hash = hashlib.sha256(
            json.dumps(expected_data).encode("utf-8")
        ).hexdigest()

        assert result == expected_hash
        assert mock_listdir.call_count == 1
        assert mock_join.call_count == 2


def test_calculate_provider_hash_no_input():
    """Test calculating hash with no input"""
    result = ProvidersService.calculate_provider_hash()
    expected_hash = hashlib.sha256(json.dumps("").encode("utf-8")).hexdigest()

    assert result == expected_hash


def test_write_provisioned_hash_redis_enabled(tenant_id, hash_value):
    """Test writing hash to Redis when Redis is enabled"""
    with patch("keep.providers.providers_service.REDIS", True), patch(
        "redis.Redis"
    ) as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        ProvidersService.write_provisioned_hash(tenant_id, hash_value)

        mock_redis.assert_called_once_with(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB
        )
        mock_redis_instance.set.assert_called_once_with(
            f"{tenant_id}_providers_hash", hash_value
        )


def test_write_provisioned_hash_redis_disabled_secret_manager(tenant_id, hash_value):
    """Test writing hash to secret manager when Redis is disabled"""
    mock_secret_manager = MagicMock()

    with patch("keep.providers.providers_service.REDIS", False), patch(
        "keep.providers.providers_service.SecretManagerFactory.get_secret_manager"
    ) as mock_get_secret_manager:
        mock_get_secret_manager.return_value = mock_secret_manager

        ProvidersService.write_provisioned_hash(tenant_id, hash_value)

        mock_secret_manager.write_secret.assert_called_once_with(
            secret_name=f"{tenant_id}_providers_hash", secret_value=hash_value
        )


def test_get_provisioned_hash_redis_enabled_success(tenant_id, hash_value):
    """Test getting hash from Redis successfully when Redis is enabled"""
    with patch("keep.providers.providers_service.REDIS", True), patch(
        "redis.Redis"
    ) as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = hash_value.encode()
        mock_redis.return_value.__enter__.return_value = mock_redis_instance

        result = ProvidersService.get_provisioned_hash(tenant_id)

        assert result == hash_value
        mock_redis_instance.get.assert_called_once_with(f"{tenant_id}_providers_hash")


def test_get_provisioned_hash_redis_enabled_none_value(tenant_id):
    """Test getting None from Redis when Redis is enabled but no value exists"""
    with patch("keep.providers.providers_service.REDIS", True), patch(
        "redis.Redis"
    ) as mock_redis:
        # Mock Redis returning None
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = None
        mock_redis.return_value.__enter__.return_value = mock_redis_instance

        result = ProvidersService.get_provisioned_hash(tenant_id)

        assert result is None
        mock_redis_instance.get.assert_called_once_with(f"{tenant_id}_providers_hash")


def test_get_provisioned_hash_redis_preferred(tenant_id, hash_value):
    """Test that Redis is preferred over secret manager when Redis works"""
    with patch("keep.providers.providers_service.REDIS", True), patch(
        "redis.Redis"
    ) as mock_redis, patch(
        "keep.providers.providers_service.SecretManagerFactory.get_secret_manager"
    ) as mock_get_secret_manager:
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = hash_value.encode()
        mock_redis.return_value.__enter__.return_value = mock_redis_instance

        result = ProvidersService.get_provisioned_hash(tenant_id)

        assert result == hash_value
        # Should not try to use secret manager when Redis works
        mock_get_secret_manager.assert_not_called()


def test_get_provisioned_hash_redis_enabled_byte_decoding(tenant_id):
    """Test proper decoding of bytes from Redis"""
    encoded_hash = b"test_hash_with_whitespace  \n"
    expected_hash = "test_hash_with_whitespace"

    with patch("keep.providers.providers_service.REDIS", True), patch(
        "redis.Redis"
    ) as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = encoded_hash
        mock_redis.return_value.__enter__.return_value = mock_redis_instance

        result = ProvidersService.get_provisioned_hash(tenant_id)

        assert result == expected_hash
        mock_redis_instance.get.assert_called_once_with(f"{tenant_id}_providers_hash")


def test_calculate_provider_hash_consistency(tenant_id):
    """Test that hash calculation is consistent for the same input"""

    # Test with JSON input
    json_input_1 = '{"provider": "test"}'
    json_input_2 = '{"provider": "test"}'

    hash_1 = ProvidersService.calculate_provider_hash(
        provisioned_providers_json=json_input_1
    )
    hash_2 = ProvidersService.calculate_provider_hash(
        provisioned_providers_json=json_input_2
    )

    assert hash_1 == hash_2

    # Test with directory input
    yaml_content = "provider: test"

    with patch("os.listdir") as mock_listdir, patch("os.path.join") as mock_join, patch(
        "builtins.open", mock_open(read_data=yaml_content)
    ):
        mock_listdir.return_value = ["provider1.yaml"]
        mock_join.side_effect = lambda *args: f"{args[0]}/{args[1]}"

        hash_3 = ProvidersService.calculate_provider_hash(
            provisioned_providers_dir="/test/dir"
        )
        hash_4 = ProvidersService.calculate_provider_hash(
            provisioned_providers_dir="/test/dir"
        )

        assert hash_3 == hash_4
