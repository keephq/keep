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


def test_write_provisioned_hash_file(tenant_id, hash_value):
    """Test writing hash to file when Redis is disabled"""
    file_path = f"/state/{tenant_id}_providers_hash.txt"

    with patch("keep.providers.providers_service.REDIS", False), patch(
        "builtins.open", mock_open()
    ) as mock_file:
        ProvidersService.write_provisioned_hash(tenant_id, hash_value)

        mock_file.assert_called_once_with(file_path, "w")
        mock_file().write.assert_called_once_with(hash_value)


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
    """Test falling back to file when Redis fails"""
    with patch("keep.providers.providers_service.REDIS", True), patch(
        "redis.Redis"
    ) as mock_redis, patch("builtins.open", mock_open(read_data=hash_value)):
        mock_redis.return_value.__enter__.side_effect = redis.RedisError("Test error")

        result = ProvidersService.get_provisioned_hash(tenant_id)

        assert result == hash_value


def test_get_provisioned_hash_file_success(tenant_id, hash_value):
    """Test getting hash from file successfully"""
    with patch("keep.providers.providers_service.REDIS", False), patch(
        "builtins.open", mock_open(read_data=hash_value)
    ):
        result = ProvidersService.get_provisioned_hash(tenant_id)

        assert result == hash_value


def test_get_provisioned_hash_file_not_found(tenant_id):
    """Test handling file not found error"""
    with patch("keep.providers.providers_service.REDIS", False), patch(
        "builtins.open"
    ) as mock_file:
        mock_file.side_effect = FileNotFoundError()

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
