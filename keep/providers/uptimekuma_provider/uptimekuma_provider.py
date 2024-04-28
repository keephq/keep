"""
UptimeKuma is a class that provides the necessary methods to interact with the UptimeKuma SDK
"""

import dataclasses

import pydantic
from typing import Optional

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.exceptions.provider_exception import ProviderException
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

from uptime_kuma_api import UptimeKumaApi

@pydantic.dataclasses.dataclass
class UptimekumaProviderAuthConfig:
  """
  UptimekumaProviderAuthConfig is a class that holds the authentication information for the UptimekumaProvider.
  """

  host_url: str = dataclasses.field(
    metadata={
      "required": True,
      "description": "UptimeKuma Host URL",
      "sensitive": False,
    },
    default=None,
  )

  username: str = dataclasses.field(
    metadata={
      "required": True,
      "description": "UptimeKuma Username",
      "sensitive": False,
    },
    default=None,
  )

  password: str = dataclasses.field(
    metadata={
      "required": True,
      "description": "UptimeKuma Password",
      "sensitive": True,
    },
    default=None,
  )

class UptimekumaProvider(BaseProvider):
  PROVIDER_DISPLAY_NAME = "UptimeKuma"
  PROVIDER_TAGS = ["alert"]

  PROVIDER_SCOPES = [
    ProviderScope(
      name="alerts",
      description="Read alerts from UptimeKuma",
    )
  ]

  STATUS_MAP = {
    "up": AlertStatus.RESOLVED,
    "down": AlertStatus.FIRING,
  }

  def __init__(
      self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
      ):
    super().__init__(context_manager, provider_id, config)

  def dispose(self):
    pass

  def validate_scopes(self):
    """
    Validate that the scopes provided in the config are valid
    """
    api = UptimeKumaApi(self.authentication_config.host_url)
    response = api.login(self.authentication_config.username, self.authentication_config.password)
    api.disconnect()
    if "token" in response:
      return {"alerts": True}
    return {"alerts": False}
    
  def validate_config(self):
    self.authentication_config = UptimekumaProviderAuthConfig(**self.config.authentication)
    if self.authentication_config.host_url is None:
      raise ProviderException("UptimeKuma Host URL is required")
    if self.authentication_config.username is None:
      raise ProviderException("UptimeKuma Username is required")
    if self.authentication_config.password is None:
      raise ProviderException("UptimeKuma Password is required")
    
  def _get_heartbeats(self):
    try:
      api = UptimeKumaApi(self.authentication_config.host_url)
      api.login(self.authentication_config.username, self.authentication_config.password)
      response = api.get_heartbeats()
      api.disconnect()

      length = len(response)

      if length == 0:
        return []

      for alert in (1, length+1):
        heartbeat = response[alert][-1]

        return AlertDto(
          id=heartbeat["id"],
          monitor_id=heartbeat["monitor_id"],
          description=heartbeat["msg"],
          status=heartbeat["status"].name.lower(),
          time=heartbeat["time"],
          ping=heartbeat["ping"],
          source="uptimekuma"
        )
      
    except Exception as e:
      self.logger.error("Error getting heartbeats from UptimeKuma: %s", e)
      raise Exception(f"Error getting heartbeats from UptimeKuma: {e}")
    
  def _get_alerts(self) -> list[AlertDto]:
    try:
      self.logger.info("Collecting alerts (heartbeats) from UptimeKuma")
      alerts = self._get_heartbeats()
      return alerts
    except Exception as e:
      self.logger.error("Error getting alerts from UptimeKuma: %s", e)
      raise Exception(f"Error getting alerts from UptimeKuma: {e}")
  
  @staticmethod
  def _format_alert(
    event: dict, provider_instance: Optional["UptimekumaProvider"] = None
    ) -> AlertDto:

    status = UptimekumaProvider.STATUS_MAP.get(event["status"], AlertStatus.FIRING)

    alert = AlertDto(
      id=event["id"],
      name=event["monitor_id"],
      status=AlertStatus.FIRING,
      description=event["description"],
      time=event["time"],
      ping=event["ping"],
      source="uptimekuma"
    )

    return alert
  
if __name__ == "__main__":
  import logging

  logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
  context_manager = ContextManager(
    tenant_id="singletenant",
    workflow_id="test",
  )

  import os

  uptimekuma_host = os.environ.get("UPTIMEKUMA_HOST")
  uptimekuma_username = os.environ.get("UPTIMEKUMA_USERNAME")
  uptimekuma_password = os.environ.get("UPTIMEKUMA_PASSWORD")

  if uptimekuma_host is None:
    raise Exception("UPTIMEKUMA_HOST is required")
  if uptimekuma_username is None:
    raise Exception("UPTIMEKUMA_USERNAME is required")
  if uptimekuma_password is None:
    raise Exception("UPTIMEKUMA_PASSWORD is required")

  config = ProviderConfig(
    description="UptimeKuma Provider",
    authentication={
      "host_url": uptimekuma_host,
      "username": uptimekuma_username,
      "password": uptimekuma_password,
    },
  )

  provider = UptimekumaProvider(
    context_manager=context_manager,
    provider_id="uptimekuma",
    config=config,
  )

  alerts = provider.get_alerts()
  print(alerts)
  provider.dispose()
