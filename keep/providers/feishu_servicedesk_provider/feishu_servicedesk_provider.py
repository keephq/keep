"""
FeishuServicedeskProvider is a class that implements the BaseProvider interface for Feishu Service Desk tickets.
"""

import dataclasses
import datetime
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlencode

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class FeishuServicedeskProviderAuthConfig:
    """Feishu Service Desk authentication configuration."""

    app_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Feishu App ID",
            "sensitive": False,
            "documentation_url": "https://open.feishu.cn/document/ukTMukTMukTM/ukDNz4SO0MjL5QzM/auth-v3/auth/tenant_access_token_internal",
        }
    )

    app_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Feishu App Secret",
            "sensitive": True,
            "documentation_url": "https://open.feishu.cn/document/ukTMukTMukTM/ukDNz4SO0MjL5QzM/auth-v3/auth/tenant_access_token_internal",
        }
    )

    host: HttpsUrl = dataclasses.field(
        metadata={
            "required": False,
            "description": "Feishu server host",
            "sensitive": False,
            "hint": "https://open.feishu.cn",
            "validation": "https_url",
        },
        default="https://open.feishu.cn",
    )

    helpdesk_id: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Helpdesk ID. Leave empty to use the default helpdesk.",
            "sensitive": False,
            "hint": "Leave empty to use default helpdesk",
        },
        default="",
    )

    helpdesk_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Helpdesk token required for creating tickets.",
            "sensitive": True,
            "hint": "Required for creating tickets. Get from Feishu Service Desk settings",
        },
        default="",
    )

    default_open_id: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Default user Open ID used when creating tickets if not specified.",
            "sensitive": False,
            "hint": "Default user open_id for creating tickets",
        },
        default="",
    )


class FeishuServicedeskProvider(BaseProvider):
    """Enrich alerts with Feishu Service Desk tickets."""

    OAUTH2_URL = None  # Feishu Service Desk does not use OAuth2 authentication
    PROVIDER_CATEGORY = ["Ticketing"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="helpdesk:ticket",
            description="Permission to read tickets",
            mandatory=True,
            alias="Read tickets",
        ),
        ProviderScope(
            name="helpdesk:ticket:create",
            description="Permission to create tickets",
            mandatory=True,
            alias="Create tickets",
        ),
        ProviderScope(
            name="helpdesk:ticket:update",
            description="Permission to update tickets",
            mandatory=False,
            alias="Update tickets",
        ),
        ProviderScope(
            name="helpdesk:agent",
            description="Permission to read agent information",
            mandatory=False,
            alias="Read agents",
        ),
        ProviderScope(
            name="contact:user.base:readonly",
            description="Permission to read user information",
            mandatory=False,
            alias="Read user info",
        ),
    ]

    PROVIDER_METHODS = []

    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_DISPLAY_NAME = "Feishu Service Desk"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._host = None
        self._access_token = None
        self._token_expiry = None

    def validate_scopes(self):
        """Validate that the provider has the required scopes."""
        try:
            # Attempt to obtain an access token to validate the credentials
            access_token = self.__get_access_token()
            if not access_token:
                scopes = {
                    scope.name: "Failed to authenticate with Feishu - wrong credentials"
                    for scope in FeishuServicedeskProvider.PROVIDER_SCOPES
                }
                return scopes

            # If the token was obtained successfully, mark all scopes as granted
            # Note: Feishu permissions are configured when the app is created, so this validation is simplified
            scopes = {
                scope.name: True
                for scope in FeishuServicedeskProvider.PROVIDER_SCOPES
            }
            return scopes
        except Exception as e:
            self.logger.exception("Failed to validate scopes")
            scopes = {
                scope.name: f"Failed to authenticate with Feishu: {e}"
                for scope in FeishuServicedeskProvider.PROVIDER_SCOPES
            }
            return scopes

    def validate_config(self):
        self.authentication_config = FeishuServicedeskProviderAuthConfig(
            **self.config.authentication
        )

    @property
    def feishu_host(self) -> str:
        if self._host is not None:
            return self._host
        host = self.authentication_config.host
        if not host.startswith("https://") and not host.startswith("http://"):
            host = f"https://{host}"
        self._host = host
        return self._host

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def __get_access_token(self) -> str:
        """Retrieve the Feishu tenant access token."""
        try:
            # Reuse the cached token if it is still valid
            import datetime
            if self._access_token and self._token_expiry:
                if datetime.datetime.now() < self._token_expiry:
                    return self._access_token

            url = urljoin(
                self.feishu_host,
                "/open-apis/auth/v3/tenant_access_token/internal/",
            )

            payload = {
                "app_id": self.authentication_config.app_id,
                "app_secret": self.authentication_config.app_secret,
            }

            response = requests.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            if result.get("code") != 0:
                raise ProviderException(
                    f"Failed to get access token: {result.get('msg')}"
                )

            self._access_token = result.get("tenant_access_token")
            # Set the token expiration time (expire five minutes earlier than the official TTL)
            expire_seconds = result.get("expire", 7200) - 300
            self._token_expiry = datetime.datetime.now() + datetime.timedelta(
                seconds=expire_seconds
            )

            return self._access_token
        except Exception as e:
            raise ProviderException(f"Failed to get access token: {e}")

    def __get_headers(self, use_helpdesk_auth: bool = False):
        """
        Helper method to build the headers for Feishu API requests.
        
        Args:
            use_helpdesk_auth (bool): When True and a helpdesk_token is configured,
                include the additional helpdesk authentication header.

        Note: Helpdesk APIs require two authentication headers:
              1. Authorization: Bearer {tenant_access_token}
              2. X-Lark-Helpdesk-Authorization: base64(helpdesk_id:helpdesk_token)
        """
        headers = {
            "Content-Type": "application/json; charset=utf-8",
        }
        
        # Always add the standard tenant_access_token authentication
        access_token = self.__get_access_token()
        headers["Authorization"] = f"Bearer {access_token}"
        
        # Add the helpdesk-specific authentication header when requested
        if (use_helpdesk_auth and 
            self.authentication_config.helpdesk_id and 
            self.authentication_config.helpdesk_token):
            import base64
            auth_string = f"{self.authentication_config.helpdesk_id}:{self.authentication_config.helpdesk_token}"
            encoded = base64.b64encode(auth_string.encode()).decode()
            headers["X-Lark-Helpdesk-Authorization"] = encoded
            self.logger.info(f"Using dual authentication: Bearer token + Helpdesk auth")
        
        return headers

    def __get_url(self, path: str):
        """
        Helper method to build the url for Feishu API requests.
        """
        return urljoin(self.feishu_host, path)

    def __create_ticket(
        self,
        title: str,
        description: str = "",
        customized_fields: List[dict] = None,
        category_id: Optional[str] = None,
        priority: Optional[int] = None,
        tags: Optional[List[str]] = None,
        open_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        **kwargs: dict,
    ):
        """
        Helper method to create a ticket in Feishu Service Desk (start human service).

        Note: The StartServiceTicket API requires a helpdesk token and the
              special helpdesk authentication header.
        """
        try:
            self.logger.info("Creating a ticket in Feishu Service Desk...")

            # Feishu Service Desk API: start human service
            url = self.__get_url("/open-apis/helpdesk/v1/start_service")

            # Use the enriched description as customized_info so that the first
            # message in the service desk conversation contains full context.
            if description:
                ticket_content = description
            else:
                # Fall back to a lightweight template when no description is supplied
                ticket_content = f"[Ticket Title] {title}\n\nVisit the Keep platform for more details."
            
            # Append optional metadata when provided
            if category_id:
                ticket_content += f"\n\n[Category ID] {category_id}"
            if priority:
                ticket_content += f"\n[Priority] {priority}"
            if tags:
                ticket_content += f"\n[Tags] {', '.join(tags)}"

            # Build the request payload using the Feishu API schema
            ticket_data = {
                "human_service": True,  # Enable human service
                "customized_info": ticket_content,  # Include the enriched content
            }

            # An open_id is required for the request
            if open_id:
                ticket_data["open_id"] = open_id
            elif kwargs.get("open_id"):
                ticket_data["open_id"] = kwargs.get("open_id")
            elif self.authentication_config.default_open_id:
                ticket_data["open_id"] = self.authentication_config.default_open_id
                self.logger.info(f"Using default open_id: {self.authentication_config.default_open_id}")
            else:
                raise ProviderException(
                    "open_id is required to create a ticket. "
                    "Please provide open_id parameter or set default_open_id in configuration."
                )

            # Assign specific agents when supplied
            if agent_id:
                ticket_data["appointed_agents"] = [agent_id]

            # Log the request for debugging purposes
            self.logger.info(f"Creating ticket with URL: {url}")
            self.logger.info(f"Request data: {json.dumps(ticket_data, ensure_ascii=False)}")
            
            # Use the helpdesk-specific authentication header
            response = requests.post(
                url=url,
                json=ticket_data,
                headers=self.__get_headers(use_helpdesk_auth=True),
            )

            # Log the response diagnostics
            self.logger.info(f"Response status: {response.status_code}")
            self.logger.info(f"Response headers: {dict(response.headers)}")
            
            # Capture the raw text for easier troubleshooting
            response_text = response.text
            self.logger.info(f"Response text (first 500 chars): {response_text[:500]}")
            
            # Parse the JSON response
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON response: {e}")
                self.logger.error(f"Full response text: {response_text}")
                raise ProviderException(
                    f"Failed to parse Feishu API response. Status: {response.status_code}, "
                    f"Response: {response_text[:200]}"
                )
            
            # Raise for HTTP errors
            try:
                response.raise_for_status()
            except Exception as e:
                self.logger.exception(
                    "Failed to create a ticket", extra={"result": result, "status": response.status_code}
                )
                raise ProviderException(
                    f"Failed to create a ticket. HTTP {response.status_code}: {result}"
                )

            # Validate the Feishu API response
            if result.get("code") != 0:
                error_msg = result.get("msg", "Unknown error")
                self.logger.error(f"Feishu API returned error code {result.get('code')}: {error_msg}")
                raise ProviderException(
                    f"Failed to create ticket: {error_msg} (code: {result.get('code')})"
                )

            self.logger.info("Created a ticket in Feishu Service Desk!")
            
            # Return the full payload for downstream processing
            ticket_data = result.get("data", {})
            ticket_id = ticket_data.get("ticket_id")
            chat_id = ticket_data.get("chat_id")
            
            # Send the detailed description via the service desk messaging API when needed
            if ticket_id and description and len(description) > 200:
                try:
                    success = self.__send_ticket_message(ticket_id, description)
                    if success:
                        self.logger.info("✅ Sent detailed description via ticket messages API")
                    else:
                        self.logger.warning("⚠️ Failed to send message, but ticket created successfully")
                        self.logger.info("Enriched content is in customized_info")
                except Exception as e:
                    # Failure to send the follow-up message does not invalidate ticket creation
                    self.logger.warning(f"Failed to send ticket message: {e}")
                    self.logger.info("Enriched content is in customized_info")
            else:
                self.logger.info("✅ Full enriched content sent via customized_info")
            
            return {
                "ticket": ticket_data,
                "ticket_id": ticket_id,
                "chat_id": chat_id,
                # These identifiers allow Keep alerts/incidents to remain in sync with Feishu
                "feishu_ticket_id": ticket_id,
                "feishu_chat_id": chat_id,
            }
        except Exception as e:
            raise ProviderException(f"Failed to create a ticket: {e}")

    def __build_rich_card_content(self, enriched_text: str) -> list:
        """
        Convert enriched text to the Feishu rich text card format with clickable links.

        Args:
            enriched_text: Enriched description text.

        Returns:
            list: Content array compatible with the Feishu post schema.
        """
        content_lines = []
        
        lines = enriched_text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            i += 1
            
            # Skip empty lines and separators
            if not line or line.startswith('━'):
                continue
            
            # Detect lines where the next line contains a URL
            if i < len(lines) and (lines[i].strip().startswith('http://') or lines[i].strip().startswith('https://')):
                # Current line is the label, next line is the URL
                label = line
                url = lines[i].strip()
                i += 1
                
                label_lower = label.lower()
                url_lower = url.lower()

                # Determine an appropriate anchor label based on the description
                if (
                    "alert" in label_lower and "detail" in label_lower
                    or "alert-his-events" in url_lower
                    or "nalert" in url_lower
                ):
                    link_text = "🔔 View Alert Details"
                elif "keep" in label_lower and "event" in label_lower:
                    link_text = "📱 View Keep Event"
                elif "incident" in label_lower:
                    link_text = "🎯 View Incident"
                elif "generator" in label_lower:
                    link_text = "⚙️ Open Generator"
                elif "playbook" in label_lower or "runbook" in label_lower:
                    link_text = "📖 View Playbook"
                else:
                    link_text = "🔗 Open Link"
                
                # Build a clickable hyperlink segment
                content_lines.append([
                    {
                        "tag": "text",
                        "text": label + " "
                    },
                    {
                        "tag": "a",
                        "text": link_text,
                        "href": url
                    }
                ])
            # Detect lines that are URLs without labels
            elif line.startswith('http://') or line.startswith('https://'):
                # Choose a friendly caption based on the URL
                if 'alerts/feed' in line:
                    link_text = "📱 View Keep Event Details"
                elif '/incidents/' in line:
                    link_text = "🎯 View Incident Details"
                elif 'alert-his-events' in line or 'nalert' in line:
                    link_text = "🔔 View Alert Details"
                elif 'prometheus' in line or 'grafana' in line:
                    link_text = "📊 Open Monitoring Dashboard"
                else:
                    link_text = "🔗 Open Link"
                
                content_lines.append([{
                    "tag": "a",
                    "text": link_text,
                    "href": line
                }])
            # Section headers containing emojis or special characters
            elif any(emoji in line for emoji in ['📋', '🔗', '📍', '🔍', '⚠️', '📝']):
                content_lines.append([{
                    "tag": "text",
                    "text": line,
                    "un_escape": True
                }])
            else:
                # Regular text lines
                if line:
                    content_lines.append([{
                        "tag": "text",
                        "text": line
                    }])

        # Fallback to the raw text when no content blocks were generated
        if not content_lines:
            content_lines = [[{
                "tag": "text",
                "text": enriched_text
            }]]
        
        return content_lines

    def __send_ticket_message(self, ticket_id: str, content: str):
        """
        Send a message to a helpdesk ticket using the Feishu Service Desk message API.

        Args:
            ticket_id: Ticket ID.
            content: Message body (typically the enriched description).

        Returns:
            bool: True when the message is sent successfully.

        API: POST /open-apis/helpdesk/v1/tickets/{ticket_id}/messages
        """
        try:
            self.logger.info(f"Sending rich card message to ticket {ticket_id}...")
            
            # Feishu Service Desk message API endpoint
            url = self.__get_url(f"/open-apis/helpdesk/v1/tickets/{ticket_id}/messages")
            
            # Build the rich text card payload
            # Reference: https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/helpdesk-v1/ticket-message/create
            card_content = self.__build_rich_card_content(content)
            
            message_data = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": "📋 Incident Details",
                            "content": card_content
                        }
                    }
                }
            }
            
            self.logger.info(f"Sending ticket message to URL: {url}")
            
            # The service desk messaging API requires both authentication headers
            response = requests.post(
                url=url,
                json=message_data,
                headers=self.__get_headers(use_helpdesk_auth=True),  # Ensure helpdesk authentication is supplied
            )
            
            self.logger.info(f"Ticket message response: {response.status_code}")
            
            # Attempt to parse the response payload
            try:
                result = response.json()
                self.logger.info(f"Response: {result}")
            except:
                result = {"text": response.text}
            
            if response.status_code == 200:
                if result.get("code") == 0:
                    self.logger.info("✅ Message sent successfully to ticket")
                    return True
                else:
                    self.logger.warning(f"Failed to send ticket message: {result.get('msg')}")
                    return False
            else:
                self.logger.warning(f"Failed to send ticket message: HTTP {response.status_code}, {result}")
                return False
                
        except Exception as e:
            self.logger.warning(f"Exception while sending ticket message: {e}")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            return False

    def __update_ticket(
        self,
        ticket_id: str,
        status: Optional[int] = None,
        customized_fields: List[dict] = None,
        **kwargs: dict,
    ):
        """Helper method to update a ticket in Feishu Service Desk."""
        try:
            self.logger.info(f"Updating ticket {ticket_id} in Feishu Service Desk...")

            url = self.__get_url(f"/open-apis/helpdesk/v1/tickets/{ticket_id}")

            update_data = {}

            # Update ticket status
            if status is not None:
                update_data["status"] = status

            # Update custom fields
            if customized_fields:
                update_data["customized_fields"] = customized_fields

            response = requests.patch(
                url=url,
                json=update_data,
                headers=self.__get_headers(),
            )

            # Log the response for debugging
            self.logger.info(f"Update response status: {response.status_code}")
            response_text = response.text
            self.logger.info(f"Update response text: {response_text[:500]}")

            # Parse the response body
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse update response: {e}")
                self.logger.error(f"Full response: {response_text}")
                raise ProviderException(
                    f"Failed to parse update response. Status: {response.status_code}, "
                    f"Response: {response_text[:200]}"
                )

            # Propagate HTTP errors
            try:
                response.raise_for_status()
            except Exception as e:
                self.logger.exception(
                    "Failed to update a ticket", 
                    extra={"result": result, "status": response.status_code}
                )
                raise ProviderException(
                    f"Failed to update a ticket. HTTP {response.status_code}: {result}"
                )

            # Validate the Feishu API response payload
            if result.get("code") != 0:
                error_msg = result.get("msg", "Unknown error")
                self.logger.error(f"Feishu API update error: code={result.get('code')}, msg={error_msg}")
                raise ProviderException(
                    f"Failed to update ticket: {error_msg} (code: {result.get('code')})"
                )

            self.logger.info("Updated a ticket in Feishu Service Desk!")
            return {"ticket": result.get("data", {})}
        except ProviderException:
            raise
        except Exception as e:
            raise ProviderException(f"Failed to update a ticket: {e}")

    def __get_ticket(self, ticket_id: str):
        """
        Helper method to retrieve ticket details.

        Note: The Feishu Service Desk ticket detail API also requires the
        helpdesk-specific authentication header.
        """
        try:
            self.logger.info(f"Fetching ticket {ticket_id} from Feishu Service Desk...")

            url = self.__get_url(f"/open-apis/helpdesk/v1/tickets/{ticket_id}")

            # Use the helpdesk-specific authentication header
            response = requests.get(
                url=url,
                headers=self.__get_headers(use_helpdesk_auth=True),
            )

            # Log the response for debugging
            self.logger.info(f"Get ticket response status: {response.status_code}")
            response_text = response.text
            self.logger.info(f"Get ticket response: {response_text[:500]}")

            # Parse the response body
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse get ticket response: {e}")
                # Return minimal information when full details are unavailable
                self.logger.warning("Could not fetch ticket details, using minimal info")
                return {
                    "ticket_id": ticket_id,
                    "ticket_url": f"{self.feishu_host}/helpdesk/ticket/{ticket_id}"
                }

            # Gracefully handle authorization and missing resources
            if response.status_code == 401 or response.status_code == 404:
                # The lookup API may be unavailable; return minimal information
                self.logger.warning(f"Ticket detail API returned {response.status_code}, using basic info")
                return {
                    "ticket_id": ticket_id,
                    "ticket_url": f"{self.feishu_host}/helpdesk/ticket/{ticket_id}"
                }

            response.raise_for_status()

            if result.get("code") != 0:
                self.logger.warning(f"Failed to get ticket details: {result.get('msg')}")
                # Return minimal information rather than raising an exception
                return {
                    "ticket_id": ticket_id,
                    "ticket_url": f"{self.feishu_host}/helpdesk/ticket/{ticket_id}"
                }

            self.logger.info("Fetched ticket from Feishu Service Desk!")
            return result.get("data", {})
        except Exception as e:
            # Fall back to minimal information when the API call fails
            self.logger.warning(f"Could not fetch ticket details: {e}, returning basic info")
            return {
                "ticket_id": ticket_id,
                "ticket_url": f"{self.feishu_host}/helpdesk/ticket/{ticket_id}"
            }

    # ==================== Provider Methods (for frontend) ====================

    def get_helpdesks(self) -> Dict[str, Any]:
        """
        Retrieve the list of helpdesks (used for frontend dropdowns).

        Returns:
            dict: Helpdesk metadata, including IDs and names.

        Note: ⚠️ This endpoint may vary between tenants. If the call fails,
              adjust the endpoint path or fetch the data via an alternative API.
        """
        try:
            self.logger.info("Fetching helpdesks list...")

            url = self.__get_url("/open-apis/helpdesk/v1/helpdesks")

            response = requests.get(
                url=url,
                headers=self.__get_headers(),
            )

            response.raise_for_status()

            result = response.json()
            if result.get("code") != 0:
                raise ProviderException(
                    f"Failed to get helpdesks: {result.get('msg')}"
                )

            helpdesks = result.get("data", {}).get("helpdesks", [])
            
            # Normalize the data for client consumption
            formatted_helpdesks = [
                {
                    "id": helpdesk.get("id"),
                    "name": helpdesk.get("name"),
                    "avatar": helpdesk.get("avatar"),
                }
                for helpdesk in helpdesks
            ]

            self.logger.info(f"Fetched {len(formatted_helpdesks)} helpdesks")
            return {
                "helpdesks": formatted_helpdesks,
                "total": len(formatted_helpdesks)
            }
        except Exception as e:
            self.logger.exception("Failed to get helpdesks")
            raise ProviderException(f"Failed to get helpdesks: {e}")

    def get_agents(self, helpdesk_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve the list of helpdesk agents (used for frontend dropdowns).

        Args:
            helpdesk_id (str): Helpdesk ID (optional — defaults to the configured helpdesk).

        Returns:
            dict: Agent metadata, including IDs and names.

        Note: ⚠️ This API may require helpdesk authentication or an alternative endpoint.
              If it fails, try:
              1. Calling with use_helpdesk_auth=True.
              2. Falling back to the contact API to obtain user information.
        """
        try:
            helpdesk_id = helpdesk_id or self.authentication_config.helpdesk_id
            if not helpdesk_id:
                # If no helpdesk ID is supplied, fall back to the first available helpdesk
                helpdesks = self.get_helpdesks()
                if helpdesks.get("helpdesks"):
                    helpdesk_id = helpdesks["helpdesks"][0]["id"]
                else:
                    raise ProviderException("No helpdesk found")

            self.logger.info(f"Fetching agents for helpdesk {helpdesk_id}...")

            url = self.__get_url(f"/open-apis/helpdesk/v1/agents")
            params = {"helpdesk_id": helpdesk_id}

            response = requests.get(
                url=url,
                params=params,
                headers=self.__get_headers(),
            )

            response.raise_for_status()

            result = response.json()
            if result.get("code") != 0:
                raise ProviderException(
                    f"Failed to get agents: {result.get('msg')}"
                )

            agents = result.get("data", {}).get("agents", [])
            
            # Normalize the response items
            formatted_agents = [
                {
                    "id": agent.get("user_id"),
                    "name": agent.get("name"),
                    "email": agent.get("email"),
                    "status": agent.get("status"),  # 1: online, 2: offline, 3: busy
                }
                for agent in agents
            ]

            self.logger.info(f"Fetched {len(formatted_agents)} agents")
            return {
                "agents": formatted_agents,
                "total": len(formatted_agents)
            }
        except Exception as e:
            self.logger.exception("Failed to get agents")
            raise ProviderException(f"Failed to get agents: {e}")

    def get_ticket_categories(self, helpdesk_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve ticket categories (used for frontend dropdowns).
        
        Args:
            helpdesk_id (str): Helpdesk ID (optional)
            
        Returns:
            dict: List of categories with their IDs and names
        """
        try:
            helpdesk_id = helpdesk_id or self.authentication_config.helpdesk_id
            
            self.logger.info(f"Fetching ticket categories for helpdesk {helpdesk_id}...")

            url = self.__get_url("/open-apis/helpdesk/v1/categories")
            params = {}
            if helpdesk_id:
                params["helpdesk_id"] = helpdesk_id

            response = requests.get(
                url=url,
                params=params,
                headers=self.__get_headers(),
            )

            response.raise_for_status()

            result = response.json()
            if result.get("code") != 0:
                raise ProviderException(
                    f"Failed to get categories: {result.get('msg')}"
                )

            categories = result.get("data", {}).get("categories", [])
            
            # Normalize the result for client consumption
            formatted_categories = [
                {
                    "id": category.get("category_id"),
                    "name": category.get("name"),
                    "parent_id": category.get("parent_id"),
                }
                for category in categories
            ]

            self.logger.info(f"Fetched {len(formatted_categories)} categories")
            return {
                "categories": formatted_categories,
                "total": len(formatted_categories)
            }
        except Exception as e:
            self.logger.exception("Failed to get categories")
            raise ProviderException(f"Failed to get categories: {e}")

    def get_ticket_custom_fields(self, helpdesk_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve ticket custom field definitions (used to build frontend forms).
        
        Args:
            helpdesk_id (str): Helpdesk ID (optional)
            
        Returns:
            dict: List of custom fields with their configurations
        """
        try:
            helpdesk_id = helpdesk_id or self.authentication_config.helpdesk_id
            
            self.logger.info(f"Fetching custom fields for helpdesk {helpdesk_id}...")

            url = self.__get_url("/open-apis/helpdesk/v1/ticket_customized_fields")
            params = {}
            if helpdesk_id:
                params["helpdesk_id"] = helpdesk_id

            response = requests.get(
                url=url,
                params=params,
                headers=self.__get_headers(),
            )

            response.raise_for_status()

            result = response.json()
            if result.get("code") != 0:
                raise ProviderException(
                    f"Failed to get custom fields: {result.get('msg')}"
                )

            fields = result.get("data", {}).get("customized_fields", [])
            
            # Normalize the result for client consumption
            formatted_fields = [
                {
                    "id": field.get("field_id"),
                    "name": field.get("display_name"),
                    "type": field.get("field_type"),  # text, dropdown, multi_select, etc.
                    "required": field.get("required", False),
                    "options": field.get("dropdown_allowed", []) if field.get("field_type") == "dropdown" else None,
                }
                for field in fields
            ]

            self.logger.info(f"Fetched {len(formatted_fields)} custom fields")
            return {
                "fields": formatted_fields,
                "total": len(formatted_fields)
            }
        except Exception as e:
            self.logger.exception("Failed to get custom fields")
            raise ProviderException(f"Failed to get custom fields: {e}")

    def add_ticket_comment(
        self,
        ticket_id: str,
        content: str,
        comment_type: int = 1  # 1: plain text, 2: rich text
    ) -> Dict[str, Any]:
        """
        Add a comment to a ticket.

        Args:
            ticket_id (str): Ticket ID.
            content (str): Comment body.
            comment_type (int): Comment type (1: plain text, 2: rich text).

        Returns:
            dict: Comment payload returned by Feishu.

        Note: ⚠️ This endpoint may differ between tenants. If the call fails:
              1. Verify whether another endpoint should be used.
              2. Consider sending a Service Desk message instead.
              3. Confirm whether the payload requires alternative field names (for example, msg_type).
        """
        try:
            self.logger.info(f"Adding comment to ticket {ticket_id}...")

            url = self.__get_url(f"/open-apis/helpdesk/v1/tickets/{ticket_id}/comments")

            comment_data = {
                "content": content,
                "msg_type": comment_type,
            }

            response = requests.post(
                url=url,
                json=comment_data,
                headers=self.__get_headers(),
            )

            response.raise_for_status()

            result = response.json()
            if result.get("code") != 0:
                raise ProviderException(
                    f"Failed to add comment: {result.get('msg')}"
                )

            self.logger.info("Comment added successfully!")
            return {
                "success": True,
                "comment": result.get("data", {}),
                "ticket_id": ticket_id
            }
        except Exception as e:
            self.logger.exception("Failed to add comment")
            raise ProviderException(f"Failed to add comment: {e}")

    def assign_ticket(
        self,
        ticket_id: str,
        agent_id: str,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assign a ticket to a specific agent.

        Args:
            ticket_id (str): Ticket ID.
            agent_id (str): Agent user ID.
            comment (str): Optional comment to include in the notification.

        Returns:
            dict: Result of the assignment attempt.

        Note: ⚠️ Feishu Service Desk does not currently expose an assignment API (returns 404).
              Prefer specifying appointed_agents during ticket creation. This method provides
              a best-effort notification for compatibility.
        """
        try:
            self.logger.warning(
                f"⚠️ Assign ticket API may not be available in Feishu Service Desk. "
                f"Recommend using agent_email/agent_id in ticket creation instead."
            )
            self.logger.info(f"Attempting to assign ticket {ticket_id} to agent {agent_id}...")

            # Notify the agent via ticket messages because the dedicated assignment API is unavailable
            message = f"@{agent_id} This ticket has been assigned to you."
            if comment:
                message += f"\nNote: {comment}"
            
            # Send the message as an alternative assignment workflow
            success = self.__send_ticket_message(ticket_id, message)
            
            if success:
                self.logger.info("✅ Notified agent via ticket message")
                return {
                    "success": True,
                    "ticket_id": ticket_id,
                    "agent_id": agent_id,
                    "method": "message_notification"
                }
            else:
                self.logger.warning("Failed to notify agent, but not critical")
                return {
                    "success": False,
                    "ticket_id": ticket_id,
                    "agent_id": agent_id,
                    "error": "Failed to send notification"
                }
                
        except Exception as e:
            self.logger.warning(f"Failed to assign ticket: {e}")
            # Do not raise an exception because the ticket was already created successfully
            return {
                "success": False,
                "ticket_id": ticket_id,
                "agent_id": agent_id,
                "error": str(e)
            }

    def get_user_by_email(self, email: str) -> Dict[str, Any]:
        """
        Retrieve user information (including open_id) by email address.

        Args:
            email (str): User email.

        Returns:
            dict: User information containing the open_id.

        Note: Used by workflows to automatically resolve open_id from email.
        """
        try:
            self.logger.info(f"Getting user info for email: {email}")
            
            # Feishu Contact API: batch get user information
            # Reference: https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/contact-v3/user/batch_get_id
            url = self.__get_url("/open-apis/contact/v3/users/batch_get_id")
            
            # Use POST request with the email list in the body
            params = {
                "user_id_type": "open_id"  # Response should include open_id
            }
            
            body = {
                "emails": [email],
                "include_resigned": False
            }
            
            self.logger.info(f"Request URL: {url}")
            self.logger.info(f"Request body: {json.dumps(body, ensure_ascii=False)}")
            
            response = requests.post(
                url=url,
                params=params,
                json=body,
                headers=self.__get_headers(),
            )
            
            self.logger.info(f"Response status: {response.status_code}")
            
            # Parse the response body
            try:
                result = response.json()
                self.logger.info(f"Response: {result}")
            except:
                self.logger.error(f"Failed to parse response: {response.text}")
                raise
            
            response.raise_for_status()
            
            if result.get("code") != 0:
                raise ProviderException(
                    f"Failed to get user by email: {result.get('msg')} (code: {result.get('code')})"
                )
            
            # Extract the list of matched users
            user_list = result.get("data", {}).get("user_list", [])
            
            if not user_list:
                raise ProviderException(f"User not found for email: {email}")
            
            # Use the first matched user
            user_info = user_list[0]
            user_id = user_info.get("user_id")
            
            self.logger.info(f"✅ Found user for {email}: {user_id}")
            
            return {
                "open_id": user_id,
                "email": email,
                "user_id": user_id,
            }
        except Exception as e:
            self.logger.exception("Failed to get user by email")
            raise ProviderException(f"Failed to get user by email: {e}")
    
    def get_users(self, page_size: int = 50) -> Dict[str, Any]:
        """
        Retrieve a list of users in the organization.

        Args:
            page_size (int): Number of results per page.

        Returns:
            dict: User list formatted for frontend dropdowns.
        """
        try:
            self.logger.info("Fetching users list...")
            
            url = self.__get_url("/open-apis/contact/v3/users")
            
            params = {
                "page_size": page_size
            }
            
            response = requests.get(
                url=url,
                params=params,
                headers=self.__get_headers(),
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") != 0:
                raise ProviderException(
                    f"Failed to get users: {result.get('msg')}"
                )
            
            items = result.get("data", {}).get("items", [])
            
            # Normalize user metadata
            formatted_users = [
                {
                    "open_id": user.get("open_id"),
                    "user_id": user.get("user_id"),
                    "name": user.get("name"),
                    "email": user.get("enterprise_email") or user.get("email"),
                }
                for user in items
            ]
            
            self.logger.info(f"Fetched {len(formatted_users)} users")
            return {
                "users": formatted_users,
                "total": len(formatted_users)
            }
        except Exception as e:
            self.logger.exception("Failed to get users")
            raise ProviderException(f"Failed to get users: {e}")

    # ==================== End of Provider Methods ====================

    def __auto_enrich_description(self, title: str, description: str, **kwargs) -> str:
        """
        Auto-enrich the ticket description with Keep platform links and contextual details.

        The enrichment includes:
        - Direct links to the Keep UI.
        - Timeline information (first trigger, last received, counters).
        - Source, environment, and service metadata.
        - Associated incident references.
        - Monitoring and runbook URLs.
        """
        try:
            context = self.context_manager.get_full_context() if hasattr(self, "context_manager") else {}

            alert = context.get("event")
            incident = context.get("incident")

            if not alert and not incident:
                self.logger.debug("No alert or incident found in context, using original description")
                return description if description else "No detailed description provided."

            def get_attr(obj, attr, default="N/A"):
                """Safely retrieve an attribute from a dict or object."""
                if obj is None:
                    return default
                if isinstance(obj, dict):
                    return obj.get(attr, default)
                return getattr(obj, attr, default)

            def format_status(status):
                """Normalize status enums to uppercase strings."""
                if not status or status == "N/A":
                    return "N/A"
                status_str = str(status)
                if "." in status_str:
                    status_str = status_str.split(".")[-1]
                return status_str.upper()

            def format_severity(severity):
                """Normalize severity values to uppercase strings."""
                if not severity or severity == "N/A":
                    return "N/A"
                return str(severity).upper()

            enriched = ""

            if alert:
                enriched += f"🔴 Event Title: {title}\n"
                enriched += f"📊 Severity: {format_severity(get_attr(alert, 'severity'))}\n"
                enriched += f"🏷️ Status: {format_status(get_attr(alert, 'status'))}\n"
                enriched += f"⏰ Last Received: {get_attr(alert, 'lastReceived')}\n"

                firing_start = get_attr(alert, "firingStartTime", None)
                if firing_start and str(firing_start).lower() not in {"n/a", "null", "none"}:
                    enriched += f"🔥 First Triggered: {firing_start}\n"

                firing_counter = get_attr(alert, "firingCounter", None)
                if firing_counter is not None and str(firing_counter).lower() not in {"n/a", "null", "none"}:
                    enriched += f"🔢 Trigger Count: {firing_counter}\n"

                sources = get_attr(alert, "source", [])
                if sources and sources != "N/A":
                    if isinstance(sources, list):
                        enriched += f"\n📍 Sources: {', '.join(str(s) for s in sources)}\n"
                    else:
                        enriched += f"\n📍 Sources: {sources}\n"
                else:
                    enriched += "\n📍 Sources: N/A\n"

                enriched += f"🌐 Environment: {get_attr(alert, 'environment')}\n"

                service = get_attr(alert, "service", None)
                if service and str(service).lower() not in {"n/a", "null", "none"}:
                    enriched += f"⚙️ Related Service: {service}\n"

                keep_api_url = None
                keep_context = context.get("keep")
                if isinstance(keep_context, dict):
                    keep_api_url = keep_context.get("api_url")

                if not keep_api_url:
                    import os
                    keep_api_url = os.environ.get("KEEP_API_URL", "http://localhost:3000/api/v1")

                keep_frontend_url = (
                    keep_api_url.replace("/api/v1", "")
                    .replace(":8080", ":3000")
                    .replace(":8000", ":3000")
                    .replace("0.0.0.0", "localhost")
                )

                self.logger.debug(f"Keep API URL: {keep_api_url}")
                self.logger.debug(f"Keep Frontend URL: {keep_frontend_url}")

                alert_id = get_attr(alert, "id", None)

                link_added = False
                if alert_id and alert_id != "N/A":
                    keep_url = f"{keep_frontend_url}/alerts/feed?cel=id%3D%3D%22{alert_id}%22"
                    enriched += f"\n🔗 Keep Event: {keep_url}\n"
                    link_added = True

                alert_url = get_attr(alert, "url", None)
                if alert_url and str(alert_url).lower() not in {"n/a", "null", "none"}:
                    if not link_added:
                        enriched += "\n"
                    enriched += f"🔗 Alert Details: {alert_url}\n"
                    link_added = True

                generator_url = get_attr(alert, "generatorURL", None)
                if generator_url and str(generator_url).lower() not in {"n/a", "null", "none"}:
                    enriched += f"🔗 Monitoring Dashboard: {generator_url}\n"
                    link_added = True

                playbook_url = get_attr(alert, "playbook_url", None)
                if playbook_url and str(playbook_url).lower() not in {"n/a", "null", "none"}:
                    enriched += f"🔗 Runbook: {playbook_url}\n"
                    link_added = True

                incident_id = get_attr(alert, "incident", None)
                if incident_id and str(incident_id).lower() not in {"n/a", "null", "none"}:
                    keep_frontend_url = (
                        keep_api_url.replace("/api/v1", "")
                        .replace(":8080", ":3000")
                        .replace(":8000", ":3000")
                        .replace("0.0.0.0", "localhost")
                    )
                    enriched += f"🎯 Related Incident: {keep_frontend_url}/incidents/{incident_id}\n"

            elif incident:
                incident_name = (
                    get_attr(incident, "user_generated_name", None)
                    or get_attr(incident, "ai_generated_name", None)
                    or title
                )
                enriched += f"🔴 Incident Title: {incident_name}\n"
                enriched += f"📊 Severity: {format_severity(get_attr(incident, 'severity'))}\n"
                enriched += f"🏷️ Status: {format_status(get_attr(incident, 'status'))}\n"
                enriched += f"🔍 Alert Count: {get_attr(incident, 'alerts_count', 0)}\n"
                enriched += f"⏰ Created At: {get_attr(incident, 'creation_time')}\n"

                start_time = get_attr(incident, "start_time", None)
                if start_time and str(start_time).lower() not in {"n/a", "null", "none"}:
                    enriched += f"⏰ Started At: {start_time}\n"

                alert_sources = get_attr(incident, "alert_sources", [])
                if alert_sources and alert_sources != "N/A":
                    if isinstance(alert_sources, list) and len(alert_sources) > 0:
                        enriched += f"\n📍 Alert Sources: {', '.join(str(s) for s in alert_sources)}\n"
                    else:
                        enriched += f"\n📍 Alert Sources: {alert_sources}\n"

                services = get_attr(incident, "services", [])
                if services and services != "N/A":
                    if isinstance(services, list) and len(services) > 0:
                        enriched += f"⚙️ Related Services: {', '.join(str(s) for s in services)}\n"
                    else:
                        enriched += f"⚙️ Related Services: {services}\n"

                keep_api_url = None
                keep_context = context.get("keep")
                if isinstance(keep_context, dict):
                    keep_api_url = keep_context.get("api_url")

                if not keep_api_url:
                    import os
                    keep_api_url = os.environ.get("KEEP_API_URL", "http://localhost:3000/api/v1")

                keep_frontend_url = (
                    keep_api_url.replace("/api/v1", "")
                    .replace(":8080", ":3000")
                    .replace(":8000", ":3000")
                    .replace("0.0.0.0", "localhost")
                )

                incident_id = get_attr(incident, "id", None)

                if incident_id and str(incident_id).lower() not in {"n/a", "null", "none"}:
                    keep_url = f"{keep_frontend_url}/incidents/{incident_id}"
                    enriched += f"\n🔗 Incident Details: {keep_url}\n"

            if description:
                enriched += f"\n📝 Description: {description}\n"

            if alert:
                assignee = get_attr(alert, "assignee", None)
                if assignee and str(assignee).lower() not in {"n/a", "null", "none"}:
                    enriched += f"\n👤 Owner: {assignee}\n"
            elif incident:
                assignee = get_attr(incident, "assignee", None)
                if assignee and str(assignee).lower() not in {"n/a", "null", "none"}:
                    enriched += f"\n👤 Owner: {assignee}\n"

            enriched += "\n⚠️ Use the links above to review full context and take action promptly."

            self.logger.info("✅ Auto-enriched ticket description with event context")
            return enriched

        except Exception as e:
            self.logger.warning(f"Failed to auto-enrich description: {e}, using original")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            return description if description else "No detailed description provided."

    def _notify(
        self,
        title: Optional[str] = None,
        user_email: Optional[str] = None,
        agent_email: Optional[str] = None,
        **kwargs: dict,
    ):
        """
        Create or update a Feishu Service Desk ticket.

        Args:
            title: Ticket title (required for creating, optional for updating)
            user_email: Reporter email address (auto-converts to Feishu User ID)
            agent_email: Agent email address (auto-converts to Feishu Agent ID)
            
        Advanced parameters (passed via workflow YAML):
            description, ticket_id, status, customized_fields, category_id, 
            agent_id, priority, tags, add_comment, open_id, auto_enrich
            
        The provider automatically:
        - Converts emails to Feishu IDs
        - Enriches ticket with event details, Keep links, timestamps
        - Sends rich text cards to ticket conversation
        - Includes original alert URLs from monitoring systems
        """
        try:
            self.logger.info("Notifying Feishu Service Desk...")
            
            # Extract additional parameters from kwargs
            description = kwargs.get("description", "")
            ticket_id = kwargs.get("ticket_id", None)
            
            # Support reading the title from kwargs for compatibility
            if title is None:
                title = kwargs.get("title", None)
            status = kwargs.get("status", None)
            customized_fields = kwargs.get("customized_fields", None)
            category_id = kwargs.get("category_id", None)
            agent_id = kwargs.get("agent_id", None)
            priority = kwargs.get("priority", None)
            tags = kwargs.get("tags", None)
            add_comment = kwargs.get("add_comment", None)
            open_id = kwargs.get("open_id", None)
            auto_enrich = kwargs.get("auto_enrich", True)
            
            if user_email and not open_id:
                try:
                    self.logger.info(f"🔄 Converting user email to open_id: {user_email}")
                    user_info = self.get_user_by_email(user_email)
                    open_id = user_info.get("open_id")
                    self.logger.info(f"✅ Converted user email to open_id: {open_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to convert user email to open_id: {e}")
                    # Continue with default_open_id or raise during ticket creation

            if agent_email and not agent_id:
                try:
                    self.logger.info(f"🔄 Converting agent email to agent_id: {agent_email}")
                    agent_info = self.get_user_by_email(agent_email)
                    agent_id = agent_info.get("open_id")
                    self.logger.info(f"✅ Converted agent email to agent_id: {agent_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to convert agent email to agent_id: {e}")
                    # Continue without assigning a specific agent

            if auto_enrich and title and (not description or len(description) < 300):
                original_desc = description
                enrich_kwargs = {k: v for k, v in kwargs.items() 
                                if k not in ['description', 'ticket_id', 'status', 'customized_fields', 
                                           'category_id', 'agent_id', 'priority', 'tags', 
                                           'add_comment', 'open_id', 'auto_enrich', 'title']}
                description = self.__auto_enrich_description(title, description, **enrich_kwargs)
                if description != original_desc:
                    self.logger.info("✅ Auto-enriched description with alert/incident context")

            if ticket_id:
                update_kwargs = {k: v for k, v in kwargs.items() 
                                if k not in ['description', 'ticket_id', 'status', 'customized_fields', 
                                           'category_id', 'agent_id', 'priority', 'tags', 
                                           'add_comment', 'open_id', 'auto_enrich', 'user_email', 'agent_email', 'title']}
                
                result = self.__update_ticket(
                    ticket_id=ticket_id,
                    status=status,
                    customized_fields=customized_fields,
                    **update_kwargs,
                )

                if add_comment:
                    self.add_ticket_comment(ticket_id, add_comment)
                    result["comment_added"] = True

                if agent_id:
                    self.assign_ticket(ticket_id, agent_id)
                    result["assigned_to"] = agent_id

                ticket_details = self.__get_ticket(ticket_id)
                result["ticket_url"] = ticket_details.get("ticket_url", "")

                self.logger.info("Updated a Feishu Service Desk ticket: " + str(result))
                return result
            else:
                if not title:
                    raise ProviderException("Title is required to create a ticket!")

                create_kwargs = {k: v for k, v in kwargs.items() 
                                if k not in ['description', 'ticket_id', 'status', 'customized_fields', 
                                           'category_id', 'agent_id', 'priority', 'tags', 
                                           'add_comment', 'open_id', 'auto_enrich', 'user_email', 'agent_email', 'title']}
                
                result = self.__create_ticket(
                    title=title,
                    description=description,
                    customized_fields=customized_fields,
                    category_id=category_id,
                    priority=priority,
                    tags=tags,
                    open_id=open_id,
                    agent_id=agent_id,
                    **create_kwargs,
                )

                ticket_data = result.get("ticket", {})
                created_ticket_id = ticket_data.get("ticket_id")

                if created_ticket_id:
                    if agent_id:
                        result["assigned_to"] = agent_id
                        self.logger.info(f"✅ Agent assigned via appointed_agents: {agent_id}")

                    ticket_details = self.__get_ticket(created_ticket_id)
                    result["ticket_url"] = ticket_details.get("ticket_url", "")

                self.logger.info("Notified Feishu Service Desk!")
                return result
        except Exception as e:
            raise ProviderException(f"Failed to notify Feishu Service Desk: {e}")

    def _query(
        self,
        ticket_id: Optional[str] = None,
        **kwargs: dict
    ):
        """
        Query Feishu Service Desk tickets.

        Args:
            ticket_id: Ticket ID (query specific ticket, leave empty to list tickets)
            
        Advanced filters (via workflow YAML):
            status, category_id, agent_id, page_size, page_token
        """
        try:
            if ticket_id:
                ticket = self.__get_ticket(ticket_id)
                return {"ticket": ticket}
            else:
                status = kwargs.get("status", None)
                category_id = kwargs.get("category_id", None)
                agent_id = kwargs.get("agent_id", None)
                page_size = kwargs.get("page_size", 50)
                page_token = kwargs.get("page_token", None)
                
                self.logger.info("Listing tickets from Feishu Service Desk...")

                url = self.__get_url("/open-apis/helpdesk/v1/tickets")
                
                params = {
                    "page_size": page_size,
                }
                
                if page_token:
                    params["page_token"] = page_token
                if status is not None:
                    params["status"] = status
                if category_id:
                    params["category_id"] = category_id
                if agent_id:
                    params["agent_id"] = agent_id
                
                if self.authentication_config.helpdesk_id:
                    params["helpdesk_id"] = self.authentication_config.helpdesk_id

                response = requests.get(
                    url=url,
                    params=params,
                    headers=self.__get_headers(),
                )

                response.raise_for_status()

                result = response.json()
                if result.get("code") != 0:
                    raise ProviderException(
                        f"Failed to list tickets: {result.get('msg')}"
                    )

                data = result.get("data", {})
                tickets = data.get("tickets", [])
                has_more = data.get("has_more", False)
                next_page_token = data.get("page_token", None)
                
                return {
                    "tickets": tickets,
                    "total": len(tickets),
                    "has_more": has_more,
                    "page_token": next_page_token
                }
        except Exception as e:
            raise ProviderException(f"Failed to query Feishu Service Desk: {e}")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    feishu_app_id = os.environ.get("FEISHU_APP_ID")
    feishu_app_secret = os.environ.get("FEISHU_APP_SECRET")
    feishu_host = os.environ.get("FEISHU_HOST", "https://open.feishu.cn")

    # Initialize the provider and provider config
    config = ProviderConfig(
        description="Feishu Service Desk Provider",
        authentication={
            "app_id": feishu_app_id,
            "app_secret": feishu_app_secret,
            "host": feishu_host,
        },
    )
    provider = FeishuServicedeskProvider(
        context_manager, provider_id="feishu_servicedesk", config=config
    )
    scopes = provider.validate_scopes()
    print(f"Scopes: {scopes}")

    # Example 1: Create ticket
    result = provider.notify(
        title="Test Ticket",
        description="This is a test ticket",
    )
    print(f"Created ticket: {result}")

    # Example 2: Update ticket
    if result.get("ticket", {}).get("ticket_id"):
        ticket_id = result["ticket"]["ticket_id"]
        update_result = provider.notify(ticket_id=ticket_id, status=50)
        print(f"Updated ticket: {update_result}")

    # Example 3: Query ticket
    if result.get("ticket", {}).get("ticket_id"):
        ticket_id = result["ticket"]["ticket_id"]
        query_result = provider.query(ticket_id=ticket_id)
        print(f"Queried ticket: {query_result}")

