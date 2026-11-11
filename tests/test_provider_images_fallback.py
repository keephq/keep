import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
from keep.api.routes.provider_images import get_provider_image
from keep.identitymanager.authenticatedentity import AuthenticatedEntity


@pytest.fixture
def authenticated_entity():
    return AuthenticatedEntity(
        tenant_id="test-tenant",
        email="test@example.com",
    )


@pytest.fixture
def mock_session():
    session = MagicMock()
    first_result = MagicMock()
    first_result.first.return_value = None
    session.exec.return_value = first_result
    return session


def test_get_provider_image_serves_default_when_present(authenticated_entity, mock_session):
    async def _test():
        with tempfile.NamedTemporaryFile(suffix=".png") as default_file:
            default_file.write(b"DEFAULT_PNG_DATA")
            default_file.flush()

            with patch("keep.api.routes.provider_images.DEFAULT_IMAGE_PATH", default_file.name):
                response = await get_provider_image(
                    image_name="test_provider",
                    authenticated_entity=authenticated_entity,
                    session=mock_session,
                )
                assert response.status_code == 200
                assert response.body == b"DEFAULT_PNG_DATA"
                assert response.media_type == "image/png"

    asyncio.run(_test())


def test_get_provider_image_serves_fallback_when_default_missing(authenticated_entity, mock_session):
    async def _test():
        with tempfile.NamedTemporaryFile(suffix=".png") as fallback_file:
            fallback_file.write(b"FALLBACK_PNG_DATA")
            fallback_file.flush()

            non_existent_default = "/path/to/nonexistent/default-icon.png"

            with patch("keep.api.routes.provider_images.DEFAULT_IMAGE_PATH", non_existent_default):
                with patch("keep.api.routes.provider_images.FALLBACK_IMAGE_PATH", fallback_file.name):
                    response = await get_provider_image(
                        image_name="test_provider",
                        authenticated_entity=authenticated_entity,
                        session=mock_session,
                    )
                    assert response.status_code == 200
                    assert response.body == b"FALLBACK_PNG_DATA"
                    assert response.media_type == "image/png"

    asyncio.run(_test())


def test_get_provider_image_raises_404_when_both_missing(authenticated_entity, mock_session):
    async def _test():
        non_existent_default = "/path/to/nonexistent/default-icon.png"
        non_existent_fallback = "/path/to/nonexistent/fallback-icon.png"

        with patch("keep.api.routes.provider_images.DEFAULT_IMAGE_PATH", non_existent_default):
            with patch("keep.api.routes.provider_images.FALLBACK_IMAGE_PATH", non_existent_fallback):
                with pytest.raises(HTTPException) as exc_info:
                    await get_provider_image(
                        image_name="test_provider",
                        authenticated_entity=authenticated_entity,
                        session=mock_session,
                    )
                assert exc_info.value.status_code == 404
                assert exc_info.value.detail == "Default image not found"

    asyncio.run(_test())


def test_get_provider_image_serves_db_custom_image(authenticated_entity):
    async def _test():
        session = MagicMock()
        custom_record = MagicMock()
        custom_record.image_blob = b"CUSTOM_BLOB_DATA"
        session.exec.return_value.first.return_value = custom_record

        response = await get_provider_image(
            image_name="test_provider",
            authenticated_entity=authenticated_entity,
            session=session,
        )
        assert response.status_code == 200
        assert response.body == b"CUSTOM_BLOB_DATA"
        assert response.media_type == "image/png"

    asyncio.run(_test())
