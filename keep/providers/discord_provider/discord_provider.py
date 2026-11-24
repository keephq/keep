"""
DiscordProvider is a class that implements the BaseOutputProvider interface for Discord messages.
"""

import base64
import binascii
import dataclasses
import json
import mimetypes
import os
import re
import time
from urllib.parse import urlparse

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl

# Discord snowflake ids are unsigned 64-bit integers, always returned/accepted
# as numeric strings. https://discord.com/developers/docs/reference#snowflakes
SNOWFLAKE_RE = re.compile(r"^\d+$")


@pydantic.dataclasses.dataclass
class DiscordProviderAuthConfig:
    """Discord authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Discord Webhook Url",
            "sensitive": True,
            "validation": "https_url",
        }
    )


class DiscordProvider(BaseProvider):
    """Send alert message to Discord."""

    PROVIDER_DISPLAY_NAME = "Discord"
    PROVIDER_CATEGORY = ["Collaboration"]

    # Discord webhook URLs are always issued on one of these hosts. Restricting
    # to them stops this provider being usable as a generic "POST/GET an
    # arbitrary HTTPS URL" primitive (HttpsUrl alone only checks the scheme).
    ALLOWED_WEBHOOK_HOSTS = {"discord.com", "discordapp.com"}

    # Discord's documented hard limits for the Execute Webhook endpoint:
    # https://discord.com/developers/docs/resources/webhook#execute-webhook
    MAX_CONTENT_LENGTH = 2000
    MAX_EMBEDS = 10
    MAX_FILES = 10
    # Default (non-boosted, non-Nitro) per-file upload limit:
    # https://discord.com/developers/docs/reference#uploading-files
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

    # Bounded retry attempts when Discord responds with 429 (rate limited)
    MAX_RETRIES = 3
    # Upper bound on how long a single retry wait can be, regardless of what
    # a Retry-After response claims - protects a worker thread from being
    # tied up indefinitely by a malformed or hostile response.
    MAX_RETRY_AFTER_SECONDS = 30.0

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DiscordProviderAuthConfig(
            **self.config.authentication
        )
        host = urlparse(str(self.authentication_config.webhook_url)).hostname
        if host not in self.ALLOWED_WEBHOOK_HOSTS:
            raise ProviderException(
                f"{self.__class__.__name__} webhook_url must be a "
                f"{'/'.join(sorted(self.ALLOWED_WEBHOOK_HOSTS))} URL, got host: {host}"
            )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate that the webhook is real and reachable, without sending a message.

        Uses Discord's "Get Webhook with Token" endpoint (a plain GET on the webhook
        URL), which requires no additional authentication beyond the URL itself.
        """
        try:
            response = requests.get(
                str(self.authentication_config.webhook_url), timeout=10
            )
            if response.status_code == 200:
                return {"webhook_url": True}
            return {
                "webhook_url": (
                    f"Webhook validation failed ({response.status_code}): "
                    f"{response.text}"
                )
            }
        except Exception as e:
            self.logger.exception("Failed to validate Discord webhook")
            return {"webhook_url": str(e)}

    def _normalize_file(self, file_spec):
        """
        Normalize a file spec into a (filename, content_bytes, content_type) tuple.

        Deliberately does *not* accept a filesystem path: this provider runs
        in the same shared, long-running process/container as every other
        tenant's workflows (see keep/workflowmanager/workflowscheduler.py),
        so a "read this path" parameter driven by workflow templating (which
        can embed externally-influenced alert/event data) would be an
        arbitrary local file read. Base64 keeps the file entirely in-memory,
        flowing through Keep's existing step-output/templating mechanism
        (`{{ steps.<name>.results.<key> }}`) with nothing ever touching disk.

        Accepts:
            - bytes: raw file content
            - tuple: (filename, content_bytes, content_type)
            - dict: {"base64": str, "filename": str} - e.g. a chart image
              rendered by an earlier step and returned as a base64 string in
              its results, referenced here via
              `{{ steps.render-chart.results.chart_base64 }}`
        """
        cls_name = self.__class__.__name__

        if isinstance(file_spec, tuple) and len(file_spec) == 3:
            _, content_bytes, _ = file_spec
            if isinstance(content_bytes, bytes) and len(
                content_bytes
            ) > self.MAX_FILE_SIZE_BYTES:
                raise ProviderException(
                    f"{cls_name} file exceeds Discord's "
                    f"{self.MAX_FILE_SIZE_BYTES} byte default upload limit "
                    f"({len(content_bytes)} bytes)"
                )
            return file_spec

        if isinstance(file_spec, bytes):
            if len(file_spec) > self.MAX_FILE_SIZE_BYTES:
                raise ProviderException(
                    f"{cls_name} file exceeds Discord's "
                    f"{self.MAX_FILE_SIZE_BYTES} byte default upload limit "
                    f"({len(file_spec)} bytes)"
                )
            return ("file", file_spec, "application/octet-stream")

        if isinstance(file_spec, dict):
            b64_content = file_spec.get("base64")
            filename = file_spec.get("filename")
            if not b64_content:
                raise ProviderException(
                    f"{cls_name} file dict 'base64' value is empty or missing"
                )
            if not filename:
                raise ProviderException(
                    f"{cls_name} file dict missing 'filename' key"
                )
            try:
                content = base64.b64decode(b64_content, validate=True)
            except (binascii.Error, ValueError) as e:
                raise ProviderException(
                    f"{cls_name} file 'base64' value is not valid base64: {e}"
                )
            if len(content) > self.MAX_FILE_SIZE_BYTES:
                raise ProviderException(
                    f"{cls_name} file exceeds Discord's "
                    f"{self.MAX_FILE_SIZE_BYTES} byte default upload limit "
                    f"({len(content)} bytes)"
                )
            content_type = (
                mimetypes.guess_type(filename)[0] or "application/octet-stream"
            )
            return (filename, content, content_type)

        raise ProviderException(
            f"{cls_name} unsupported file spec type: {type(file_spec).__name__}. "
            "Expected bytes, a (filename, content, content_type) tuple, or "
            "{'base64': ..., 'filename': ...}"
        )

    def _get_retry_after(self, response) -> float:
        """
        Extract the retry delay (seconds) Discord reports on a 429 response,
        clamped to MAX_RETRY_AFTER_SECONDS so a malformed or hostile response
        can't tie up a worker thread indefinitely.
        """
        retry_after = 1.0
        header_val = response.headers.get("Retry-After")
        if header_val:
            try:
                retry_after = float(header_val)
            except (TypeError, ValueError):
                retry_after = 1.0
        else:
            try:
                body = response.json()
                if isinstance(body, dict) and "retry_after" in body:
                    retry_after = float(body["retry_after"])
            except Exception:
                retry_after = 1.0

        return min(max(retry_after, 0.0), self.MAX_RETRY_AFTER_SECONDS)

    def _send_request(self, method: str, url: str, **request_kwargs):
        """
        Send an HTTP request to Discord, retrying (bounded) on HTTP 429 and
        honoring the (clamped) Retry-After delay Discord reports.
        """
        # Resolved dynamically (rather than bound once) so it keeps working
        # if `requests.post`/`requests.patch` are patched, e.g. in tests.
        request_fn = getattr(requests, method)
        response = None
        for attempt in range(self.MAX_RETRIES):
            response = request_fn(url, timeout=10, **request_kwargs)
            if response.status_code != 429:
                return response
            retry_after = self._get_retry_after(response)
            if attempt < self.MAX_RETRIES - 1:
                self.logger.warning(
                    f"{self.__class__.__name__} rate limited by Discord, "
                    f"retrying in {retry_after}s "
                    f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                time.sleep(retry_after)
        return response

    def _message_url(self, webhook_url, message_id: str) -> str:
        if not SNOWFLAKE_RE.match(str(message_id)):
            raise ProviderException(
                f"{self.__class__.__name__} message_id must be a Discord "
                f"snowflake (digits only), got: {message_id!r}"
            )
        base = str(webhook_url).rstrip("/")
        return f"{base}/messages/{message_id}"

    def _raise_for_error(self, response):
        """Raise a ProviderException with the clearest message we can extract."""
        try:
            r = response.json()
        except Exception:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify Discord: {response.text}"
            )

        if r.get("components") and "ListType" in r["components"][0]:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify Discord: components should be a list"
            )
        elif "message" in r:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify Discord: {r['message']}"
            )
        else:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify Discord: {response.text}"
            )

    def _notify(
        self,
        content: str = "",
        components: list = None,
        files: list = None,
        message_id: str = None,
        **kwargs,
    ):
        """
        Notify alert message to Discord using the Discord Incoming Webhook API
        https://discord.com/developers/docs/resources/webhook

        Args:
            content (str): Message text (up to 2000 characters).
            components (list): Interactive components (buttons, action rows).
            files (list): List of file specs, up to 10. Each element can be:
                - bytes: raw file content
                - tuple: (filename, content_bytes, content_type)
                - dict: {"base64": "...", "filename": "..."} - the way to
                  attach a file produced by an earlier workflow step, e.g. a
                  rendered chart or log excerpt returned as a base64 string
                  in that step's results and referenced here via
                  `{{ steps.<name>.results.<key> }}`. No filesystem path form
                  is supported, so a file can never be attached by pointing
                  at an arbitrary path on the server.
            message_id (str): Id of a previously sent webhook message. When
                set, edits that message instead of posting a new one. Obtain
                it from a prior call's return value (result["message_id"],
                requires wait=True) or from Discord directly.
            **kwargs: Any other Discord webhook JSON body param (embeds, username,
                      avatar_url, allowed_mentions, flags, thread_name,
                      applied_tags, poll, attachments) is forwarded as-is.
                      `tts` is explicitly not supported (dropped, with a
                      warning) - see README for rationale.
                      Query string params: wait, thread_id, with_components.

        Returns:
            dict: {"success": True} on success. Includes "message_id" and
            "channel_id" when Discord returns message data (wait=True or edit).
        """
        self.logger.debug("Notifying alert message to Discord")
        webhook_url = self.authentication_config.webhook_url

        # Extract query string params (not part of the JSON/form body)
        QUERY_PARAM_KEYS = ("wait", "thread_id", "with_components")
        params = {}
        for key in QUERY_PARAM_KEYS:
            if key in kwargs:
                params[key] = kwargs.pop(key)

        # tts is deliberately unsupported - see README for rationale
        # (marginal value for incident notifications, not worth the surface
        # area). Dropped rather than forwarded, so it fails safe/quiet
        # instead of unexpectedly reading messages aloud in a voice channel.
        if "tts" in kwargs:
            kwargs.pop("tts")
            self.logger.warning(
                f"{self.__class__.__name__} tts is not supported by this "
                "provider and will be ignored"
            )

        # Normalize components
        if components is None:
            components = []
        if components and not isinstance(components, list):
            self.logger.warning(
                f"{self.__class__.__name__} components should be a list, omitting"
            )
            components = []

        # Build the JSON body
        json_body = {}
        if content:
            json_body["content"] = content
        if components:
            json_body["components"] = components
        json_body.update(kwargs)

        has_content = bool(json_body.get("content"))
        has_embeds = bool(json_body.get("embeds"))
        has_components = bool(json_body.get("components"))
        has_poll = bool(json_body.get("poll"))
        has_files = bool(files)

        # Discord requires at least one of content/embeds/components/files/poll
        # when creating a new message. Edits are exempt (e.g. an edit may only
        # change `flags` to suppress embeds) - all params are optional there.
        if not message_id and not any(
            [has_content, has_embeds, has_components, has_poll, has_files]
        ):
            raise ProviderException(
                f"{self.__class__.__name__} requires at least one of: "
                "content, embeds, components, files, poll"
            )

        # Client-side guardrails against Discord's hard limits (avoids a
        # round-trip for a predictable 400 error)
        if has_content and len(json_body["content"]) > self.MAX_CONTENT_LENGTH:
            raise ProviderException(
                f"{self.__class__.__name__} content exceeds Discord's "
                f"{self.MAX_CONTENT_LENGTH} character limit "
                f"({len(json_body['content'])} chars)"
            )
        if has_embeds and len(json_body["embeds"]) > self.MAX_EMBEDS:
            raise ProviderException(
                f"{self.__class__.__name__} embeds exceeds Discord's "
                f"{self.MAX_EMBEDS} embed limit ({len(json_body['embeds'])} embeds)"
            )
        if has_files and len(files) > self.MAX_FILES:
            raise ProviderException(
                f"{self.__class__.__name__} files exceeds Discord's "
                f"{self.MAX_FILES} file limit ({len(files)} files)"
            )

        # files are only supported on new message creation, not edits
        if has_files and message_id:
            raise ProviderException(
                f"{self.__class__.__name__} files are not supported "
                "when editing a message"
            )

        # --- Create vs. edit ---
        if message_id:
            url = self._message_url(webhook_url, message_id)
            method = "patch"
        else:
            url = webhook_url
            method = "post"

        # Send the request - multipart when files are attached, plain JSON otherwise
        if has_files:
            normalized_files = [self._normalize_file(fs) for fs in files]

            form_data = {"payload_json": json.dumps(json_body)}
            request_files = []
            for i, (filename, content_bytes, content_type) in enumerate(
                normalized_files
            ):
                request_files.append(
                    (f"files[{i}]", (filename, content_bytes, content_type))
                )

            response = self._send_request(
                method, url, data=form_data, files=request_files, params=params
            )
        else:
            response = self._send_request(method, url, json=json_body, params=params)

        # Discord returns 200 (with message body) for edits or wait=true sends,
        # and 204 (no body) for a default (wait=false) new-message send.
        if response.status_code in (200, 204):
            self.logger.debug("Alert message notified to Discord")
            result = {"success": True}
            if response.status_code == 200:
                try:
                    message = response.json()
                    result["message_id"] = message.get("id")
                    result["channel_id"] = message.get("channel_id")
                except Exception:
                    pass
            return result

        self._raise_for_error(response)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    config = ProviderConfig(
        description="Discord Output Provider",
        authentication={"webhook_url": discord_webhook_url},
    )
    provider = DiscordProvider(
        context_manager, provider_id="discord-test", config=config
    )

    # Example 0: Validate the webhook is reachable before sending anything
    print(provider.validate_scopes())

    # Example 1: Basic message with interactive components
    button_component = {
        "type": 1,
        "components": [
            {"type": 2, "style": 1, "label": "Click Me!", "custom_id": "button_click"}
        ],
    }
    provider.notify(content="Hey Discord!", components=[button_component])

    # Example 2: Rich embed with username/avatar override
    embed = {
        "title": "Alert!",
        "description": "Something happened",
        "color": 0xFF0000,
    }
    provider.notify(embeds=[embed], username="AlertBot")

    # Example 3: File attachment via base64 - this is how a chart/report
    # generated by an earlier workflow step would be attached, using
    # {{ steps.<name>.results.<key> }} instead of the hardcoded base64 below
    import base64 as _base64

    fake_report_bytes = b"%PDF-1.4 fake report content"
    provider.notify(
        content="Here is the report",
        files=[
            {
                "base64": _base64.b64encode(fake_report_bytes).decode(),
                "filename": "report.pdf",
            }
        ],
    )

    # Example 4: Send with wait=True to get the message id back, then edit it
    result = provider.notify(content="Investigating...", wait=True)
    message_id = result["message_id"]
    provider.notify(message_id=message_id, content="Resolved.")
