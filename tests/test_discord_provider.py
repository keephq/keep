import base64
import mimetypes
from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.discord_provider.discord_provider import (
    DiscordProvider,
    DiscordProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig

# `mimetypes` lazily scans system paths (via os.path.isfile) the first time
# guess_type()/init() runs, which showed up as an issue in earlier revisions
# of this test suite when os.path.isfile was mocked broadly (it's a single
# shared module across the process). Pre-warming here is now belt-and-braces
# since the provider no longer touches the filesystem at all for `files`.
mimetypes.init()

WEBHOOK_URL = "https://discord.com/api/webhooks/test/token"


@pytest.fixture
def discord_provider():
    context_manager = ContextManager(
        tenant_id="test-tenant", workflow_id="test-workflow"
    )
    config = ProviderConfig(
        description="Discord Test Provider",
        authentication={"webhook_url": WEBHOOK_URL},
    )
    return DiscordProvider(context_manager, provider_id="discord-test", config=config)


def _response(status_code=204, json_body=None, text="", headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.headers = headers if headers is not None else {}
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("no json body")
    return resp


@pytest.fixture
def mock_response_204():
    return _response(status_code=204)


@pytest.fixture
def mock_response_200():
    return _response(
        status_code=200, json_body={"id": "12345", "channel_id": "67890"}
    )


class TestDiscordProviderAuthConfig:
    def test_config_requires_webhook_url(self):
        config = DiscordProviderAuthConfig(webhook_url=WEBHOOK_URL)
        assert str(config.webhook_url) == WEBHOOK_URL


class TestDiscordProviderBasics:
    def test_validate_config(self, discord_provider):
        discord_provider.validate_config()
        assert discord_provider.authentication_config is not None
        assert str(discord_provider.authentication_config.webhook_url) == WEBHOOK_URL

    def test_dispose(self, discord_provider):
        discord_provider.dispose()

    def test_validate_config_accepts_discordapp_com(self):
        context_manager = ContextManager(tenant_id="t", workflow_id="w")
        config = ProviderConfig(
            description="d",
            authentication={
                "webhook_url": "https://discordapp.com/api/webhooks/1/tok"
            },
        )
        # Should not raise
        DiscordProvider(context_manager, provider_id="discord-test", config=config)

    def test_validate_config_rejects_non_discord_host(self):
        context_manager = ContextManager(tenant_id="t", workflow_id="w")
        config = ProviderConfig(
            description="d",
            authentication={"webhook_url": "https://evil.example.com/hook"},
        )
        with pytest.raises(ProviderException) as exc_info:
            DiscordProvider(context_manager, provider_id="discord-test", config=config)
        assert "evil.example.com" in str(exc_info.value)

    def test_validate_config_rejects_discord_cdn_host(self):
        """A plausible-looking but wrong Discord host (CDN, not the webhook
        API host) must also be rejected - this isn't a domain-suffix check."""
        context_manager = ContextManager(tenant_id="t", workflow_id="w")
        config = ProviderConfig(
            description="d",
            authentication={
                "webhook_url": "https://cdn.discordapp.com/api/webhooks/1/tok"
            },
        )
        with pytest.raises(ProviderException):
            DiscordProvider(context_manager, provider_id="discord-test", config=config)


class TestDiscordValidateScopes:
    @patch("requests.get")
    def test_success(self, mock_get, discord_provider):
        mock_get.return_value = _response(status_code=200)
        result = discord_provider.validate_scopes()
        assert result == {"webhook_url": True}
        mock_get.assert_called_once()
        assert mock_get.call_args[0][0] == WEBHOOK_URL

    @patch("requests.get")
    def test_failure_status(self, mock_get, discord_provider):
        mock_get.return_value = _response(status_code=404, text="Unknown Webhook")
        result = discord_provider.validate_scopes()
        assert result["webhook_url"] != True  # noqa: E712
        assert "404" in result["webhook_url"]

    @patch("requests.get")
    def test_raises_exception_is_caught(self, mock_get, discord_provider):
        mock_get.side_effect = Exception("connection refused")
        result = discord_provider.validate_scopes()
        assert result == {"webhook_url": "connection refused"}


class TestDiscordNotifyJSON:
    @patch("requests.post")
    def test_content_only(self, mock_post, discord_provider, mock_response_204):
        mock_post.return_value = mock_response_204
        result = discord_provider._notify(content="hello")
        assert result == {"success": True}
        mock_post.assert_called_once()
        assert mock_post.call_args[1]["json"] == {"content": "hello"}

    @patch("requests.post")
    def test_content_and_components(
        self, mock_post, discord_provider, mock_response_204
    ):
        mock_post.return_value = mock_response_204
        component = {
            "type": 1,
            "components": [
                {"type": 2, "style": 1, "label": "Click", "custom_id": "btn"}
            ],
        }
        result = discord_provider._notify(content="alert", components=[component])
        assert result == {"success": True}
        payload = mock_post.call_args[1]["json"]
        assert payload["content"] == "alert"
        assert payload["components"] == [component]

    @patch("requests.post")
    def test_pass_embeds_via_kwargs(
        self, mock_post, discord_provider, mock_response_204
    ):
        mock_post.return_value = mock_response_204
        embed = {"title": "Oops", "description": "something broke", "color": 0xFF0000}
        result = discord_provider._notify(embeds=[embed])
        assert result == {"success": True}
        payload = mock_post.call_args[1]["json"]
        assert payload == {"embeds": [embed]}

    @patch("requests.post")
    def test_pass_username_and_avatar_via_kwargs(
        self, mock_post, discord_provider, mock_response_204
    ):
        mock_post.return_value = mock_response_204
        discord_provider._notify(
            content="hi", username="MyBot", avatar_url="https://example.com/a.png"
        )
        payload = mock_post.call_args[1]["json"]
        assert payload["username"] == "MyBot"
        assert payload["avatar_url"] == "https://example.com/a.png"

    @patch("requests.post")
    def test_pass_allowed_mentions_via_kwargs(
        self, mock_post, discord_provider, mock_response_204
    ):
        mock_post.return_value = mock_response_204
        mentions = {"parse": ["users"], "users": ["12345"]}
        discord_provider._notify(content="hello", allowed_mentions=mentions)
        payload = mock_post.call_args[1]["json"]
        assert payload["allowed_mentions"] == mentions

    @patch("requests.post")
    def test_pass_poll_via_kwargs(self, mock_post, discord_provider, mock_response_204):
        mock_post.return_value = mock_response_204
        poll = {
            "question": {"text": "??"},
            "answers": [{"poll_media": {"text": "yes"}}],
        }
        discord_provider._notify(poll=poll)
        payload = mock_post.call_args[1]["json"]
        assert payload["poll"] == poll

    @patch("requests.post")
    def test_tts_is_dropped_not_forwarded(
        self, mock_post, discord_provider, mock_response_204
    ):
        """tts is deliberately unsupported (marginal value, see README) -
        it must never reach the Discord request payload."""
        mock_post.return_value = mock_response_204
        result = discord_provider._notify(content="hi", tts=True)
        assert result == {"success": True}
        payload = mock_post.call_args[1]["json"]
        assert "tts" not in payload

    @patch("requests.post")
    def test_200_response_returns_message_id(
        self, mock_post, discord_provider, mock_response_200
    ):
        mock_post.return_value = mock_response_200
        result = discord_provider._notify(content="hi", wait=True)
        assert result == {
            "success": True,
            "message_id": "12345",
            "channel_id": "67890",
        }

    @patch("requests.post")
    def test_raises_on_missing_required_body(self, mock_post, discord_provider):
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify()
        assert "requires at least one of" in str(exc_info.value)
        mock_post.assert_not_called()

    @patch("requests.post")
    def test_raises_on_non_success_status(self, mock_post, discord_provider):
        mock_post.return_value = _response(
            status_code=400, json_body={"message": "Bad request"}
        )
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(content="bad")
        assert "Bad request" in str(exc_info.value)

    @patch("requests.post")
    def test_raises_on_non_json_error_body(self, mock_post, discord_provider):
        mock_post.return_value = _response(status_code=500, text="Internal Error")
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(content="boom")
        assert "Internal Error" in str(exc_info.value)

    @patch("requests.post")
    def test_components_not_a_list_warns_and_continues(
        self, mock_post, discord_provider, mock_response_204
    ):
        mock_post.return_value = mock_response_204
        result = discord_provider._notify(content="ok", components={"not": "a list"})
        assert result == {"success": True}
        payload = mock_post.call_args[1]["json"]
        assert "components" not in payload


class TestDiscordNotifyQueryParams:
    @patch("requests.post")
    def test_wait_query_param(self, mock_post, discord_provider, mock_response_204):
        mock_post.return_value = mock_response_204
        discord_provider._notify(content="hi", wait=True)
        assert mock_post.call_args[1]["params"].get("wait") is True

    @patch("requests.post")
    def test_thread_id_query_param(
        self, mock_post, discord_provider, mock_response_204
    ):
        mock_post.return_value = mock_response_204
        discord_provider._notify(content="thread reply", thread_id="999")
        assert mock_post.call_args[1]["params"].get("thread_id") == "999"

    @patch("requests.post")
    def test_with_components_query_param(
        self, mock_post, discord_provider, mock_response_204
    ):
        mock_post.return_value = mock_response_204
        discord_provider._notify(content="comp", with_components=True)
        assert mock_post.call_args[1]["params"].get("with_components") is True

    @patch("requests.post")
    def test_query_params_excluded_from_json_body(
        self, mock_post, discord_provider, mock_response_204
    ):
        mock_post.return_value = mock_response_204
        discord_provider._notify(content="hi", wait=True, thread_id="42")
        payload = mock_post.call_args[1]["json"]
        assert "wait" not in payload
        assert "thread_id" not in payload


class TestDiscordNotifyFiles:
    """
    `files` never touches the filesystem: bytes/tuple specs are already
    in-memory, and dict specs carry a base64 string (the mechanism a
    previous workflow step uses to hand off a generated artifact - e.g. a
    chart image - via its `results`, since step outputs are plain strings
    rendered through templating, never raw file objects/paths).
    """

    @patch("requests.post")
    def test_bytes_file_spec(self, mock_post, discord_provider, mock_response_204):
        mock_post.return_value = mock_response_204
        discord_provider._notify(files=[b"raw bytes data"])
        filename, content, content_type = mock_post.call_args[1]["files"][0][1]
        assert filename == "file"
        assert content == b"raw bytes data"
        assert content_type == "application/octet-stream"

    @patch("requests.post")
    def test_tuple_file_spec(self, mock_post, discord_provider, mock_response_204):
        mock_post.return_value = mock_response_204
        discord_provider._notify(
            content="img", files=[("photo.png", b"image data", "image/png")]
        )
        filename, content, content_type = mock_post.call_args[1]["files"][0][1]
        assert filename == "photo.png"
        assert content == b"image data"
        assert content_type == "image/png"

    @patch("requests.post")
    def test_base64_dict_file_spec(
        self, mock_post, discord_provider, mock_response_204
    ):
        mock_post.return_value = mock_response_204
        raw = b"fake chart png bytes"
        discord_provider._notify(
            content="report",
            files=[
                {
                    "base64": base64.b64encode(raw).decode(),
                    "filename": "chart.png",
                }
            ],
        )

        call_kwargs = mock_post.call_args[1]
        assert "data" in call_kwargs
        assert "files" in call_kwargs
        assert "json" not in call_kwargs

        import json

        payload = json.loads(call_kwargs["data"]["payload_json"])
        assert payload["content"] == "report"

        filename, content, content_type = call_kwargs["files"][0][1]
        assert filename == "chart.png"
        assert content == raw
        assert content_type == "image/png"
        assert call_kwargs["files"][0][0] == "files[0]"

    @patch("requests.post")
    def test_multiple_files(self, mock_post, discord_provider, mock_response_204):
        mock_post.return_value = mock_response_204
        discord_provider._notify(
            content="here",
            files=[
                {"base64": base64.b64encode(b"log excerpt").decode(), "filename": "a.log"},
                b"inline data",
            ],
        )
        files_arg = mock_post.call_args[1]["files"]
        assert len(files_arg) == 2
        assert files_arg[0][0] == "files[0]"
        assert files_arg[1][0] == "files[1]"

    def test_dict_missing_base64_key_raises(self, discord_provider):
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(files=[{"filename": "nope.csv"}])
        assert "empty or missing" in str(exc_info.value)

    def test_dict_missing_filename_key_raises(self, discord_provider):
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(
                files=[{"base64": base64.b64encode(b"x").decode()}]
            )
        assert "missing 'filename' key" in str(exc_info.value)

    def test_dict_invalid_base64_raises(self, discord_provider):
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(
                files=[{"base64": "not-valid-base64!!!", "filename": "x.txt"}]
            )
        assert "not valid base64" in str(exc_info.value)

    def test_unsupported_file_spec_raises(self, discord_provider):
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(files=[12345])
        assert "unsupported file spec type" in str(exc_info.value)

    def test_string_file_spec_is_unsupported(self, discord_provider):
        """A bare string is no longer accepted as a file path - this
        provider never reads from the local filesystem."""
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(files=["/etc/passwd"])
        assert "unsupported file spec type" in str(exc_info.value)

    def test_embeds_only_valid_without_content(self, discord_provider):
        with patch("requests.post") as mock_post:
            mock_post.return_value = _response(status_code=204)
            embed = {"title": "Standalone", "color": 0x00FF00}
            discord_provider._notify(embeds=[embed])
            assert mock_post.call_args[1]["json"] == {"embeds": [embed]}


class TestDiscordGuardrails:
    def test_content_too_long_raises(self, discord_provider):
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(content="x" * 2001)
        assert "character limit" in str(exc_info.value)

    def test_content_at_limit_is_allowed(self, discord_provider):
        with patch("requests.post") as mock_post:
            mock_post.return_value = _response(status_code=204)
            discord_provider._notify(content="x" * 2000)
            mock_post.assert_called_once()

    def test_too_many_embeds_raises(self, discord_provider):
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(embeds=[{"title": str(i)} for i in range(11)])
        assert "embed limit" in str(exc_info.value)

    def test_too_many_files_raises(self, discord_provider):
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(content="x", files=[b"f"] * 11)
        assert "file limit" in str(exc_info.value)

    def test_bytes_file_too_large_raises(self, discord_provider):
        oversized = b"x" * (discord_provider.MAX_FILE_SIZE_BYTES + 1)
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(files=[oversized])
        assert "byte default upload limit" in str(exc_info.value)

    def test_base64_file_too_large_raises(self, discord_provider):
        oversized = b"x" * (discord_provider.MAX_FILE_SIZE_BYTES + 1)
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(
                files=[
                    {
                        "base64": base64.b64encode(oversized).decode(),
                        "filename": "big.bin",
                    }
                ]
            )
        assert "byte default upload limit" in str(exc_info.value)

    def test_tuple_file_too_large_raises(self, discord_provider):
        oversized = b"x" * (discord_provider.MAX_FILE_SIZE_BYTES + 1)
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(files=[("big.bin", oversized, "application/octet-stream")])
        assert "byte default upload limit" in str(exc_info.value)


class TestDiscordNotifyEdit:
    @patch("requests.patch")
    def test_edit_message(self, mock_patch, discord_provider):
        mock_patch.return_value = _response(
            status_code=200, json_body={"id": "111", "channel_id": "222"}
        )
        result = discord_provider._notify(message_id="111", content="Updated!")
        assert result == {
            "success": True,
            "message_id": "111",
            "channel_id": "222",
        }
        mock_patch.assert_called_once()
        url = mock_patch.call_args[0][0]
        assert url.endswith("/messages/111")
        assert mock_patch.call_args[1]["json"] == {"content": "Updated!"}

    @patch("requests.patch")
    def test_edit_without_content_is_allowed(self, mock_patch, discord_provider):
        """Editing doesn't require content/embeds/components/files/poll."""
        mock_patch.return_value = _response(
            status_code=200, json_body={"id": "111", "channel_id": "222"}
        )
        result = discord_provider._notify(message_id="111", flags=4)
        assert result["success"] is True
        assert mock_patch.call_args[1]["json"] == {"flags": 4}

    @patch("requests.patch")
    def test_edit_raises_on_error(self, mock_patch, discord_provider):
        mock_patch.return_value = _response(
            status_code=404, json_body={"message": "Unknown Message"}
        )
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(message_id="12345", content="x")
        assert "Unknown Message" in str(exc_info.value)

    def test_edit_rejects_non_snowflake_message_id(self, discord_provider):
        """message_id is interpolated into the request URL - it must be
        digits-only (a real Discord snowflake), not an arbitrary string."""
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(message_id="does-not-exist", content="x")
        assert "snowflake" in str(exc_info.value)

    def test_edit_with_files_raises(self, discord_provider):
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(message_id="111", files=[b"data"], content="x")
        assert "files are not supported when editing" in str(exc_info.value)

    def test_edit_rejects_path_traversal_message_id(self, discord_provider):
        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(
                message_id="123/../../webhooks/other-id/other-token",
                content="x",
            )
        assert "snowflake" in str(exc_info.value)


class TestDiscordRateLimiting:
    @patch("time.sleep")
    @patch("requests.post")
    def test_retries_on_429_then_succeeds(
        self, mock_post, mock_sleep, discord_provider
    ):
        rate_limited = _response(
            status_code=429,
            json_body={"message": "You are being rate limited.", "retry_after": 0.5},
            headers={"Retry-After": "0.5"},
        )
        success = _response(status_code=204)
        mock_post.side_effect = [rate_limited, success]

        result = discord_provider._notify(content="hi")
        assert result == {"success": True}
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(0.5)

    @patch("time.sleep")
    @patch("requests.post")
    def test_exhausts_retries_and_raises(
        self, mock_post, mock_sleep, discord_provider
    ):
        rate_limited = _response(
            status_code=429,
            json_body={"message": "You are being rate limited.", "retry_after": 1},
        )
        mock_post.return_value = rate_limited

        with pytest.raises(ProviderException) as exc_info:
            discord_provider._notify(content="hi")

        assert "rate limited" in str(exc_info.value).lower()
        assert mock_post.call_count == discord_provider.MAX_RETRIES
        # only sleeps between attempts, not after the last one
        assert mock_sleep.call_count == discord_provider.MAX_RETRIES - 1

    @patch("time.sleep")
    @patch("requests.post")
    def test_retry_after_falls_back_to_body_when_no_header(
        self, mock_post, mock_sleep, discord_provider
    ):
        rate_limited = _response(
            status_code=429,
            json_body={"message": "You are being rate limited.", "retry_after": 2.5},
        )
        success = _response(status_code=204)
        mock_post.side_effect = [rate_limited, success]

        discord_provider._notify(content="hi")
        mock_sleep.assert_called_once_with(2.5)

    @patch("time.sleep")
    @patch("requests.post")
    def test_retry_after_defaults_when_unparseable(
        self, mock_post, mock_sleep, discord_provider
    ):
        rate_limited = _response(status_code=429, json_body={"message": "limited"})
        success = _response(status_code=204)
        mock_post.side_effect = [rate_limited, success]

        discord_provider._notify(content="hi")
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    @patch("requests.post")
    def test_retry_after_is_clamped_to_max(
        self, mock_post, mock_sleep, discord_provider
    ):
        """A malicious/misbehaving endpoint claiming an enormous Retry-After
        must not be able to block a worker thread for that long."""
        rate_limited = _response(
            status_code=429,
            json_body={"message": "limited", "retry_after": 999999},
            headers={"Retry-After": "999999"},
        )
        success = _response(status_code=204)
        mock_post.side_effect = [rate_limited, success]

        discord_provider._notify(content="hi")
        mock_sleep.assert_called_once_with(discord_provider.MAX_RETRY_AFTER_SECONDS)
