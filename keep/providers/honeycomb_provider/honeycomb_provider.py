"""
HoneycombProvider is a class that integrates Keep with Honeycomb,
an observability platform for high-cardinality event data and distributed tracing.
Supports pulling triggered alerts and receiving real-time webhook notifications.
"""

import dataclasses
import datetime
from typing import List, Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class HoneycombProviderAuthConfig:
    """
    HoneycombProviderAuthConfig holds the Honeycomb API key and dataset configuration.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Honeycomb API Key",
            "sensitive": True,
            "hint": "Find it in Honeycomb → Account Settings → API Keys",
        },
    )

    dataset: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Honeycomb dataset name (leave blank to query all datasets)",
            "sensitive": False,
        },
    )


class HoneycombProvider(BaseProvider):
    """Pull triggered alerts from Honeycomb and receive real-time webhook notifications."""

    PROVIDER_DISPLAY_NAME = "Honeycomb"
    PROVIDER_TAGS = ["alert", "tracing"]
    PROVIDER_CATEGORY = ["Monitoring", "Tracing"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_triggers",
            description="Read triggered alerts from Honeycomb",
            mandatory=True,
        ),
    ]

    HONEYCOMB_API_URL = "https://api.honeycomb.io"

    # Honeycomb trigger state → Keep AlertStatus
    # "triggered" = condition met (firing), "ok" = condition cleared (resolved)
    STATUS_MAP = {
        "triggered": AlertStatus.FIRING,
        "ok": AlertStatus.RESOLVED,
        "ok_with_no_data": AlertStatus.RESOLVED,
    }

    # Honeycomb severity/threshold direction → Keep AlertSeverity
    # Honeycomb doesn't have a direct severity field on triggers;
    # we infer from alert_type or use INFO as default
    SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = HoneycombProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _get_headers(self) -> dict:
        return {
            "X-Honeycomb-Team": self.authentication_config.api_key,
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            # Use the auth endpoint to verify the API key works
            response = requests.get(
                f"{self.HONEYCOMB_API_URL}/1/auth",
                headers=self._get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                return {"read_triggers": True}
            else:
                return {
                    "read_triggers": f"HTTP {response.status_code}: {response.text[:200]}"
                }
        except Exception as e:
            self.logger.error("Error validating Honeycomb scopes: %s", e)
            return {"read_triggers": str(e)}

    def _get_datasets(self) -> List[str]:
        """Return list of dataset slugs to query."""
        if self.authentication_config.dataset:
            return [self.authentication_config.dataset]

        # List all datasets in the environment
        try:
            response = requests.get(
                f"{self.HONEYCOMB_API_URL}/1/datasets",
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            return [ds["slug"] for ds in response.json()]
        except Exception as e:
            self.logger.warning("Could not list datasets, using __all__: %s", e)
            return ["__all__"]

    def _get_triggers_for_dataset(self, dataset: str) -> List[dict]:
        """Fetch all triggers (alert rules) for a given dataset."""
        try:
            response = requests.get(
                f"{self.HONEYCOMB_API_URL}/1/triggers/{dataset}",
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(
                "Error fetching triggers for dataset %s: %s", dataset, e
            )
            return []

    def _get_alerts(self) -> List[AlertDto]:
        """Pull all triggered alerts from Honeycomb."""
        alerts = []
        datasets = self._get_datasets()

        for dataset in datasets:
            triggers = self._get_triggers_for_dataset(dataset)
            for trigger in triggers:
                # Only surface triggered (firing) alerts when pulling
                state = trigger.get("triggered_at") is not None
                alert = self._trigger_to_alert(trigger, dataset)
                alerts.append(alert)

        self.logger.info(
            "Fetched %d triggers from %d Honeycomb datasets",
            len(alerts),
            len(datasets),
        )
        return alerts

    def _trigger_to_alert(self, trigger: dict, dataset: str) -> AlertDto:
        trigger_id = trigger.get("id", "")
        name = trigger.get("name", "Honeycomb Trigger")
        description = trigger.get("description", "")
        disabled = trigger.get("disabled", False)

        triggered_at = trigger.get("triggered_at")
        if triggered_at:
            try:
                last_received = datetime.datetime.fromisoformat(
                    triggered_at.replace("Z", "+00:00")
                ).isoformat()
                status = AlertStatus.FIRING
            except (ValueError, AttributeError):
                last_received = datetime.datetime.utcnow().isoformat()
                status = AlertStatus.FIRING
        else:
            last_received = datetime.datetime.utcnow().isoformat()
            status = AlertStatus.RESOLVED if not disabled else AlertStatus.SUPPRESSED

        # Honeycomb triggers fire when a threshold is exceeded; treat as WARNING by default
        severity = AlertSeverity.WARNING

        return AlertDto(
            id=trigger_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["honeycomb"],
            dataset=dataset,
            trigger_id=trigger_id,
            disabled=disabled,
            url=trigger.get("url", f"https://ui.honeycomb.io/triggers/{trigger_id}"),
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Parse a Honeycomb trigger webhook payload.

        Honeycomb sends a JSON payload when a trigger fires or resolves.
        Key fields: id, name, description, status, triggered_at, dataset,
                    result_url, threshold, operator, value
        """
        trigger_id = event.get("id", "")
        name = event.get("name", "Honeycomb Trigger")
        description = event.get("description", "")
        status_str = event.get("status", "triggered").lower()
        dataset = event.get("dataset", "")

        status = HoneycombProvider.STATUS_MAP.get(status_str, AlertStatus.FIRING)

        # Infer severity from alert_type if present, default to WARNING for triggers
        alert_type = (event.get("alert_type") or "").lower()
        severity = HoneycombProvider.SEVERITY_MAP.get(alert_type, AlertSeverity.WARNING)

        # Parse triggered_at timestamp
        triggered_at = event.get("triggered_at")
        if triggered_at:
            try:
                last_received = datetime.datetime.fromisoformat(
                    triggered_at.replace("Z", "+00:00")
                ).isoformat()
            except (ValueError, AttributeError):
                last_received = datetime.datetime.utcnow().isoformat()
        else:
            last_received = datetime.datetime.utcnow().isoformat()

        return AlertDto(
            id=trigger_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["honeycomb"],
            dataset=dataset,
            trigger_id=trigger_id,
            result_url=event.get("result_url", ""),
            threshold=event.get("threshold"),
            operator=event.get("operator"),
            trigger_value=event.get("value"),
            url=event.get("result_url", ""),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("HONEYCOMB_API_KEY")
    dataset = os.environ.get("HONEYCOMB_DATASET")

    if not api_key:
        raise Exception("HONEYCOMB_API_KEY is required")

    config = ProviderConfig(
        description="Honeycomb Provider",
        authentication={
            "api_key": api_key,
            "dataset": dataset,
        },
    )

    provider = HoneycombProvider(
        context_manager=context_manager,
        provider_id="honeycomb",
        config=config,
    )

    scopes = provider.validate_scopes()
    print("Scopes:", scopes)

    alerts = provider.get_alerts()
    print(f"Got {len(alerts)} triggers")
    for alert in alerts[:5]:
        print(alert)
