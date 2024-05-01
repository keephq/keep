"""
Statuscake is a class that provides a way to read alerts from the Statuscake API
"""

import dataclasses

import pydantic
import requests
from typing import Optional

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

@pydantic.dataclasses.dataclass
class StatuscakeProviderAuthConfig:
  """
  StatuscakeProviderAuthConfig is a class that holds the authentication information for the StatuscakeProvider.
  """

  api_key: str = dataclasses.field(
    metadata={
      "required": True,
      "description": "Statuscake API Key",
      "sensitive": True,
    },
    default=None,
  )

class StatuscakeProvider(BaseProvider):
  PROVIDER_DISPLAY_NAME = "Statuscake"
  PROVIDER_TAGS = ["alert"]

  PROVIDER_SCOPES = [
    ProviderScope(
      name="alerts",
      description="Read alerts from Statuscake",
    )
  ]

  SEVERITIES_MAP = {
    "high": AlertSeverity.HIGH,
  }

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
    Validate that the user has the required scopes to use the provider
    """
    try:
      response = requests.get('https://api.statuscake.com/v1/uptime/', headers=self.__get_auth_headers())

      if response.status_code == 200:
        scopes = {
          "alerts": True
        }

      else:
        self.logger.error("Unable to read alerts from Statuscake, statusCode: %s", response.status_code)
        scopes = {
          "alerts": f"Unable to read alerts from Statuscake, statusCode: {response.status_code}"
        }
    
    except Exception as e:
      self.logger.error("Error validating scopes for Statuscake: %s", e)
      scopes = {
        "alerts": f"Error validating scopes for Statuscake: {e}"
      }

    return scopes

  def validate_config(self):
    self.authentication_config = StatuscakeProviderAuthConfig(**self.config.authentication)
    if self.authentication_config.api_key is None:
      raise ValueError("Statuscake API Key is required")

  def __get_auth_headers(self):
    if self.authentication_config.api_key is not None:
      return {
        "Authorization": f"Bearer {self.authentication_config.api_key}"
      }

  def __get_heartbeat_alerts(self) -> list[AlertDto]:
    try:
      response = requests.get('https://api.statuscake.com/v1/uptime/', headers=self.__get_auth_headers())

      if not response.ok:
        self.logger.error("Failed to get heartbeat from Statuscake: %s", response.json())
        raise Exception("Could not get heartbeat from Statuscake")
      
      return [AlertDto(
        id=alert["id"],
        name=alert["name"],
        status=alert["status"],
        url=alert["website_url"],
        uptime=alert["uptime"],
        source="statuscake"
      ) for alert in response.json()["data"]]
    
    except Exception as e:
      self.logger.error("Error getting heartbeat from Statuscake: %s", e)
      raise Exception(f"Error getting heartbeat from Statuscake: {e}")
    
  def __get_pagespeed_alerts(self) -> list[AlertDto]:
    try:
      response = requests.get('https://api.statuscake.com/v1/pagespeed/', headers=self.__get_auth_headers())

      if not response.ok:
        self.logger.error("Failed to get pagespeed from Statuscake: %s", response.json())
        raise Exception("Could not get pagespeed from Statuscake")
      
      return [AlertDto(
        name=alert["name"],
        url=alert["website_url"],
        location=alert["location"],
        alert_smaller=alert["alert_smaller"],
        alert_bigger=alert["alert_bigger"],
        alert_slower=alert["alert_slower"],
        status=alert["status"],
        source="statuscake"
      ) for alert in response.json()["data"]]
    
    except Exception as e:
      self.logger.error("Error getting pagespeed from Statuscake: %s", e)
      raise Exception(f"Error getting pagespeed from Statuscake: {e}")
    
  def __get_ssl_alerts(self) -> list[AlertDto]:
    try:
      response = requests.get('https://api.statuscake.com/v1/ssl/', headers=self.__get_auth_headers())

      if not response.ok:
        self.logger.error("Failed to get ssl from Statuscake: %s", response.json())
        raise Exception("Could not get ssl from Statuscake")
      
      return [AlertDto(
        id=alert["id"],
        url=alert["website_url"],
        issuer_common_name=alert["issuer_common_name"],
        cipher=alert["cipher"],
        cipher_score=alert["cipher_score"],
        certificate_score=alert["certificate_score"],
        certificate_status=alert["certificate_status"],
        valid_from=alert["valid_from"],
        valid_until=alert["valid_until"],
        source="statuscake"
      ) for alert in response.json()["data"]]
    
    except Exception as e:
      self.logger.error("Error getting ssl from Statuscake: %s", e)
      raise Exception(f"Error getting ssl from Statuscake: {e}")

  def __get_uptime_alerts(self) -> list[AlertDto]:
    try:
      response = requests.get('https://api.statuscake.com/v1/uptime/', headers=self.__get_auth_headers())

      if not response.ok:
        self.logger.error("Failed to get uptime from Statuscake: %s", response.json())
        raise Exception("Could not get uptime from Statuscake")
      
      return [AlertDto(
        id=alert["id"],
        name=alert["name"],
        status=alert["status"],
        url=alert["website_url"],
        uptime=alert["uptime"],
        source="statuscake"
      ) for alert in response.json()["data"]]
    
    except Exception as e:
      self.logger.error("Error getting uptime from Statuscake: %s", e)
      raise Exception(f"Error getting uptime from Statuscake: {e}")
    
  def _get_alerts(self) -> list[AlertDto]:
    alerts = []
    try:
      self.logger.info("Collecting alerts (heartbeats) from Statuscake")
      heartbeat_alerts = self.__get_heartbeat_alerts()
      alerts.extend(heartbeat_alerts)
    except Exception as e:
      self.logger.error("Error getting heartbeat from Statuscake: %s", e)

    try:
      self.logger.info("Collecting alerts (pagespeed) from Statuscake")
      pagespeed_alerts = self.__get_pagespeed_alerts()
      alerts.extend(pagespeed_alerts)
    except Exception as e:
      self.logger.error("Error getting pagespeed from Statuscake: %s", e)

    try:
      self.logger.info("Collecting alerts (ssl) from Statuscake")
      ssl_alerts = self.__get_ssl_alerts()
      alerts.extend(ssl_alerts)
    except Exception as e:
      self.logger.error("Error getting ssl from Statuscake: %s", e)

    try:
      self.logger.info("Collecting alerts (uptime) from Statuscake")
      uptime_alerts = self.__get_uptime_alerts()
      alerts.extend(uptime_alerts)
    except Exception as e:
      self.logger.error("Error getting uptime from Statuscake: %s", e)
      
    return alerts
  
  @staticmethod
  def _format_alert(
    event: dict, provider_instance: Optional["StatuscakeProvider"] = None
  ) -> AlertDto:
    
    status = StatuscakeProvider.STATUS_MAP.get(event.get("status"),AlertStatus.FIRING)

    # Statuscake does not provide severity information
    severity = AlertSeverity.HIGH

    alert = AlertDto(
      id=event.get("id"),
      name=event.get("name"),
      status=status if status is not None else AlertStatus.FIRING,
      severity=severity,
      url=event["website_url"] if "website_url" in event else None,
      source="statuscake"
    )

    return alert

if __name__ == "__main__":
  pass
  import logging

  logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
  context_manager = ContextManager(
    tenant_id="singletenant",
    workflow_id="test",
  )

  import os

  statuscake_api_key = os.environ.get("STATUSCAKE_API_KEY")

  if statuscake_api_key is None:
    raise Exception("STATUSCAKE_API_KEY is required")
  
  config = ProviderConfig(
    description="Statuscake Provider",
    authentication={
      "api_key": statuscake_api_key
    },
  )

  provider = StatuscakeProvider(
    context_manager,
    provider_id="statuscake",
    config=config,
  )

  provider._get_alerts()