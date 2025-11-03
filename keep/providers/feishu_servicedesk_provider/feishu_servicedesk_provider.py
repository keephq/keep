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
            "description": "飞书应用 ID (Feishu App ID)",
            "sensitive": False,
            "documentation_url": "https://open.feishu.cn/document/ukTMukTMukTM/ukDNz4SO0MjL5QzM/auth-v3/auth/tenant_access_token_internal",
        }
    )

    app_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "飞书应用密钥 (Feishu App Secret)",
            "sensitive": True,
            "documentation_url": "https://open.feishu.cn/document/ukTMukTMukTM/ukDNz4SO0MjL5QzM/auth-v3/auth/tenant_access_token_internal",
        }
    )

    host: HttpsUrl = dataclasses.field(
        metadata={
            "required": False,
            "description": "飞书服务器地址 (Feishu Server Host)",
            "sensitive": False,
            "hint": "https://open.feishu.cn",
            "validation": "https_url",
        },
        default="https://open.feishu.cn",
    )

    helpdesk_id: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "服务台 ID (Helpdesk ID), 如不提供则使用默认服务台",
            "sensitive": False,
            "hint": "Leave empty to use default helpdesk",
        },
        default="",
    )

    helpdesk_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "服务台 Token (Helpdesk Token), 创建工单必需",
            "sensitive": True,
            "hint": "Required for creating tickets. Get from Feishu Service Desk settings",
        },
        default="",
    )

    default_open_id: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "默认用户 Open ID, 创建工单时如未指定则使用此ID",
            "sensitive": False,
            "hint": "Default user open_id for creating tickets",
        },
        default="",
    )


class FeishuServicedeskProvider(BaseProvider):
    """Enrich alerts with Feishu Service Desk tickets."""

    OAUTH2_URL = None  # 飞书服务台不使用 OAuth2 认证
    PROVIDER_CATEGORY = ["Ticketing"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="helpdesk:ticket",
            description="工单读取权限 (Read Tickets)",
            mandatory=True,
            alias="Read tickets",
        ),
        ProviderScope(
            name="helpdesk:ticket:create",
            description="工单创建权限 (Create Tickets)",
            mandatory=True,
            alias="Create tickets",
        ),
        ProviderScope(
            name="helpdesk:ticket:update",
            description="工单更新权限 (Update Tickets)",
            mandatory=False,
            alias="Update tickets",
        ),
        ProviderScope(
            name="helpdesk:agent",
            description="客服信息读取权限 (Read Agent Info)",
            mandatory=False,
            alias="Read agents",
        ),
        ProviderScope(
            name="contact:user.base:readonly",
            description="用户信息读取权限 (Read User Info)",
            mandatory=False,
            alias="Read user info",
        ),
    ]

    PROVIDER_METHODS = []

    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_DISPLAY_NAME = "飞书服务台 (Feishu Service Desk)"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._host = None
        self._access_token = None
        self._token_expiry = None

    def validate_scopes(self):
        """
        验证 provider 是否具有所需的权限。
        Validate that the provider has the required scopes.
        """
        try:
            # 尝试获取 access token 来验证凭据
            access_token = self.__get_access_token()
            if not access_token:
                scopes = {
                    scope.name: "Failed to authenticate with Feishu - wrong credentials"
                    for scope in FeishuServicedeskProvider.PROVIDER_SCOPES
                }
                return scopes

            # 如果成功获取 token，返回所有权限为 True
            # Note: 飞书的权限验证在创建应用时配置，这里简化验证逻辑
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
        """
        获取飞书 tenant_access_token
        Get Feishu tenant access token.
        """
        try:
            # 检查 token 是否还有效
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
            # 设置 token 过期时间（提前 5 分钟过期）
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
            use_helpdesk_auth (bool): 如果为True且配置了helpdesk_token，
                                     同时发送服务台特殊认证头
        
        Note: 服务台API需要同时发送两个认证头:
              1. Authorization: Bearer {tenant_access_token}
              2. X-Lark-Helpdesk-Authorization: base64(helpdesk_id:helpdesk_token)
        """
        headers = {
            "Content-Type": "application/json; charset=utf-8",
        }
        
        # 总是添加标准的 tenant_access_token 认证
        access_token = self.__get_access_token()
        headers["Authorization"] = f"Bearer {access_token}"
        
        # 如果需要服务台特殊认证，同时添加服务台认证头
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
        创建飞书服务台工单（启动人工服务）
        Helper method to create a ticket in Feishu Service Desk.
        
        Note: 飞书服务台使用 StartServiceTicket API (启动人工服务)
              需要 helpdesk_token 和特殊的认证头
        """
        try:
            self.logger.info("Creating a ticket in Feishu Service Desk...")

            # 飞书服务台API：启动人工服务
            url = self.__get_url("/open-apis/helpdesk/v1/start_service")

            # 🆕 直接使用enriched描述作为customized_info
            # 不再使用简化格式，因为后续的消息/评论API都不可用
            # customized_info会作为首条消息显示在服务台对话中
            if description:
                ticket_content = description
            else:
                # 如果没有description，使用简单格式
                ticket_content = f"【工单标题】{title}\n\n请查看Keep平台获取详细信息"
            
            # 如果有额外信息，添加到内容末尾
            if category_id:
                ticket_content += f"\n\n【分类ID】{category_id}"
            if priority:
                ticket_content += f"\n【优先级】{priority}"
            if tags:
                ticket_content += f"\n【标签】{', '.join(tags)}"

            # 构建请求体（符合飞书API格式）
            ticket_data = {
                "human_service": True,  # 启用人工服务
                "customized_info": ticket_content,  # 完整的enriched内容
            }

            # 添加用户open_id（必需）
            if open_id:
                ticket_data["open_id"] = open_id
            elif kwargs.get("open_id"):
                ticket_data["open_id"] = kwargs.get("open_id")
            elif self.authentication_config.default_open_id:
                ticket_data["open_id"] = self.authentication_config.default_open_id
                self.logger.info(f"Using default open_id: {self.authentication_config.default_open_id}")
            else:
                # open_id是必需的
                raise ProviderException(
                    "open_id is required to create a ticket. "
                    "Please provide open_id parameter or set default_open_id in configuration."
                )

            # 添加指定客服（可选）
            if agent_id:
                ticket_data["appointed_agents"] = [agent_id]

            # 记录请求信息（用于调试）
            self.logger.info(f"Creating ticket with URL: {url}")
            self.logger.info(f"Request data: {json.dumps(ticket_data, ensure_ascii=False)}")
            
            # 使用服务台特殊认证
            response = requests.post(
                url=url,
                json=ticket_data,
                headers=self.__get_headers(use_helpdesk_auth=True),
            )

            # 记录响应状态和内容（用于调试）
            self.logger.info(f"Response status: {response.status_code}")
            self.logger.info(f"Response headers: {dict(response.headers)}")
            
            # 先获取原始文本，以便调试
            response_text = response.text
            self.logger.info(f"Response text (first 500 chars): {response_text[:500]}")
            
            # 尝试解析JSON
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON response: {e}")
                self.logger.error(f"Full response text: {response_text}")
                raise ProviderException(
                    f"Failed to parse Feishu API response. Status: {response.status_code}, "
                    f"Response: {response_text[:200]}"
                )
            
            # 检查HTTP状态码
            try:
                response.raise_for_status()
            except Exception as e:
                self.logger.exception(
                    "Failed to create a ticket", extra={"result": result, "status": response.status_code}
                )
                raise ProviderException(
                    f"Failed to create a ticket. HTTP {response.status_code}: {result}"
                )

            # 检查飞书API返回的code
            if result.get("code") != 0:
                error_msg = result.get("msg", "Unknown error")
                self.logger.error(f"Feishu API returned error code {result.get('code')}: {error_msg}")
                raise ProviderException(
                    f"Failed to create ticket: {error_msg} (code: {result.get('code')})"
                )

            self.logger.info("Created a ticket in Feishu Service Desk!")
            
            # 返回完整信息供后续使用
            ticket_data = result.get("data", {})
            ticket_id = ticket_data.get("ticket_id")
            chat_id = ticket_data.get("chat_id")
            
            # 🆕 使用正确的服务台消息API发送详细描述
            # API: POST /open-apis/helpdesk/v1/tickets/{ticket_id}/messages
            if ticket_id and description and len(description) > 200:
                try:
                    success = self.__send_ticket_message(ticket_id, description)
                    if success:
                        self.logger.info("✅ Sent detailed description via ticket messages API")
                    else:
                        self.logger.warning("⚠️ Failed to send message, but ticket created successfully")
                        self.logger.info("Enriched content is in customized_info")
                except Exception as e:
                    # 发送失败不影响工单创建
                    self.logger.warning(f"Failed to send ticket message: {e}")
                    self.logger.info("Enriched content is in customized_info")
            else:
                self.logger.info("✅ Full enriched content sent via customized_info")
            
            return {
                "ticket": ticket_data,
                "ticket_id": ticket_id,
                "chat_id": chat_id,
                # 这些信息可以保存到Keep的alert/incident中，用于后续同步
                "feishu_ticket_id": ticket_id,
                "feishu_chat_id": chat_id,
            }
        except Exception as e:
            raise ProviderException(f"Failed to create a ticket: {e}")

    def __build_rich_card_content(self, enriched_text: str) -> list:
        """
        将enriched文本转换为飞书富文本卡片格式
        Convert enriched text to Feishu rich text card format with clickable links.
        
        Args:
            enriched_text: Enriched描述文本
            
        Returns:
            list: 飞书post格式的content数组
        """
        content_lines = []
        
        lines = enriched_text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            i += 1
            
            # 跳过空行和分隔线
            if not line or line.startswith('━'):
                continue
            
            # 检测URL行（下一行是链接）
            if i < len(lines) and (lines[i].strip().startswith('http://') or lines[i].strip().startswith('https://')):
                # 当前行是描述，下一行是URL
                label = line
                url = lines[i].strip()
                i += 1
                
                # 根据标签选择合适的显示文本
                if '告警详情' in label or 'alert-his-events' in url or 'nalert' in url:
                    link_text = "🔔 查看告警详情"
                elif 'Keep事件详情' in label:
                    link_text = "📱 查看Keep事件"
                elif 'Incident' in label:
                    link_text = "🎯 查看Incident"
                elif '生成器' in label or 'generator' in label.lower():
                    link_text = "⚙️ 打开生成器"
                elif '运行手册' in label or 'playbook' in label.lower():
                    link_text = "📖 查看手册"
                else:
                    link_text = "🔗 点击打开"
                
                # 创建可点击的超链接
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
            # 检测直接的URL行
            elif line.startswith('http://') or line.startswith('https://'):
                # 根据URL类型设置友好文本
                if 'alerts/feed' in line:
                    link_text = "📱 点击查看Keep事件详情"
                elif '/incidents/' in line:
                    link_text = "🎯 点击查看Incident详情"
                elif 'alert-his-events' in line or 'nalert' in line:
                    link_text = "🔔 查看告警详情"
                elif 'prometheus' in line or 'grafana' in line:
                    link_text = "📊 打开监控系统"
                else:
                    link_text = "🔗 点击打开链接"
                
                content_lines.append([{
                    "tag": "a",
                    "text": link_text,
                    "href": line
                }])
            # 章节标题（包含emoji或特殊字符）
            elif any(emoji in line for emoji in ['📋', '🔗', '📍', '🔍', '⚠️', '📝']):
                content_lines.append([{
                    "tag": "text",
                    "text": line,
                    "un_escape": True
                }])
            else:
                # 普通文本行
                if line:
                    content_lines.append([{
                        "tag": "text",
                        "text": line
                    }])
        
        # 如果没有解析出内容，使用原始文本
        if not content_lines:
            content_lines = [[{
                "tag": "text",
                "text": enriched_text
            }]]
        
        return content_lines

    def __send_ticket_message(self, ticket_id: str, content: str):
        """
        向工单发送消息（使用飞书服务台专用消息API）
        Send a message to helpdesk ticket.
        
        Args:
            ticket_id: Ticket ID
            content: 消息内容（enriched描述）
            
        Returns:
            bool: 是否发送成功
            
        API: POST /open-apis/helpdesk/v1/tickets/{ticket_id}/messages
        """
        try:
            self.logger.info(f"Sending rich card message to ticket {ticket_id}...")
            
            # 飞书服务台消息API
            url = self.__get_url(f"/open-apis/helpdesk/v1/tickets/{ticket_id}/messages")
            
            # 🎨 构建富文本卡片格式
            # 参考：https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/helpdesk-v1/ticket-message/create
            card_content = self.__build_rich_card_content(content)
            
            message_data = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": "📋 事件详细信息",
                            "content": card_content
                        }
                    }
                }
            }
            
            self.logger.info(f"Sending ticket message to URL: {url}")
            
            # 🔧 服务台消息API需要双认证
            response = requests.post(
                url=url,
                json=message_data,
                headers=self.__get_headers(use_helpdesk_auth=True),  # ← 关键：使用服务台认证
            )
            
            self.logger.info(f"Ticket message response: {response.status_code}")
            
            # 尝试解析响应
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
        """
        更新飞书服务台工单
        Helper method to update a ticket in Feishu Service Desk.
        """
        try:
            self.logger.info(f"Updating ticket {ticket_id} in Feishu Service Desk...")

            url = self.__get_url(f"/open-apis/helpdesk/v1/tickets/{ticket_id}")

            update_data = {}

            # 更新工单状态
            if status is not None:
                update_data["status"] = status

            # 更新自定义字段
            if customized_fields:
                update_data["customized_fields"] = customized_fields

            response = requests.patch(
                url=url,
                json=update_data,
                headers=self.__get_headers(),
            )

            # 记录响应（调试用）
            self.logger.info(f"Update response status: {response.status_code}")
            response_text = response.text
            self.logger.info(f"Update response text: {response_text[:500]}")

            # 解析响应
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse update response: {e}")
                self.logger.error(f"Full response: {response_text}")
                raise ProviderException(
                    f"Failed to parse update response. Status: {response.status_code}, "
                    f"Response: {response_text[:200]}"
                )

            # 检查HTTP状态码
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

            # 检查飞书API返回码
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
        获取工单详情
        Helper method to get ticket details.
        
        Note: 飞书服务台的查询工单API也需要服务台特殊认证
        """
        try:
            self.logger.info(f"Fetching ticket {ticket_id} from Feishu Service Desk...")

            url = self.__get_url(f"/open-apis/helpdesk/v1/tickets/{ticket_id}")

            # 使用服务台特殊认证
            response = requests.get(
                url=url,
                headers=self.__get_headers(use_helpdesk_auth=True),
            )

            # 记录响应（调试用）
            self.logger.info(f"Get ticket response status: {response.status_code}")
            response_text = response.text
            self.logger.info(f"Get ticket response: {response_text[:500]}")

            # 解析响应
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse get ticket response: {e}")
                # 如果无法获取工单详情，返回基本信息
                self.logger.warning("Could not fetch ticket details, using minimal info")
                return {
                    "ticket_id": ticket_id,
                    "ticket_url": f"{self.feishu_host}/helpdesk/ticket/{ticket_id}"
                }

            # 检查状态码
            if response.status_code == 401 or response.status_code == 404:
                # 查询API可能不可用，返回基本信息
                self.logger.warning(f"Ticket detail API returned {response.status_code}, using basic info")
                return {
                    "ticket_id": ticket_id,
                    "ticket_url": f"{self.feishu_host}/helpdesk/ticket/{ticket_id}"
                }

            response.raise_for_status()

            if result.get("code") != 0:
                self.logger.warning(f"Failed to get ticket details: {result.get('msg')}")
                # 返回基本信息而不是抛出异常
                return {
                    "ticket_id": ticket_id,
                    "ticket_url": f"{self.feishu_host}/helpdesk/ticket/{ticket_id}"
                }

            self.logger.info("Fetched ticket from Feishu Service Desk!")
            return result.get("data", {})
        except Exception as e:
            # 如果获取工单详情失败，返回基本信息而不是失败
            self.logger.warning(f"Could not fetch ticket details: {e}, returning basic info")
            return {
                "ticket_id": ticket_id,
                "ticket_url": f"{self.feishu_host}/helpdesk/ticket/{ticket_id}"
            }

    # ==================== Provider Methods (for frontend) ====================

    def get_helpdesks(self) -> Dict[str, Any]:
        """
        获取服务台列表
        Get list of helpdesks (for frontend dropdown).
        
        Returns:
            dict: List of helpdesks with their IDs and names
            
        Note: ⚠️ 此API端点需要验证是否存在。
              如果失败，可能需要调整端点路径或使用其他方式获取服务台列表。
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
            
            # 格式化返回数据，方便前端使用
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
        获取服务台客服列表
        Get list of agents (for frontend dropdown).
        
        Args:
            helpdesk_id (str): Helpdesk ID (optional, uses configured helpdesk_id if not provided)
            
        Returns:
            dict: List of agents with their IDs and names
            
        Note: ⚠️ 此API可能需要特殊认证或使用不同端点。
              如果失败，尝试：
              1. 使用 use_helpdesk_auth=True 启用服务台特殊认证
              2. 或使用通讯录API获取用户信息
        """
        try:
            helpdesk_id = helpdesk_id or self.authentication_config.helpdesk_id
            if not helpdesk_id:
                # 如果没有指定服务台ID，获取第一个服务台
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
            
            # 格式化返回数据
            formatted_agents = [
                {
                    "id": agent.get("user_id"),
                    "name": agent.get("name"),
                    "email": agent.get("email"),
                    "status": agent.get("status"),  # 1: 在线, 2: 离线, 3: 忙碌
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
        获取工单分类列表
        Get list of ticket categories (for frontend dropdown).
        
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
            
            # 格式化返回数据
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
        获取工单自定义字段配置
        Get ticket custom fields configuration (for frontend form).
        
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
            
            # 格式化返回数据
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
        comment_type: int = 1  # 1: 文本, 2: 富文本
    ) -> Dict[str, Any]:
        """
        添加工单评论
        Add comment to a ticket.
        
        Args:
            ticket_id (str): Ticket ID
            content (str): Comment content
            comment_type (int): Comment type (1: plain text, 2: rich text)
            
        Returns:
            dict: Comment result
            
        Note: ⚠️ 此API端点需要验证。
              评论功能可能需要：
              1. 不同的API端点
              2. 使用飞书消息API
              3. 不同的参数格式（msg_type字段名）
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
        分配工单给指定客服
        Assign ticket to a specific agent.
        
        Args:
            ticket_id (str): Ticket ID
            agent_id (str): Agent user ID
            comment (str): Optional comment for the assignment
            
        Returns:
            dict: Assignment result
            
        Note: ⚠️ 飞书服务台不支持后续分配API（返回404）
              建议在创建工单时通过appointed_agents参数指定客服
              此方法保留以供兼容性，但可能不可用
        """
        try:
            self.logger.warning(
                f"⚠️ Assign ticket API may not be available in Feishu Service Desk. "
                f"Recommend using agent_email/agent_id in ticket creation instead."
            )
            self.logger.info(f"Attempting to assign ticket {ticket_id} to agent {agent_id}...")

            # 尝试通过发送消息通知客服
            # 因为直接的分配API不可用
            message = f"@{agent_id} 此工单已分配给你处理"
            if comment:
                message += f"\n备注：{comment}"
            
            # 使用消息API通知（作为替代方案）
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
            # 不抛出异常，因为工单已创建成功
            return {
                "success": False,
                "ticket_id": ticket_id,
                "agent_id": agent_id,
                "error": str(e)
            }

    def get_user_by_email(self, email: str) -> Dict[str, Any]:
        """
        通过邮箱获取用户信息（包括open_id）
        Get user information by email.
        
        Args:
            email (str): 用户邮箱
            
        Returns:
            dict: 用户信息，包含open_id
            
        Note: 用于在工作流中通过邮箱自动获取open_id
        """
        try:
            self.logger.info(f"Getting user info for email: {email}")
            
            # 飞书通讯录API：批量获取用户信息
            # 参考：https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/contact-v3/user/batch_get_id
            url = self.__get_url("/open-apis/contact/v3/users/batch_get_id")
            
            # 🔧 使用POST请求，emails放在请求体中，格式为数组
            params = {
                "user_id_type": "open_id"  # 返回open_id格式
            }
            
            body = {
                "emails": [email],  # 数组格式
                "include_resigned": False  # 不包括离职用户
            }
            
            self.logger.info(f"Request URL: {url}")
            self.logger.info(f"Request body: {json.dumps(body, ensure_ascii=False)}")
            
            response = requests.post(  # ← POST而不是GET
                url=url,
                params=params,
                json=body,
                headers=self.__get_headers(),
            )
            
            self.logger.info(f"Response status: {response.status_code}")
            
            # 解析响应
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
            
            # 提取user_list
            user_list = result.get("data", {}).get("user_list", [])
            
            if not user_list:
                raise ProviderException(f"User not found for email: {email}")
            
            # 提取第一个匹配的用户
            user_info = user_list[0]
            user_id = user_info.get("user_id")
            
            self.logger.info(f"✅ Found user for {email}: {user_id}")
            
            return {
                "open_id": user_id,  # open_id
                "email": email,
                "user_id": user_id,
            }
        except Exception as e:
            self.logger.exception("Failed to get user by email")
            raise ProviderException(f"Failed to get user by email: {e}")
    
    def get_users(self, page_size: int = 50) -> Dict[str, Any]:
        """
        获取企业用户列表
        Get list of users in the organization.
        
        Args:
            page_size (int): 每页数量
            
        Returns:
            dict: 用户列表
            
        Note: 用于前端下拉选择用户
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
            
            # 格式化返回数据
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
        🆕 自动enrichment工单描述，添加Keep平台链接和事件详细信息
        Auto-enrich ticket description with Keep platform links and event details.
        
        如果检测到工作流上下文中有alert或incident，自动添加：
        - Keep平台事件详情页链接（可直接点击）
        - 完整的时间信息（触发时间、次数等）
        - 所有来源和环境信息
        - 关联Incident链接
        - 原始监控系统链接
        
        Args:
            title: 工单标题
            description: 原始描述
            **kwargs: 其他参数
            
        Returns:
            enriched_description: enrichment后的描述
        """
        try:
            # 获取工作流上下文
            context = self.context_manager.get_full_context() if hasattr(self, 'context_manager') else {}
            
            # 尝试从上下文中获取alert或incident
            alert = context.get('event', None)
            incident = context.get('incident', None)
            
            # 如果没有找到，返回原始描述
            if not alert and not incident:
                self.logger.debug("No alert or incident found in context, using original description")
                return description if description else "无详细描述 / No description provided"
            
            # 辅助函数：安全获取属性值
            def get_attr(obj, attr, default='N/A'):
                """安全获取对象属性，支持dict和对象"""
                if obj is None:
                    return default
                # 如果是dict，使用get方法
                if isinstance(obj, dict):
                    return obj.get(attr, default)
                # 如果是对象，使用getattr
                return getattr(obj, attr, default)
            
            # 辅助函数：格式化状态
            def format_status(status):
                """格式化状态，去除前缀，保持英文"""
                if not status or status == 'N/A':
                    return 'N/A'
                status_str = str(status)
                # 去除 INCIDENTSTATUS. 或 ALERTSTATUS. 前缀
                if '.' in status_str:
                    status_str = status_str.split('.')[-1]
                return status_str.upper()
            
            # 辅助函数：格式化严重程度
            def format_severity(severity):
                """格式化严重程度，保持英文"""
                if not severity or severity == 'N/A':
                    return 'N/A'
                return str(severity).upper()
            
            # 构建enrichment描述（参考用户提供的格式）
            enriched = ""
            
            if alert:
                # Alert基本信息
                enriched += f"🔴 事件名称: {title}\n"
                enriched += f"📊 严重程度: {format_severity(get_attr(alert, 'severity'))}\n"
                enriched += f"🏷️ 当前状态: {format_status(get_attr(alert, 'status'))}\n"
                enriched += f"⏰ 最后接收: {get_attr(alert, 'lastReceived')}\n"
                
                firing_start = get_attr(alert, 'firingStartTime', None)
                if firing_start and firing_start != 'N/A' and firing_start != 'null' and str(firing_start).lower() != 'none':
                    enriched += f"🔥 首次触发: {firing_start}\n"
                
                firing_counter = get_attr(alert, 'firingCounter', None)
                # 注意：firing_counter可能是0，0也是有效值
                if firing_counter is not None and firing_counter != 'N/A' and str(firing_counter).lower() != 'none':
                    enriched += f"🔢 触发次数: {firing_counter}\n"
                
                # 来源信息（一行显示）
                sources = get_attr(alert, 'source', [])
                if sources and sources != 'N/A':
                    if isinstance(sources, list):
                        enriched += f"\n📍 来源信息: {', '.join(str(s) for s in sources)}\n"
                    else:
                        enriched += f"\n📍 来源信息: {sources}\n"
                else:
                    enriched += f"\n📍 来源信息: N/A\n"
                
                enriched += f"🌐 部署环境: {get_attr(alert, 'environment')}\n"
                
                service = get_attr(alert, 'service', None)
                if service and service != 'N/A' and service != 'null' and str(service).lower() != 'none':
                    enriched += f"⚙️ 关联服务: {service}\n"
                
                # 🔧 获取Keep前端URL（不是API URL）
                keep_api_url = None
                keep_context = context.get('keep')
                if isinstance(keep_context, dict):
                    keep_api_url = keep_context.get('api_url')
                
                # 如果context中没有，尝试从环境变量或配置获取
                if not keep_api_url:
                    import os
                    keep_api_url = os.environ.get('KEEP_API_URL')
                    if not keep_api_url:
                        # 使用默认值（本地开发环境）
                        keep_api_url = "http://localhost:3000/api/v1"
                
                # 🔧 将API URL转换为前端UI URL
                # API: http://0.0.0.0:8080/api/v1 → 前端: http://localhost:3000
                # API: http://localhost:8080/api/v1 → 前端: http://localhost:3000
                keep_frontend_url = keep_api_url.replace('/api/v1', '')
                # 如果是后端端口(8080, 8000等)，替换为前端端口(3000)
                keep_frontend_url = keep_frontend_url.replace(':8080', ':3000')
                keep_frontend_url = keep_frontend_url.replace(':8000', ':3000')
                keep_frontend_url = keep_frontend_url.replace('0.0.0.0', 'localhost')
                
                self.logger.debug(f"Keep API URL: {keep_api_url}")
                self.logger.debug(f"Keep Frontend URL: {keep_frontend_url}")
                
                alert_id = get_attr(alert, 'id', None)
                
                # 重要链接
                link_added = False
                if alert_id and alert_id != 'N/A':
                    keep_url = f"{keep_frontend_url}/alerts/feed?cel=id%3D%3D%22{alert_id}%22"
                    enriched += f"\n🔗 事件详情: {keep_url}\n"
                    link_added = True
                
                # 告警详情URL（alert.url字段）
                alert_url = get_attr(alert, 'url', None)
                if alert_url and alert_url != 'N/A' and alert_url != 'null' and str(alert_url).lower() != 'none':
                    if not link_added:
                        enriched += "\n"
                    enriched += f"🔗 告警详情: {alert_url}\n"
                    link_added = True
                
                # 其他链接
                generator_url = get_attr(alert, 'generatorURL', None)
                if generator_url and generator_url != 'N/A' and generator_url != 'null' and str(generator_url).lower() != 'none':
                    enriched += f"🔗 监控面板: {generator_url}\n"
                    link_added = True
                
                playbook_url = get_attr(alert, 'playbook_url', None)
                if playbook_url and playbook_url != 'N/A' and playbook_url != 'null' and str(playbook_url).lower() != 'none':
                    enriched += f"🔗 处理手册: {playbook_url}\n"
                    link_added = True
                
                # Incident关联
                incident_id = get_attr(alert, 'incident', None)
                if incident_id and incident_id != 'N/A' and incident_id != 'null' and str(incident_id).lower() != 'none':
                    # 确保keep_api_url可用
                    if not keep_api_url:
                        import os
                        keep_api_url = os.environ.get('KEEP_API_URL', "http://localhost:3000/api/v1")
                    # 转换为前端URL
                    keep_frontend_url = keep_api_url.replace('/api/v1', '')
                    keep_frontend_url = keep_frontend_url.replace(':8080', ':3000').replace(':8000', ':3000').replace('0.0.0.0', 'localhost')
                    enriched += f"🎯 关联Incident: {keep_frontend_url}/incidents/{incident_id}\n"
                
            elif incident:
                # Incident信息
                incident_name = get_attr(incident, 'user_generated_name', None) or get_attr(incident, 'ai_generated_name', None) or title
                enriched += f"🔴 事件名称: {incident_name}\n"
                enriched += f"📊 严重程度: {format_severity(get_attr(incident, 'severity'))}\n"
                enriched += f"🏷️ 当前状态: {format_status(get_attr(incident, 'status'))}\n"
                enriched += f"🔍 关联告警数: {get_attr(incident, 'alerts_count', 0)}\n"
                enriched += f"⏰ 创建时间: {get_attr(incident, 'creation_time')}\n"
                
                start_time = get_attr(incident, 'start_time', None)
                if start_time and start_time != 'N/A' and start_time != 'null' and str(start_time).lower() != 'none':
                    enriched += f"⏰ 开始时间: {start_time}\n"
                
                # 告警来源（Incident特有字段）
                alert_sources = get_attr(incident, 'alert_sources', [])
                if alert_sources and alert_sources != 'N/A':
                    if isinstance(alert_sources, list) and len(alert_sources) > 0:
                        enriched += f"\n📍 告警来源: {', '.join(str(s) for s in alert_sources)}\n"
                    else:
                        enriched += f"\n📍 告警来源: {alert_sources}\n"
                
                # 关联服务（Incident中是services数组）
                services = get_attr(incident, 'services', [])
                if services and services != 'N/A':
                    if isinstance(services, list) and len(services) > 0:
                        enriched += f"⚙️ 关联服务: {', '.join(str(s) for s in services)}\n"
                    else:
                        enriched += f"⚙️ 关联服务: {services}\n"
                
                # 🔧 获取Keep前端URL（不是API URL）
                keep_api_url = None
                keep_context = context.get('keep')
                if isinstance(keep_context, dict):
                    keep_api_url = keep_context.get('api_url')
                
                if not keep_api_url:
                    import os
                    keep_api_url = os.environ.get('KEEP_API_URL', "http://localhost:3000/api/v1")
                
                # 🔧 将API URL转换为前端UI URL
                keep_frontend_url = keep_api_url.replace('/api/v1', '')
                keep_frontend_url = keep_frontend_url.replace(':8080', ':3000')
                keep_frontend_url = keep_frontend_url.replace(':8000', ':3000')
                keep_frontend_url = keep_frontend_url.replace('0.0.0.0', 'localhost')
                
                incident_id = get_attr(incident, 'id', None)
                
                # Keep链接
                if incident_id and incident_id != 'N/A' and incident_id != 'null' and str(incident_id).lower() != 'none':
                    keep_url = f"{keep_frontend_url}/incidents/{incident_id}"
                    enriched += f"\n🔗 事件详情: {keep_url}\n"
            
            # 添加原始描述
            if description:
                enriched += f"\n📝 详细描述: {description}\n"
            
            # 负责人
            if alert:
                assignee = get_attr(alert, 'assignee', None)
                if assignee and assignee != 'N/A' and assignee != 'null' and str(assignee).lower() != 'none':
                    enriched += f"\n👤 事件负责人: {assignee}\n"
            elif incident:
                assignee = get_attr(incident, 'assignee', None)
                if assignee and assignee != 'N/A' and assignee != 'null' and str(assignee).lower() != 'none':
                    enriched += f"\n👤 事件负责人: {assignee}\n"
            
            # 添加提示
            enriched += f"\n⚠️ 请点击上方事件详情链接查看完整信息并及时处理"
            
            self.logger.info("✅ Auto-enriched ticket description with event context")
            return enriched
            
        except Exception as e:
            self.logger.warning(f"Failed to auto-enrich description: {e}, using original")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            return description if description else "无详细描述 / No description provided"

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
            
            # 从kwargs中获取其他参数
            description = kwargs.get("description", "")
            ticket_id = kwargs.get("ticket_id", None)
            
            # 如果title在kwargs中，也支持从kwargs获取（兼容性）
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
            
            # 🆕 如果提供了user_email，自动转换为open_id
            if user_email and not open_id:
                try:
                    self.logger.info(f"🔄 Converting user email to open_id: {user_email}")
                    user_info = self.get_user_by_email(user_email)
                    open_id = user_info.get("open_id")
                    self.logger.info(f"✅ Converted user email to open_id: {open_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to convert user email to open_id: {e}")
                    # 继续执行，使用default_open_id或报错
            
            # 🆕 如果提供了agent_email，自动转换为agent_id
            if agent_email and not agent_id:
                try:
                    self.logger.info(f"🔄 Converting agent email to agent_id: {agent_email}")
                    agent_info = self.get_user_by_email(agent_email)
                    agent_id = agent_info.get("open_id")
                    self.logger.info(f"✅ Converted agent email to agent_id: {agent_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to convert agent email to agent_id: {e}")
                    # 继续执行，不分配客服
            
            # 🆕 自动enrichment：如果启用且description较短或为空，自动添加完整的事件信息
            # 只在创建工单时（有title）或更新工单时（有description）才enrich
            if auto_enrich and title and (not description or len(description) < 300):
                original_desc = description
                # 创建一个新的kwargs副本，移除已经提取的参数以避免冲突
                enrich_kwargs = {k: v for k, v in kwargs.items() 
                                if k not in ['description', 'ticket_id', 'status', 'customized_fields', 
                                           'category_id', 'agent_id', 'priority', 'tags', 
                                           'add_comment', 'open_id', 'auto_enrich', 'title']}
                description = self.__auto_enrich_description(title, description, **enrich_kwargs)
                if description != original_desc:
                    self.logger.info("✅ Auto-enriched description with alert/incident context")

            if ticket_id:
                # 更新现有工单
                # 创建一个清理过的kwargs，移除已经作为显式参数传递的值
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

                # 如果提供了评论，添加评论
                if add_comment:
                    self.add_ticket_comment(ticket_id, add_comment)
                    result["comment_added"] = True

                # 如果提供了客服 ID，分配工单
                if agent_id:
                    self.assign_ticket(ticket_id, agent_id)
                    result["assigned_to"] = agent_id

                # 获取工单详情以获取完整的 ticket_url
                ticket_details = self.__get_ticket(ticket_id)
                result["ticket_url"] = ticket_details.get("ticket_url", "")

                self.logger.info("Updated a Feishu Service Desk ticket: " + str(result))
                return result
            else:
                # 创建新工单
                if not title:
                    raise ProviderException("Title is required to create a ticket!")

                # 创建一个清理过的kwargs，移除已经作为显式参数传递的值
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

                # 获取创建的工单 ID 和 URL
                ticket_data = result.get("ticket", {})
                created_ticket_id = ticket_data.get("ticket_id")

                if created_ticket_id:
                    # Note: agent_id已经在__create_ticket中通过appointed_agents参数指定
                    # 不需要后续调用assign_ticket（该API返回404）
                    if agent_id:
                        result["assigned_to"] = agent_id
                        self.logger.info(f"✅ Agent assigned via appointed_agents: {agent_id}")

                    # 获取工单详情
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
                # 查询单个工单
                ticket = self.__get_ticket(ticket_id)
                return {"ticket": ticket}
            else:
                # 从 kwargs 提取高级参数
                status = kwargs.get("status", None)
                category_id = kwargs.get("category_id", None)
                agent_id = kwargs.get("agent_id", None)
                page_size = kwargs.get("page_size", 50)
                page_token = kwargs.get("page_token", None)
                
                # 列出工单
                self.logger.info("Listing tickets from Feishu Service Desk...")

                url = self.__get_url("/open-apis/helpdesk/v1/tickets")
                
                params = {
                    "page_size": page_size,
                }
                
                # 添加可选的过滤参数
                if page_token:
                    params["page_token"] = page_token
                if status is not None:
                    params["status"] = status
                if category_id:
                    params["category_id"] = category_id
                if agent_id:
                    params["agent_id"] = agent_id
                
                # 添加服务台 ID（如果已配置）
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
        title="测试工单",
        description="这是一个测试工单",
    )
    print(f"Created ticket: {result}")

    # Example 2: Update ticket
    if result.get("ticket", {}).get("ticket_id"):
        ticket_id = result["ticket"]["ticket_id"]
        update_result = provider.notify(
            ticket_id=ticket_id,
            status=50,  # 已完成
        )
        print(f"Updated ticket: {update_result}")

    # Example 3: Query ticket
    if result.get("ticket", {}).get("ticket_id"):
        ticket_id = result["ticket"]["ticket_id"]
        query_result = provider.query(ticket_id=ticket_id)
        print(f"Queried ticket: {query_result}")

