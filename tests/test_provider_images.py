import asyncio

import pytest

from keep.api.routes import provider_images
from keep.api.routes.provider_images import get_provider_image
from keep.identitymanager.authenticatedentity import AuthenticatedEntity

PNG_BYTES = b"\x89PNG\r\n\x1a\n"


class _NoCustomImageSession:
    """Stand-in for get_session() whose query never finds a custom image."""

    def exec(self, *args, **kwargs):
        class _Result:
            def first(self):
                return None

        return _Result()


def _entity():
    return AuthenticatedEntity(tenant_id="test-tenant", email="test@keephq.dev")


def _serve_default_icon(monkeypatch, tmp_path, default_exists, fallback_exists):
    default = tmp_path / "unknown-icon.png"
    fallback = tmp_path / "fallback-icon.png"
    if default_exists:
        default.write_bytes(PNG_BYTES + b"-default")
    if fallback_exists:
        fallback.write_bytes(PNG_BYTES + b"-fallback")
    monkeypatch.setattr(provider_images, "DEFAULT_IMAGE_PATH", str(default))
    monkeypatch.setattr(provider_images, "FALLBACK_IMAGE_PATH", str(fallback))
    return asyncio.run(get_provider_image("acme", _entity(), _NoCustomImageSession()))


def test_default_icon_served_when_present(monkeypatch, tmp_path):
    resp = _serve_default_icon(monkeypatch, tmp_path, True, False)
    assert resp.body == PNG_BYTES + b"-default"
    assert resp.media_type == "image/png"


def test_fallback_icon_served_when_default_missing(monkeypatch, tmp_path):
    # regression: the computed fallback path was ignored and the default
    # constant re-opened, so a missing default icon 404'd despite the
    # "using fallback path" log line
    resp = _serve_default_icon(monkeypatch, tmp_path, False, True)
    assert resp.body == PNG_BYTES + b"-fallback"
    assert resp.media_type == "image/png"


def test_404_when_default_and_fallback_missing(monkeypatch, tmp_path):
    with pytest.raises(Exception) as exc_info:
        _serve_default_icon(monkeypatch, tmp_path, False, False)
    assert exc_info.value.status_code == 404
