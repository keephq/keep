"""
Slack provider is an interface for Slack messages.
"""

import dataclasses
import json
import logging
import os

import emoji
import pydantic
import requests
from fastapi import Request

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.alerts import query_last_alerts
from keep.api.core.db import get_session_sync as get_session
from keep.api.models.action_type import ActionType
from keep.api.routes.alerts import assign_alert
from keep.api.routes.providers import install_provider_oauth2
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.functions import utcnowtimestamp
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.models.provider_method import ProviderMethod


@pydantic.dataclasses.dataclass
class SlackProviderAuthConfig:
    """Slack authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Slack Webhook Url",
            "sensitive": True,
        },
        default="",
    )
    access_token: str = dataclasses.field(
        metadata={
            "description": "For access token installation flow, use Keep UI",
            "required": False,
            "sensitive": True,
            "hidden": True,
        },
        default="",
    )


class SlackProvider(BaseProvider):
    """Send alert message to Slack."""

    PROVIDER_DISPLAY_NAME = "Slack"
    OAUTH2_URL = os.environ.get("SLACK_OAUTH2_URL")
    SLACK_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID")
    SLACK_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET")
    SLACK_VERIFICATION_TOKEN = os.environ.get("SLACK_VERIFICATION_TOKEN")
    SLACK_API = "https://slack.com/api"
    PROVIDER_CATEGORY = ["Collaboration"]

    # Shahar: TODO - this could be dynamic from UI/configuration
    EMOJI_HANDLERS = {
        "eyes": "_handle_eyes_reaction",
        "wave": "_handle_wave_reaction",
    }

    PROVIDER_METHODS = [
        ProviderMethod(
            name="Send a Slack Message",
            func_name="send_slack_message",
            scopes=[],
            description="Send a Slack Message",
            type="action",
        ),
    ]

    async def _handle_eyes_reaction(
        self,
        related_alert,
        event,
        user_id,
        user_email,
        channel,
        ts,
        message,
        message_link,
    ):
        self.logger.info("Handling eyes reaction")
        # send the full payload
        self._notify(
            message=f"👀 <@{user_id}> is watching this alert",
            channel=channel,
            thread_timestamp=ts,
        )
        return {"status": "success", "event_type": "reaction_added", "reaction": "eyes"}

    async def _handle_wave_reaction(
        self,
        related_alert,
        event,
        user_id,
        user_email,
        channel,
        ts,
        message,
        message_link,
    ):
        try:
            self.logger.info("Handling wave reaction")
            authenticated_entity = authenticated_entity = AuthenticatedEntity(
                tenant_id=self.context_manager.tenant_id, email=user_email
            )
            assigned = assign_alert(
                authenticated_entity=authenticated_entity,
                fingerprint=related_alert.fingerprint,
                last_received=related_alert.lastReceived,
            )
            self.logger.info(f"Assigned alert: {assigned}")
        except Exception:
            self.logger.exception("Error assigning alert")

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SlackProviderAuthConfig(
            **self.config.authentication
        )
        if (
            not self.authentication_config.webhook_url
            and not self.authentication_config.access_token
        ):
            raise Exception("Slack webhook url OR Slack access token is required")

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    @staticmethod
    def oauth2_logic(**payload) -> dict:
        """
        Logic for handling oauth2 callback.

        Args:
            payload (dict): The payload from the oauth2 callback.

        Returns:
            dict: The provider configuration.
        """
        code = payload.get("code")
        if not code:
            raise Exception("No code provided")
        exchange_request_payload = {
            **payload,
            "client_id": SlackProvider.SLACK_CLIENT_ID,
            "client_secret": SlackProvider.SLACK_CLIENT_SECRET,
        }
        response = requests.post(
            f"{SlackProvider.SLACK_API}/oauth.v2.access",
            data=exchange_request_payload,
        )
        response_json = response.json()
        if not response.ok or not response_json.get("ok"):
            raise Exception(
                response_json.get("error"),
            )
        new_provider_info = {"access_token": response_json.get("access_token")}

        team_name = response_json.get("team", {}).get("name")
        team_id = response_json.get("team", {}).get("id")
        # we need to have team_id in name because when events are sent to us, we only get team_id
        if team_name and team_id:
            new_provider_info["provider_name"] = team_name
            new_provider_info["provider_secret_suffix"] = team_id

        return new_provider_info

    def _notify_reaction(self, channel: str, emoji: str, timestamp: str):
        if not self.authentication_config.access_token:
            raise ProviderException("Access token is required to notify reaction")

        self.logger.info(
            "Notifying reaction to Slack using",
            extra={
                "emoji": emoji,
                "channel": channel,
                "timestamp": timestamp,
            },
        )
        payload = {
            "channel": channel,
            "token": self.authentication_config.access_token,
            "name": emoji,
            "timestamp": timestamp,
        }
        response = requests.post(
            f"{SlackProvider.SLACK_API}/reactions.add",
            data=payload,
        )
        if not response.ok:
            raise ProviderException(
                f"Failed to notify reaction to Slack: {response.text}"
            )
        self.logger.info("Reaction notified to Slack")
        return response.json()

    def _notify(
        self,
        message="",
        blocks=[],
        channel="",
        slack_timestamp="",
        thread_timestamp="",
        attachments=[],
        username="",
        notification_type="message",
        **kwargs: dict,
    ):
        """
        Notify alert message to Slack using the Slack Incoming Webhook API
        https://api.slack.com/messaging/webhooks

        Args:
            kwargs (dict): The providers with context
        """
        if notification_type == "reaction":
            return self._notify_reaction(
                channel=channel,
                emoji=message,
                timestamp=thread_timestamp,
            )

        notify_data = None
        self.logger.info(
            f"Notifying message to Slack using {'webhook' if self.authentication_config.webhook_url else 'access token'}",
            extra={
                "slack_message": message,
                "blocks": blocks,
                "channel": channel,
            },
        )
        if not message:
            if not blocks and not attachments:
                raise ProviderException(
                    "Message is required - see for example https://github.com/keephq/keep/blob/main/examples/workflows/slack_basic.yml#L16"
                )
        payload = {
            "channel": channel,
        }
        if message:
            payload["text"] = message
        if blocks:
            payload["blocks"] = (
                json.dumps(blocks)
                if isinstance(blocks, dict) or isinstance(blocks, list)
                else blocks
            )
        if attachments:
            payload["attachments"] = (
                json.dumps(attachments)
                if isinstance(attachments, dict) or isinstance(attachments, list)
                else blocks
            )
        if username:
            payload["username"] = username

        if self.authentication_config.webhook_url:
            # If attachments are present, we need to send them as the payload with nothing else
            # Also, do not encode the payload as json, but as x-www-form-urlencoded
            # Only reference I found for it is: https://getkeep.slack.com/services/B082F60L9GX?added=1 and
            # https://stackoverflow.com/questions/42993602/slack-chat-postmessage-attachment-gives-no-text
            if payload.get("attachments", None):
                payload["attachments"] = attachments
                response = requests.post(
                    self.authentication_config.webhook_url,
                    data={"payload": json.dumps(payload)},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            else:
                response = requests.post(
                    self.authentication_config.webhook_url,
                    json=payload,
                )
            if not response.ok:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify alert message to Slack: {response.text}"
                )
            notify_data = {"slack_timestamp": utcnowtimestamp()}
        elif self.authentication_config.access_token:
            if not channel:
                raise ProviderException("Channel is required (E.g. C12345)")
            payload["token"] = self.authentication_config.access_token
            if slack_timestamp == "" and thread_timestamp == "":
                self.logger.info("Sending a new message to Slack")
                method = "chat.postMessage"
            else:
                self.logger.info(f"Updating Slack message with ts: {slack_timestamp}")
                if slack_timestamp:
                    payload["ts"] = slack_timestamp
                    method = "chat.update"
                else:
                    method = "chat.postMessage"
                    payload["thread_ts"] = thread_timestamp

            if payload.get("attachments", None):
                payload["attachments"] = attachments
                response = requests.post(
                    f"{SlackProvider.SLACK_API}/{method}",
                    data={"payload": json.dumps(payload)},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            else:
                response = requests.post(
                    f"{SlackProvider.SLACK_API}/{method}", data=payload
                )

            response_json = response.json()
            if not response.ok or not response_json.get("ok"):
                raise ProviderException(
                    f"Failed to notify alert message to Slack: {response_json.get('error')}"
                )

            ts = response_json.get("ts")
            slack_link = f"https://slack.com/archives/{channel}/p{ts.replace('.', '')}"
            notify_data = {
                "slack_timestamp": ts,
                # auto-enrich the slack link
                "slack_link_autoenrich": slack_link,
            }
        self.logger.info("Message notified to Slack")
        return notify_data

    @staticmethod
    async def challenge(request: Request):
        try:
            logger = logging.getLogger(__name__)
            data = await request.json()
            if data.get("type") == "url_verification":
                challenge = data.get("challenge")
                logger.info(f"Responding to Slack challenge: {challenge}")
                return {"challenge": challenge}
        except Exception as e:
            logger.exception(f"Failed to process Slack challenge: {str(e)}")
            raise ProviderException("Failed to process Slack challenge")

    @staticmethod
    async def extract_provider_id_from_event(data: dict, request: Request) -> str:
        return data.get("team_id")

    @staticmethod
    async def verify_request(request: Request):
        if not SlackProvider.SLACK_VERIFICATION_TOKEN:
            raise ProviderException(
                "Slack verification token is required for handling Slack events"
            )
        # compare between request token and the token in the environment
        data = await request.json()
        if data.get("token") == SlackProvider.SLACK_VERIFICATION_TOKEN:
            return True
        raise ProviderException("Invalid Slack verification token")

    async def handle_event(self, event: dict):
        """
        Handle various Slack events including reactions, comments, and other interactions.

        Args:
            event (dict): The Slack event payload

        Returns:
            dict: Response with status and details
        """
        self.logger.info(
            "Handling Slack event",
            extra={"event_type": event.get("event", {}).get("type")},
        )

        try:
            event_type = event.get("event", {}).get("type")

            # Get common event data
            event_data = {
                "team_id": event.get("team_id"),
                "event_id": event.get("event_id"),
                "event_time": event.get("event_time"),
            }

            # Handle different event types
            if event_type == "reaction_added":
                return await self._handle_reaction_event(event, event_data)
            elif event_type == "message":
                return await self._handle_message_event(event, event_data)
            elif event_type == "app_mention":
                return await self._handle_mention_event(event, event_data)
            elif event_type == "file_shared":
                return await self._handle_file_event(event, event_data)
            else:
                self.logger.info(f"Unhandled event type: {event_type}")
                return {
                    "status": "ignored",
                    "reason": f"Event type {event_type} not handled",
                }

        except Exception as e:
            self.logger.error(f"Error handling Slack event: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}

    async def _handle_reaction_event(self, event: dict, event_data: dict):
        """
        Handle reaction_added events from Slack.

        Args:
            event (dict): The Slack event payload
            event_data (dict): Basic event metadata

        Returns:
            dict: Response with status and details
        """
        self.logger.info("Handling reaction added event")

        try:
            # Extract reaction details
            reaction_event = event.get("event", {})
            user_id = reaction_event.get("user")
            reaction = reaction_event.get("reaction")
            item = reaction_event.get("item", {})
            channel = item.get("channel")
            ts = item.get("ts")

            if not all([user_id, channel, ts]):
                self.logger.warning(
                    "Missing required fields for reaction event",
                    extra={"user_id": user_id, "channel": channel, "ts": ts},
                )
                return {"status": "error", "reason": "Missing required fields"}

            # Get user email
            try:
                user_email = self._get_user_email(user_id)
            except Exception as e:
                self.logger.error(f"Failed to get user email: {str(e)}")
                user_email = f"unknown_user_{user_id}"

            # Get message content
            try:
                message = self._get_message(event)
            except Exception as e:
                self.logger.error(f"Failed to get message content: {str(e)}")
                message = "Message content unavailable"

            # Create message link
            message_link = (
                f"https://slack.com/archives/{channel}/p{ts.replace('.', '')}"
            )

            # Query for related alert
            related_alert = await self._query_related_alert(message_link)

            handler_method_name = self.EMOJI_HANDLERS.get(reaction)
            if handler_method_name:
                try:
                    self.logger.info(
                        f"Found handler method for reaction: {handler_method_name}"
                    )
                    handler_method = getattr(self, handler_method_name)
                    handler_result = await handler_method(
                        related_alert=related_alert,
                        event=event,
                        user_id=user_id,
                        user_email=user_email,
                        channel=channel,
                        ts=ts,
                        message=message,
                        message_link=message_link,
                    )
                    self.logger.info(f"Handler method result: {handler_result}")
                except Exception:
                    self.logger.exception("Error in handler method")
                    # pass

            reaction = f":{reaction}:"
            if related_alert:
                # Enrich the alert with reaction information
                enrichments_bl = EnrichmentsBl(self.context_manager.tenant_id)
                enrichments_bl.enrich_entity(
                    related_alert.fingerprint,
                    enrichments={
                        "slack_user_email": user_email,
                        "slack_message": message,
                        "slack_link": message_link,
                        "slack_reaction": reaction,
                        "slack_reaction_timestamp": event.get("event_time"),
                    },
                    action_type=ActionType.SLACK_EMOJI_ADDED,
                    action_callee="system",
                    action_description=f"Slack emoji '{emoji.emojize(reaction)}' added by {user_email}",
                    audit_enabled=True,
                )
                self.logger.info(
                    f"Successfully enriched alert with reaction: {reaction}"
                )
                return {
                    "status": "success",
                    "event_type": "reaction_added",
                    "reaction": reaction,
                }
            else:
                self.logger.info("No related alert found for the reaction")
                return {"status": "ignored", "reason": "No related alert found"}

        except Exception as e:
            self.logger.error(
                f"Error in reaction event handler: {str(e)}", exc_info=True
            )
            return {"status": "error", "error": str(e)}

    async def _handle_message_event(self, event: dict, event_data: dict):
        """
        Handle message events from Slack including replies and comments.

        Args:
            event (dict): The Slack event payload
            event_data (dict): Basic event metadata

        Returns:
            dict: Response with status and details
        """
        self.logger.info("Handling message event")

        try:
            # Extract message details
            message_event = event.get("event", {})
            user_id = message_event.get("user")
            channel = message_event.get("channel")
            ts = message_event.get("ts")
            thread_ts = message_event.get("thread_ts")
            message_text = message_event.get("text", "")

            # Skip bot messages
            if (
                message_event.get("bot_id")
                or message_event.get("subtype") == "bot_message"
            ):
                self.logger.info("Ignoring bot message")
                return {"status": "ignored", "reason": "Bot message"}

            if not all([user_id, channel, ts]):
                self.logger.warning("Missing required fields for message event")
                return {"status": "error", "reason": "Missing required fields"}

            # Get user email
            try:
                user_email = self._get_user_email(user_id)
            except Exception as e:
                self.logger.error(f"Failed to get user email: {str(e)}")
                user_email = f"unknown_user_{user_id}"

            # Determine if this is a thread reply
            is_thread_reply = thread_ts is not None and ts != thread_ts

            # Create message link for the parent message if it's a reply
            if is_thread_reply:
                parent_message_link = f"https://slack.com/archives/{channel}/p{thread_ts.replace('.', '')}"
                current_message_link = (
                    f"https://slack.com/archives/{channel}/p{ts.replace('.', '')}"
                )

                # Query for related alert using the parent message
                related_alert, _ = await self._query_related_alert(parent_message_link)

                if related_alert:
                    # Enrich the alert with reply information
                    enrichments_bl = EnrichmentsBl(self.context_manager.tenant_id)
                    enrichments_bl.enrich_entity(
                        related_alert.fingerprint,
                        enrichments={
                            "slack_reply_user_email": user_email,
                            "slack_reply_message": message_text,
                            "slack_reply_link": current_message_link,
                            "slack_reply_timestamp": event.get("event_time"),
                        },
                        action_type=ActionType.SLACK_REPLY_ADDED,
                        action_callee="system",
                        action_description=f"Slack reply added by {user_email}",
                        audit_enabled=True,
                    )
                    self.logger.info("Successfully enriched alert with thread reply")
                    return {
                        "status": "success",
                        "event_type": "message_reply",
                        "message": message_text,
                    }
                else:
                    self.logger.info("No related alert found for the thread reply")
                    return {"status": "ignored", "reason": "No related alert found"}
            else:
                # It's a new message, not a reply
                # In most cases, we might not need to process new messages unless they're bot-triggered
                self.logger.info("New message detected, not processing further")
                return {
                    "status": "ignored",
                    "reason": "Not a reply to a managed message",
                }

        except Exception as e:
            self.logger.error(
                f"Error in message event handler: {str(e)}", exc_info=True
            )
            return {"status": "error", "error": str(e)}

    async def _handle_mention_event(self, event: dict, event_data: dict):
        """
        Handle app_mention events from Slack.

        Args:
            event (dict): The Slack event payload
            event_data (dict): Basic event metadata

        Returns:
            dict: Response with status and details
        """
        self.logger.info("Handling app mention event")

        try:
            # Extract mention details
            mention_event = event.get("event", {})
            user_id = mention_event.get("user")
            channel = mention_event.get("channel")
            ts = mention_event.get("ts")
            text = mention_event.get("text", "")

            if not all([user_id, channel, ts]):
                self.logger.warning("Missing required fields for mention event")
                return {"status": "error", "reason": "Missing required fields"}

            # Get user email
            try:
                user_email = self._get_user_email(user_id)
            except Exception:
                user_email = f"unknown_user_{user_id}"
                self.logger.exception(
                    "Failed to get user email",
                    extra={
                        "user_id": user_id,
                        "user_email": user_email,
                    },
                )

            # Process commands in the mention
            # This could be parsing text for commands like "status", "help", etc.
            command = self._parse_mention_command(text)
            self.logger.info(f"Extracted mention command: {command}")
            if command:
                # Handle the command
                # This would typically send a message back to the channel
                response = await self._process_mention_command(
                    command, channel, user_id, ts
                )
                self.logger.info(
                    f"Processed mention command: {command}",
                    extra={
                        "response": response,
                    },
                )
                return {
                    "status": "success",
                    "event_type": "app_mention",
                    "command": command,
                }
            else:
                # No recognizable command, maybe send help info
                self._notify(
                    message=f"Hello <@{user_id}>! I didn't recognize that command. Try 'help' for a list of commands.",
                    channel=channel,
                    thread_timestamp=ts,
                )
                return {
                    "status": "success",
                    "event_type": "app_mention",
                    "action": "help_sent",
                }

        except Exception as e:
            self.logger.error(
                f"Error in mention event handler: {str(e)}", exc_info=True
            )
            return {"status": "error", "error": str(e)}

    async def _handle_file_event(self, event: dict, event_data: dict):
        """
        Handle file_shared events from Slack.

        Args:
            event (dict): The Slack event payload
            event_data (dict): Basic event metadata

        Returns:
            dict: Response with status and details
        """
        self.logger.info("Handling file shared event")

        try:
            # Extract file details
            file_event = event.get("event", {})
            user_id = file_event.get("user_id")
            file_id = file_event.get("file_id")

            if not all([user_id, file_id]):
                self.logger.warning("Missing required fields for file event")
                return {"status": "error", "reason": "Missing required fields"}

            # Get file info (would need a new method)
            try:
                file_info = self._get_file_info(file_id)
            except Exception as e:
                self.logger.error(f"Failed to get file info: {str(e)}")
                return {
                    "status": "error",
                    "error": f"Failed to get file info: {str(e)}",
                }

            # Process the file as needed
            self.logger.info(f"File shared: {file_info.get('name')}")
            return {
                "status": "success",
                "event_type": "file_shared",
                "file_id": file_id,
            }

        except Exception as e:
            self.logger.error(f"Error in file event handler: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _get_user_email(self, user_id):
        """
        Get user email from Slack user ID.

        Args:
            user_id (str): Slack user ID

        Returns:
            str: User email address

        Raises:
            ProviderException: If user info cannot be retrieved
        """
        self.logger.debug(f"Getting email for user ID: {user_id}")

        try:
            response = requests.get(
                f"{self.SLACK_API}/users.info",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}"
                },
                params={"user": user_id},
            )

            if not response.ok:
                error_msg = f"Failed to get user info. Status: {response.status_code}, Response: {response.text}"
                self.logger.error(error_msg)
                raise ProviderException(error_msg)

            response_data = response.json()
            ok = response_data.get("ok")

            if not ok:
                error_msg = f"Failed to get user info: {response_data.get('error')}"
                self.logger.error(error_msg)
                raise ProviderException(error_msg)

            user = response_data.get("user", {})
            profile = user.get("profile", {})
            email = profile.get("email")

            if not email:
                self.logger.warning(f"No email found for user {user_id}")
                return f"no-email-{user_id}"

            self.logger.debug(f"Successfully retrieved email for user {user_id}")
            return email

        except Exception as e:
            self.logger.error(f"Error getting user email: {str(e)}", exc_info=True)
            raise ProviderException(f"Failed to get user info: {str(e)}")

    def _get_message(self, event):
        """
        Get message text from Slack.

        Args:
            event (dict): Slack event containing channel and timestamp info

        Returns:
            str: Message text

        Raises:
            ProviderException: If message cannot be retrieved
        """
        self.logger.debug("Getting message content")

        try:
            channel = event.get("event", {}).get("item", {}).get("channel")
            ts = event.get("event", {}).get("item", {}).get("ts")

            if not channel or not ts:
                error_msg = "Missing channel or timestamp in event"
                self.logger.error(error_msg)
                raise ProviderException(error_msg)

            response = requests.get(
                f"{self.SLACK_API}/conversations.history",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}"
                },
                params={
                    "channel": channel,
                    "latest": ts,
                    "inclusive": True,
                    "limit": 1,
                },
            )

            if not response.ok:
                error_msg = f"Failed to get message. Status: {response.status_code}, Response: {response.text}"
                self.logger.error(error_msg)
                raise ProviderException(error_msg)

            response_data = response.json()
            ok = response_data.get("ok")

            if not ok:
                error_msg = f"Failed to get message: {response_data.get('error')}"
                self.logger.error(error_msg)
                raise ProviderException(error_msg)

            messages = response_data.get("messages", [])

            if not messages:
                self.logger.warning("No messages found")
                return ""

            message_text = messages[0].get("text", "")
            self.logger.debug("Successfully retrieved message content")
            return message_text

        except Exception as e:
            self.logger.error(f"Error getting message: {str(e)}", exc_info=True)
            raise ProviderException(f"Failed to get message: {str(e)}")

    def _get_file_info(self, file_id):
        """
        Get file information from Slack.

        Args:
            file_id (str): Slack file ID

        Returns:
            dict: File information

        Raises:
            ProviderException: If file info cannot be retrieved
        """
        self.logger.debug(f"Getting info for file ID: {file_id}")

        try:
            response = requests.get(
                f"{self.SLACK_API}/files.info",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}"
                },
                params={"file": file_id},
            )

            if not response.ok:
                error_msg = f"Failed to get file info. Status: {response.status_code}, Response: {response.text}"
                self.logger.error(error_msg)
                raise ProviderException(error_msg)

            response_data = response.json()
            ok = response_data.get("ok")

            if not ok:
                error_msg = f"Failed to get file info: {response_data.get('error')}"
                self.logger.error(error_msg)
                raise ProviderException(error_msg)

            file_info = response_data.get("file", {})
            self.logger.debug(f"Successfully retrieved info for file {file_id}")
            return file_info

        except Exception as e:
            self.logger.error(f"Error getting file info: {str(e)}", exc_info=True)
            raise ProviderException(f"Failed to get file info: {str(e)}")

    def _parse_mention_command(self, text):
        """
        Parse command from app mention text.

        Args:
            text (str): Message text

        Returns:
            dict: Command details or None
        """
        self.logger.debug(f"Parsing mention command from: {text}")

        try:
            # Remove the app mention part (e.g., "<@U12345> command")
            mention_pattern = r"<@[A-Z0-9]+>"
            import re

            clean_text = re.sub(mention_pattern, "", text).strip()

            # Basic command parsing
            if not clean_text:
                return None

            # Split by spaces
            parts = clean_text.split()
            command = parts[0].lower()

            # Return with arguments if any
            if len(parts) > 1:
                return {"command": command, "args": parts[1:]}
            else:
                return {"command": command, "args": []}

        except Exception as e:
            self.logger.error(f"Error parsing mention command: {str(e)}", exc_info=True)
            return None

    async def _process_mention_command(self, command, channel, user_id, ts):
        """
        Process command from app mention.

        Args:
            command (dict): Command details
            channel (str): Channel ID
            user_id (str): User ID
            ts (str): Message timestamp

        Returns:
            dict: Response details
        """
        self.logger.info(f"Processing mention command: {command}")

        try:
            cmd = command.get("command")
            args = command.get("args", [])

            if cmd == "help":
                # Send help information
                self._notify(
                    message="Available commands:\n• `help` - Show this help\n• `status` - Show system status\n• `alerts` - Show recent alerts",
                    channel=channel,
                    thread_timestamp=ts,
                )
                return {"status": "success", "command": "help"}

            elif cmd == "status":
                # Send status information
                self._notify(
                    message="All systems operational! 🟢",
                    channel=channel,
                    thread_timestamp=ts,
                )
                return {"status": "success", "command": "status"}

            elif cmd == "alerts":
                # Send recent alerts
                # You would need to implement a method to get recent alerts
                alerts_count = 5  # Default
                if args and args[0].isdigit():
                    alerts_count = min(int(args[0]), 10)  # Limit to 10

                recent_alerts, _ = query_last_alerts(
                    tenant_id=self.context_manager.tenant_id, limit=alerts_count
                )

                if recent_alerts:
                    alerts_text = f"Last {len(recent_alerts)} alerts:\n"
                    for idx, alert in enumerate(recent_alerts, 1):
                        alerts_text += f"{idx}. {alert.alert_name} - {alert.status}\n"
                else:
                    alerts_text = "No recent alerts found."

                self._notify(message=alerts_text, channel=channel, thread_timestamp=ts)
                return {"status": "success", "command": "alerts"}

            else:
                # Unknown command
                self._notify(
                    message=f"Unknown command: `{cmd}`. Type `help` for available commands.",
                    channel=channel,
                    thread_timestamp=ts,
                )
                return {"status": "error", "reason": "Unknown command"}

        except Exception as e:
            self.logger.error(
                f"Error processing mention command: {str(e)}", exc_info=True
            )
            # Notify the user about the error
            self._notify(
                message=f"Error processing command: {str(e)}",
                channel=channel,
                thread_timestamp=ts,
            )
            return {"status": "error", "error": str(e)}

    async def _query_related_alert(self, message_link):
        """
        Query for alerts related to a Slack message.

        Args:
            message_link (str): Slack message link

        Returns:
            tuple: (alert, _) - The alert object and unused pagination info
        """
        self.logger.debug(f"Querying for alerts related to message: {message_link}")

        try:
            related_alert, _ = query_last_alerts(
                tenant_id=self.context_manager.tenant_id,
                limit=1,
                cel=f"slack_link == '{message_link}'",
            )

            if related_alert:
                self.logger.info(f"Found related alert: {related_alert[0].fingerprint}")
                return related_alert[0]
            else:
                self.logger.info("No related alert found")
                return None

        except Exception as e:
            self.logger.error(f"Error querying related alert: {str(e)}", exc_info=True)
            return None, None


def original_main():
    # Output debug messages
    import logging

    from keep.providers.providers_factory import ProvidersFactory

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    # slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    # Initalize the provider and provider config
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    access_token = os.environ.get("SLACK_ACCESS_TOKEN")
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    if access_token:
        config = {
            "authentication": {"access_token": access_token},
        }
    elif webhook_url:
        config = {
            "authentication": {"webhook_url": webhook_url},
        }
    # you need some creds
    else:
        raise Exception("please provide either access token or webhook url")

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="slack-keephq",
        provider_type="slack",
        provider_config=config,
    )
    provider.notify(
        channel="C04P7QSG692",
        attachments=[
            {
                "fallback": "Plain-text summary of the attachment.",
                "color": "#2eb886",
                "title": "Slack API Documentation",
                "title_link": "https://api.slack.com/",
                "text": "Optional text that appears within the attachment",
                "footer": "Slack API",
                "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png",
            }
        ],
    )


def mock_oauth2_install():
    import asyncio
    import json
    import logging
    import unittest.mock as mock

    # Setup logging
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    logger = logging.getLogger(__name__)

    # Create a mock Slack API response
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "ok": True,
        "access_token": "xoxb-mock-access-token-12345",
        "token_type": "bot",
        "scope": "channels:history,chat:write,reactions:read",
        "team": {"name": "T059W3GTFJA"},
        "is_enterprise_install": False,
    }

    # Run the installation with patched request
    async def run_installation():
        # Set provider type
        provider_type = "slack"

        # Prepare OAuth payload
        provider_info = {"code": "mock_oauth_code_12345"}

        # Get actual dependencies
        authenticated_entity = AuthenticatedEntity(
            tenant_id="singletenant", email="your_email@example.com"
        )
        session = get_session()

        # Patch only the requests.post call to Slack
        with mock.patch("requests.post", return_value=mock_response):
            try:
                # Call the actual installation function
                result = await install_provider_oauth2(
                    provider_type=provider_type,
                    provider_info=provider_info,
                    authenticated_entity=authenticated_entity,
                    session=session,
                )

                logger.info("Installation successful!")
                if hasattr(result, "body"):
                    content = json.loads(result.body)
                    logger.info(f"Provider ID: {content.get('id')}")

                return result
            except Exception as e:
                logger.error(f"Installation failed: {str(e)}")
                raise

    # Run the async function
    result = asyncio.run(run_installation())
    print(result)
    print("Installation complete!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        original_main()

    #
    else:
        mock_oauth2_install()
