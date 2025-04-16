import logging
import requests
from typing import Any, Dict, List, Optional
from datetime import datetime

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.api.models.alert import Alert, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)

class Icinga2ProviderAuthConfig:
    """Icinga2 Authentication Configuration"""
    api_url: str #Icinga2
    username: str
    password: str
    verify_ssl: bool = True

class Icinga2Provider(BaseProvider):
    """
    Provider for Icinga2 Integration
    """
    PROVIDER_TYPE = "icinga2"
    PROVIDER_NAME = "icinga2"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="write",
            description="Write access to Icinga2 (acknowledge, Schedule Downtimes)",
            mandatory=False
        ),
        ProviderScope(
            name="read",
            description="Read Access to Icinga2 Monitoring Data",
            mandatory=True
        )
    ]

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = config.authentication.get("api_url").rstrip('/')
        self.username = config.authentication.get("username")
        self.password = config.authentication.get("password")
        self.verify_ssl = config.authentication.get("verify_ssl", True)
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.verify = self.verify_ssl
        self.session.headers.update({
            'Accept': 'application/json'
        })

    def validate_scopes(self) -> dict:
        """Validate Provider Scopes"""
        validated_scopes = {}
        try:
            # Get Status Summary to Test API Access
            response = self.session.get(f"{self.api_url}/v1/status")
            response.raise_for_status()
            validated_scopes["write"] = True

            # Try getting actions for write Access Test
            write_response = self.session.get(f"{self.api_url}/v1/actions")
            write_response.raise_for_status()
            validated_scopes["write"] = True

        except Exception as e:
            validated_scopes["read"] = str(e)
            validated_scopes["write"] = str(e)
        return validated_scopes
    
    def _severity_to_alert_severity(self, state: str) -> AlertSeverity:
        """Map Icinga2 state to Keep Alert Severity"""
        SEVERITY_MAP = {
            'OK': AlertSeverity.INFO,
            'WARNING': AlertSeverity.WARNING,
            'CRITICAL': AlertSeverity.CRITICAL,
            'UNKNOWN': AlertSeverity.WARNING,
            'UP': AlertSeverity.INFO,
            'DOWN': AlertSeverity.CRITICAL
        }
        return SEVERITY_MAP.get(state, AlertSeverity.WARNING)
    
    def get_alerts(self, params: Optional[Dict[str, Any]] = None) -> List[Alert]:
        """Gets Alerts from Icinga2"""
        alerts = []
        try:
            # getting all non-OK states...
            response = self.session.get(
                f"{self.api_url}/v1/objects/services",
                params={
                    "attrs": ["name", "state", "last_check_result", "host_name", "display_name", "acknowledgement"]
                }
            )
            response.raise_for_status()
            services = response.json().get('results', [])

            for service in services:
                attrs = service.get('attrs', {})
                last_check = attrs.get('last_check_result', {})

                alert = Alert(
                    id=f"{attrs.get('host_name')}_{attrs.get('name')}",
                    source=self.PROVIDER_TYPE,
                    severity=self._severity_to_alert_severity(attrs.get('state')),
                    status=AlertStatus.RESOLVED if attrs.get('state') == 'OK' else AlertStatus.FIRING,
                    timestamp=datetime.utcnow().isoformat(),
                    name=attrs.get('display_name'),
                    description=last_check.get('output', ''),
                    labels={
                        "host": attrs.get('host_name'),
                        "service": attrs.get('name'),
                        "state": attrs.get('state'),
                        "acknowledged": bool(attrs.get('acknowledgement'))
                    }
                )
                alerts.append(alert)

        except Exception as e:
            logger.error(f"Error fetching alerts from Icinga2: {str(e)}")
            raise

        return alerts
    
    def acknowledge_alerts(self, alert_id: str, **kwargs) -> dict:
        """Acknowledge an alert in Icinga2"""
        try:
            host, service = alert_id.split('_', 1)

            data = {
                "type": "Service",
                "filter": f'service.name=="{service}" && host.name=="{host}"',
                "author": kwargs.get("author", "keep"),
                "comment": kwargs.get("comment", "Acknowledged via Keep"),
                "notify": kwargs.get("notify", True),
                "sticky": kwargs.get("sticky", True)
            }

            response = self.session.post(
                f"{self.api_url}./v1/actions/acknowledge-problem",
                json=data
            )
            response.raise_for_status()
            return {"status": "success", "message": "Alert acknowledged"}

        except Exception as x:
            logger.error(f"Error acknowledging alert in Icinga2: {str(x)}")
            raise

    def close_alert(self, alert_id: str, **kwargs) -> dict:
        """Removes acknowledgement for an Alert in Icinga2"""
        try:
            host, service = alert_id.split('_', 1)

            data = {
                "type": "Service",
                "filter": f'service.name=="{service}" && host.name=="{host}"',
                "author": kwargs.get("author", "Keep"),
                "comment": kwargs.get("comment", "Removed acknowledgement via Keep")
            }

            response = self.session.post(
                f"{self.api_url}/v1/actions/remove-acknowledgement",
                json=data
            )
            response.raise_for_status()
            return {"status": "success", "message": "Alert acknowledgement removed"}

        except Exception as x:
            logger.error(f"Error removing acknowledgement in Icinga2: {str(x)}")
            raise
