"""
Nagios is a monitoring system for Infrastructure and Application Monitoring.
"""

import dataclasses
import logging
from datetime import datetime
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """Nagios authentication configuration."""

    nagios_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios server URL",
            "hint": "https://nagios.example.com",
            "validation": "https_url",
        }
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI API token",
            "hint": "Generate from Admin > System Config > API Keys",
            "sensitive": True,
        }
    )

    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify SSL certificate",
        },
    )


class NagiosProvider(BaseProvider):
    """Get alerts from Nagios into Keep"""

    SEVERITIES_MAP = {
        0: AlertSeverity.INFO,  # OK/UP
        1: AlertSeverity.WARNING,  # WARNING
        2: AlertSeverity.CRITICAL,  # CRITICAL/DOWN
        3: AlertSeverity.INFO,  # UNKNOWN/UNREACHABLE
    }

    STATUS_MAP = {
        0: AlertStatus.RESOLVED,  # OK/UP
        1: AlertStatus.FIRING,  # WARNING/DOWN/CRITICAL
        2: AlertStatus.FIRING,  # CRITICAL
        3: AlertStatus.FIRING,  # UNKNOWN/UNREACHABLE
    }

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["host_name", "service_description"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validate required configuration for Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No cleanup required for Nagios provider.
        """
        pass

    def _make_request(
        self, endpoint: str, params: Optional[dict] = None
    ) -> dict | list:
        """
        Make authenticated request to Nagios API.
        """
        url = f"{self.authentication_config.nagios_url.rstrip('/')}/api/v1/{endpoint.lstrip('/')}"
        
        default_params = {"apikey": self.authentication_config.api_key}
        if params:
            default_params.update(params)

        try:
            response = requests.get(
                url,
                params=default_params,
                verify=self.authentication_config.verify_ssl,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.exception(f"Error making request to Nagios: {e}")
            raise

    def _get_host_alerts(self) -> list[AlertDto]:
        """
        Fetch host alerts from Nagios.
        """
        self.logger.info("Fetching host alerts from Nagios")
        try:
            data = self._make_request("objects/hoststatus")
            hoststatus = data.get("hoststatus", [])
            
            alerts = []
            for host in hoststatus:
                # Only include hosts with problems (not OK)
                current_state = host.get("current_state", 0)
                if current_state == 0:
                    continue
                
                alert = self._format_host_alert(host)
                alerts.append(alert)
            
            self.logger.info(f"Fetched {len(alerts)} host alerts from Nagios")
            return alerts
        except Exception as e:
            self.logger.exception("Failed to fetch host alerts")
            return []

    def _get_service_alerts(self) -> list[AlertDto]:
        """
        Fetch service alerts from Nagios.
        """
        self.logger.info("Fetching service alerts from Nagios")
        try:
            data = self._make_request("objects/servicestatus")
            servicestatus = data.get("servicestatus", [])
            
            alerts = []
            for service in servicestatus:
                # Only include services with problems (not OK)
                current_state = service.get("current_state", 0)
                if current_state == 0:
                    continue
                
                alert = self._format_service_alert(service)
                alerts.append(alert)
            
            self.logger.info(f"Fetched {len(alerts)} service alerts from Nagios")
            return alerts
        except Exception as e:
            self.logger.exception("Failed to fetch service alerts")
            return []

    def _format_host_alert(self, host: dict) -> AlertDto:
        """
        Format a Nagios host status into an AlertDto.
        """
        current_state = host.get("current_state", 0)
        host_name = host.get("host_name", "unknown")
        
        # Determine status based on state and acknowledgement
        is_acknowledged = host.get("problem_has_been_acknowledged", 0) == 1
        status = (
            AlertStatus.ACKNOWLEDGED
            if is_acknowledged
            else self.STATUS_MAP.get(current_state, AlertStatus.FIRING)
        )

        last_check = host.get("last_check")
        if last_check:
            try:
                last_received = datetime.fromtimestamp(last_check).isoformat()
            except (ValueError, OSError):
                last_received = datetime.now().isoformat()
        else:
            last_received = datetime.now().isoformat()

        alert = AlertDto(
            id=f"host_{host_name}",
            name=f"Host: {host_name}",
            description=host.get("plugin_output", ""),
            severity=self.SEVERITIES_MAP.get(current_state, AlertSeverity.INFO),
            status=status,
            lastReceived=last_received,
            source=["nagios"],
            host_name=host_name,
            service_description=None,
            current_state=current_state,
            current_attempt=host.get("current_attempt"),
            max_attempts=host.get("max_attempts"),
            last_state_change=host.get("last_state_change"),
            notifications_enabled=host.get("notifications_enabled", 0) == 1,
            is_flapping=host.get("is_flapping", 0) == 1,
            scheduled_downtime_depth=host.get("scheduled_downtime_depth", 0),
        )
        
        alert.fingerprint = self.get_alert_fingerprint(alert, self.fingerprint_fields)
        return alert

    def _format_service_alert(self, service: dict) -> AlertDto:
        """
        Format a Nagios service status into an AlertDto.
        """
        current_state = service.get("current_state", 0)
        host_name = service.get("host_name", "unknown")
        service_description = service.get("service_description", "unknown")
        
        # Determine status based on state and acknowledgement
        is_acknowledged = service.get("problem_has_been_acknowledged", 0) == 1
        status = (
            AlertStatus.ACKNOWLEDGED
            if is_acknowledged
            else self.STATUS_MAP.get(current_state, AlertStatus.FIRING)
        )

        last_check = service.get("last_check")
        if last_check:
            try:
                last_received = datetime.fromtimestamp(last_check).isoformat()
            except (ValueError, OSError):
                last_received = datetime.now().isoformat()
        else:
            last_received = datetime.now().isoformat()

        alert = AlertDto(
            id=f"service_{host_name}_{service_description}",
            name=f"{host_name} - {service_description}",
            description=service.get("plugin_output", ""),
            severity=self.SEVERITIES_MAP.get(current_state, AlertSeverity.INFO),
            status=status,
            lastReceived=last_received,
            source=["nagios"],
            host_name=host_name,
            service_description=service_description,
            current_state=current_state,
            current_attempt=service.get("current_attempt"),
            max_attempts=service.get("max_attempts"),
            last_state_change=service.get("last_state_change"),
            notifications_enabled=service.get("notifications_enabled", 0) == 1,
            is_flapping=service.get("is_flapping", 0) == 1,
            scheduled_downtime_depth=service.get("scheduled_downtime_depth", 0),
        )
        
        alert.fingerprint = self.get_alert_fingerprint(alert, self.fingerprint_fields)
        return alert

    def _get_alerts(self) -> list[AlertDto]:
        """
        Fetch all alerts (hosts and services) from Nagios.
        """
        all_alerts = []
        
        # Fetch host alerts
        host_alerts = self._get_host_alerts()
        all_alerts.extend(host_alerts)
        
        # Fetch service alerts
        service_alerts = self._get_service_alerts()
        all_alerts.extend(service_alerts)
        
        return all_alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format incoming Nagios webhook event into AlertDto.
        """
        # Determine if this is a host or service alert
        service_description = event.get("service_description") or event.get("SERVICEDESC")
        
        if service_description:
            # Service alert
            state = event.get("state", event.get("SERVICESTATE", 0))
            if isinstance(state, str):
                state_map = {"OK": 0, "WARNING": 1, "CRITICAL": 2, "UNKNOWN": 3}
                state = state_map.get(state.upper(), 0)
            
            host_name = event.get("host_name", event.get("HOSTNAME", "unknown"))
            
            alert = AlertDto(
                id=f"service_{host_name}_{service_description}",
                name=f"{host_name} - {service_description}",
                description=event.get("output", event.get("SERVICEOUTPUT", "")),
                severity=NagiosProvider.SEVERITIES_MAP.get(state, AlertSeverity.INFO),
                status=NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING),
                lastReceived=datetime.now().isoformat(),
                source=["nagios"],
                host_name=host_name,
                service_description=service_description,
                current_state=state,
            )
        else:
            # Host alert
            state = event.get("state", event.get("HOSTSTATE", 0))
            if isinstance(state, str):
                state_map = {"UP": 0, "DOWN": 2, "UNREACHABLE": 3}
                state = state_map.get(state.upper(), 0)
            
            host_name = event.get("host_name", event.get("HOSTNAME", "unknown"))
            
            alert = AlertDto(
                id=f"host_{host_name}",
                name=f"Host: {host_name}",
                description=event.get("output", event.get("HOSTOUTPUT", "")),
                severity=NagiosProvider.SEVERITIES_MAP.get(state, AlertSeverity.INFO),
                status=NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING),
                lastReceived=datetime.now().isoformat(),
                source=["nagios"],
                host_name=host_name,
                service_description=None,
                current_state=state,
            )
        
        alert.fingerprint = NagiosProvider.get_alert_fingerprint(
            alert, NagiosProvider.FINGERPRINT_FIELDS
        )
        return alert


if __name__ == "__main__":
    pass
