"""
RootlyProvider integrates Keep with the Rootly incident management platform.

Supports:
  - Pull alerts from Rootly's Alerts API (GET /v1/alerts)
  - Pull incidents from Rootly's Incidents API (GET /v1/incidents)
  - Receive webhook events from Rootly
  - Create incidents via _notify()
  - Resolve/acknowledge alerts via _notify()
"""

import dataclasses
from datetime import datetime, timezone
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class RootlyProviderAuthConfig:
    """Authentication configuration for the Rootly provider."""

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Rootly API Key (Global, Team, or Personal)",
            "sensitive": True,
            "hint": "Organization Settings → API Keys → Generate New API Key",
        }
    )

    api_url: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Rootly API base URL",
            "hint": "https://api.rootly.com (default)",
        },
        default="https://api.rootly.com",
    )

    pull_incidents: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Also pull incidents (in addition to alerts)",
            "hint": "true or false",
        },
        default=True,
    )


class RootlyProvider(BaseProvider):
    """
    Rootly provider for incident management and alert aggregation.

    Pulls alerts and incidents from Rootly and converts them to Keep AlertDtos.
    Also receives Rootly webhook events for real-time alert ingestion.
    """

    PROVIDER_DISPLAY_NAME = "Rootly"
    PROVIDER_CATEGORY = ["Incident Management"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated with Rootly API",
            mandatory=True,
            alias="Authenticated",
        ),
        ProviderScope(
            name="read_alerts",
            description="User can read alerts from Rootly",
            mandatory=True,
            alias="Read Alerts",
        ),
        ProviderScope(
            name="read_incidents",
            description="User can read incidents from Rootly",
            mandatory=False,
            alias="Read Incidents",
        ),
    ]

    FINGERPRINT_FIELDS = ["id"]

    # Rootly incident severity → Keep AlertSeverity
    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "major": AlertSeverity.HIGH,
        "medium": AlertSeverity.WARNING,
        "warning": AlertSeverity.WARNING,
        "low": AlertSeverity.LOW,
        "minor": AlertSeverity.LOW,
        "info": AlertSeverity.INFO,
    }

    # Rootly alert/incident status → Keep AlertStatus
    STATUS_MAP = {
        # Alert statuses
        "open": AlertStatus.FIRING,
        "triggered": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "resolved": AlertStatus.RESOLVED,
        "noise": AlertStatus.SUPPRESSED,
        # Incident statuses
        "started": AlertStatus.FIRING,
        "in_triage": AlertStatus.ACKNOWLEDGED,
        "mitigated": AlertStatus.PENDING,
        "closed": AlertStatus.RESOLVED,
        "cancelled": AlertStatus.SUPPRESSED,
    }

    webhook_description = "Receive Rootly alerts and incident events"
    webhook_markdown = """
To send Rootly events to Keep, configure a webhook in Rootly:

1. Go to **Rootly** → **Settings** → **Integrations** → **Webhooks**
2. Click **Add Webhook**
3. Set the **Endpoint URL** to: `{keep_webhook_api_url}`
4. Under **Events**, select the events you want to forward:
   - `alert.created`, `alert.updated`, `alert.resolved`
   - `incident.created`, `incident.updated`, `incident.mitigated`, `incident.resolved`, `incident.cancelled`
5. Add a header `X-API-KEY: {api_key}` under **Headers**
6. Click **Save**

Keep will now receive real-time alerts and incident updates from Rootly.
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """No resources to dispose."""
        pass

    def validate_config(self):
        self.authentication_config = RootlyProviderAuthConfig(
            **self.config.authentication
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_key}",
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
        }

    @property
    def _api_base(self) -> str:
        url = (self.authentication_config.api_url or "https://api.rootly.com").rstrip("/")
        return url

    def _api_get(self, path: str, params: dict | None = None) -> requests.Response:
        url = f"{self._api_base}/{path.lstrip('/')}"
        return requests.get(url, headers=self._headers, params=params, timeout=30)

    def _api_post(self, path: str, json_data: dict) -> requests.Response:
        url = f"{self._api_base}/{path.lstrip('/')}"
        return requests.post(url, headers=self._headers, json=json_data, timeout=30)

    def _api_put(self, path: str, json_data: dict) -> requests.Response:
        url = f"{self._api_base}/{path.lstrip('/')}"
        return requests.put(url, headers=self._headers, json=json_data, timeout=30)

    # ------------------------------------------------------------------
    # Scope validation
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}

        # Check authentication by listing alerts (page size 1)
        try:
            resp = self._api_get(
                "/v1/alerts", params={"page[size]": 1}
            )
            if resp.status_code == 200:
                scopes["authenticated"] = True
                scopes["read_alerts"] = True
            elif resp.status_code == 401:
                scopes["authenticated"] = "Authentication failed (invalid API key)"
                scopes["read_alerts"] = "Cannot verify — not authenticated"
                scopes["read_incidents"] = "Cannot verify — not authenticated"
                return scopes
            elif resp.status_code == 403:
                scopes["authenticated"] = True
                scopes["read_alerts"] = "Insufficient permissions to read alerts"
            else:
                scopes["authenticated"] = (
                    f"Unexpected response (HTTP {resp.status_code})"
                )
                scopes["read_alerts"] = "Cannot verify"
        except Exception as e:
            scopes["authenticated"] = str(e)
            scopes["read_alerts"] = "Cannot verify — connection error"
            scopes["read_incidents"] = "Cannot verify — connection error"
            return scopes

        # Check incidents access
        try:
            resp = self._api_get(
                "/v1/incidents", params={"page[size]": 1}
            )
            if resp.status_code == 200:
                scopes["read_incidents"] = True
            elif resp.status_code == 403:
                scopes["read_incidents"] = "Insufficient permissions to read incidents"
            else:
                scopes["read_incidents"] = (
                    f"Cannot read incidents (HTTP {resp.status_code})"
                )
        except Exception as e:
            scopes["read_incidents"] = str(e)

        return scopes

    # ------------------------------------------------------------------
    # Alert pulling
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull alerts and optionally incidents from Rootly.

        Fetches open alerts first, then optionally active incidents.
        Both are converted to AlertDto format.
        """
        alerts: list[AlertDto] = []

        # Pull alerts
        alerts.extend(self._pull_alerts())

        # Pull incidents if configured
        if self.authentication_config.pull_incidents:
            alerts.extend(self._pull_incidents())

        return alerts

    def _pull_alerts(self) -> list[AlertDto]:
        """Fetch alerts from Rootly Alerts API with pagination."""
        alerts: list[AlertDto] = []
        page = 1
        max_pages = 10  # Safety limit

        while page <= max_pages:
            try:
                resp = self._api_get(
                    "/v1/alerts",
                    params={
                        "page[number]": page,
                        "page[size]": 100,
                    },
                )

                if not resp.ok:
                    self.logger.error(
                        f"Failed to fetch Rootly alerts: HTTP {resp.status_code}"
                    )
                    break

                data = resp.json()
                items = data.get("data", [])

                if not items:
                    break

                for item in items:
                    alert = self._rootly_alert_to_dto(item)
                    if alert:
                        alerts.append(alert)

                # Check for next page
                meta = data.get("meta", {})
                next_page = meta.get("next_page")
                if not next_page:
                    break
                page = next_page

            except Exception as e:
                self.logger.error(
                    "Error fetching Rootly alerts",
                    extra={"error": str(e), "page": page},
                )
                break

        self.logger.info(f"Fetched {len(alerts)} alerts from Rootly")
        return alerts

    def _pull_incidents(self) -> list[AlertDto]:
        """Fetch incidents from Rootly Incidents API with pagination."""
        alerts: list[AlertDto] = []
        page = 1
        max_pages = 10

        while page <= max_pages:
            try:
                resp = self._api_get(
                    "/v1/incidents",
                    params={
                        "page[number]": page,
                        "page[size]": 100,
                    },
                )

                if not resp.ok:
                    self.logger.error(
                        f"Failed to fetch Rootly incidents: HTTP {resp.status_code}"
                    )
                    break

                data = resp.json()
                items = data.get("data", [])

                if not items:
                    break

                for item in items:
                    alert = self._rootly_incident_to_dto(item)
                    if alert:
                        alerts.append(alert)

                meta = data.get("meta", {})
                next_page = meta.get("next_page")
                if not next_page:
                    break
                page = next_page

            except Exception as e:
                self.logger.error(
                    "Error fetching Rootly incidents",
                    extra={"error": str(e), "page": page},
                )
                break

        self.logger.info(f"Fetched {len(alerts)} incidents from Rootly")
        return alerts

    # ------------------------------------------------------------------
    # Data mapping
    # ------------------------------------------------------------------

    def _rootly_alert_to_dto(self, alert_data: dict) -> AlertDto | None:
        """Convert a Rootly alert (JSON:API resource) to AlertDto."""
        try:
            attrs = alert_data.get("attributes", alert_data)
            alert_id = alert_data.get("id", attrs.get("short_id", "unknown"))

            status_str = attrs.get("status", "open")
            noise = attrs.get("noise", "")
            status = self.STATUS_MAP.get(status_str, AlertStatus.FIRING)

            # If marked as noise, suppress
            if noise == "noise":
                status = AlertStatus.SUPPRESSED

            summary = attrs.get("summary", "")
            description = attrs.get("description", "")
            source = attrs.get("source", "rootly")
            external_url = attrs.get("external_url", "")
            created_at = attrs.get("created_at", "")
            updated_at = attrs.get("updated_at", "")
            started_at = attrs.get("started_at", "")
            ended_at = attrs.get("ended_at", "")
            dedup_key = attrs.get("deduplication_key", "")

            # Extract service names
            services = attrs.get("services", [])
            service_names = [s.get("name", "") for s in services if s.get("name")]
            service = ", ".join(service_names) if service_names else ""

            # Extract environment names
            environments = attrs.get("environments", [])
            env_names = [e.get("name", "") for e in environments if e.get("name")]
            environment = ", ".join(env_names) if env_names else ""

            # Extract group names
            groups = attrs.get("groups", [])
            group_names = [g.get("name", "") for g in groups if g.get("name")]

            # Extract labels
            raw_labels = attrs.get("labels", [])
            labels_dict = {}
            if isinstance(raw_labels, list):
                for label in raw_labels:
                    if isinstance(label, dict):
                        key = label.get("key", "")
                        val = label.get("value", "")
                        if key:
                            labels_dict[key] = val
            elif isinstance(raw_labels, dict):
                labels_dict = raw_labels

            labels_dict["source"] = source
            labels_dict["type"] = "alert"
            if group_names:
                labels_dict["groups"] = ", ".join(group_names)
            if dedup_key:
                labels_dict["deduplication_key"] = dedup_key

            # Determine severity from alert urgency or labels
            severity = self._resolve_alert_severity(attrs)

            return AlertDto(
                id=str(alert_id),
                name=summary or f"Rootly Alert {alert_id}",
                status=status,
                severity=severity,
                lastReceived=updated_at or started_at or created_at or datetime.now(timezone.utc).isoformat(),
                source=["rootly"],
                message=summary,
                description=description,
                url=external_url,
                service=service,
                environment=environment,
                labels=labels_dict,
                fingerprint=f"rootly-alert-{alert_id}",
            )
        except Exception as e:
            self.logger.error(
                "Error mapping Rootly alert to AlertDto",
                extra={"error": str(e), "alert_id": alert_data.get("id")},
            )
            return None

    def _rootly_incident_to_dto(self, incident_data: dict) -> AlertDto | None:
        """Convert a Rootly incident (JSON:API resource) to AlertDto."""
        try:
            attrs = incident_data.get("attributes", incident_data)
            incident_id = incident_data.get("id", attrs.get("id", "unknown"))

            title = attrs.get("title", f"Rootly Incident {incident_id}")
            summary = attrs.get("summary", "")
            status_str = attrs.get("status", "started")
            url = attrs.get("url", attrs.get("short_url", ""))
            created_at = attrs.get("created_at", "")
            updated_at = attrs.get("updated_at", "")

            status = self.STATUS_MAP.get(status_str, AlertStatus.FIRING)

            # Extract severity
            severity_data = attrs.get("severity", {})
            severity = AlertSeverity.WARNING
            if severity_data:
                if isinstance(severity_data, dict):
                    # Nested severity object: {"data": {"attributes": {"severity": "critical"}}}
                    sev_attrs = severity_data
                    if "data" in severity_data:
                        sev_attrs = severity_data["data"].get("attributes", severity_data)
                    sev_name = sev_attrs.get("severity", sev_attrs.get("name", "")).lower()
                    severity = self.SEVERITIES_MAP.get(sev_name, AlertSeverity.WARNING)

            # Extract services
            services = attrs.get("services", [])
            service_names = []
            for svc in services:
                if isinstance(svc, dict):
                    svc_data = svc.get("data", svc)
                    svc_attrs = svc_data.get("attributes", svc_data)
                    name = svc_attrs.get("name", "")
                    if name:
                        service_names.append(name)
            service = ", ".join(service_names) if service_names else ""

            # Extract environments
            environments = attrs.get("environments", [])
            env_names = []
            for env in environments:
                if isinstance(env, dict):
                    env_data = env.get("data", env)
                    env_attrs = env_data.get("attributes", env_data)
                    name = env_attrs.get("name", "")
                    if name:
                        env_names.append(name)
            environment = ", ".join(env_names) if env_names else ""

            # Extract labels
            raw_labels = attrs.get("labels", {})
            labels_dict = {}
            if isinstance(raw_labels, list):
                for label in raw_labels:
                    if isinstance(label, dict):
                        key = label.get("key", "")
                        val = label.get("value", "")
                        if key:
                            labels_dict[key] = val
            elif isinstance(raw_labels, dict):
                labels_dict = dict(raw_labels)

            labels_dict["type"] = "incident"
            labels_dict["status"] = status_str

            # Build rich description
            description = f"**{title}**"
            if summary:
                description += f"\n\n{summary}"

            # Include key timestamps
            timestamps = {}
            for ts_field in [
                "in_triage_at", "started_at", "detected_at",
                "acknowledged_at", "mitigated_at", "resolved_at",
                "closed_at", "cancelled_at",
            ]:
                val = attrs.get(ts_field)
                if val:
                    timestamps[ts_field] = val
                    labels_dict[ts_field] = val

            # Sequential ID
            seq_id = attrs.get("sequential_id")
            if seq_id:
                labels_dict["sequential_id"] = str(seq_id)

            # Slack channel
            slack_channel = attrs.get("slack_channel_name")
            if slack_channel:
                labels_dict["slack_channel"] = slack_channel

            return AlertDto(
                id=str(incident_id),
                name=title,
                status=status,
                severity=severity,
                lastReceived=updated_at or created_at or datetime.now(timezone.utc).isoformat(),
                source=["rootly"],
                message=title,
                description=description,
                description_format="markdown",
                url=url,
                service=service,
                environment=environment,
                labels=labels_dict,
                fingerprint=f"rootly-incident-{incident_id}",
            )
        except Exception as e:
            self.logger.error(
                "Error mapping Rootly incident to AlertDto",
                extra={"error": str(e), "incident_id": incident_data.get("id")},
            )
            return None

    def _resolve_alert_severity(self, attrs: dict) -> AlertSeverity:
        """
        Determine severity for a Rootly alert.

        Rootly alerts don't have a direct severity field like incidents.
        We infer from the alert urgency or labels.
        """
        # Check alert urgency ID naming convention
        urgency_id = attrs.get("alert_urgency_id", "")
        if urgency_id:
            urgency_lower = str(urgency_id).lower()
            for key, sev in self.SEVERITIES_MAP.items():
                if key in urgency_lower:
                    return sev

        # Check labels for severity hints
        labels = attrs.get("labels", [])
        if isinstance(labels, list):
            for label in labels:
                if isinstance(label, dict):
                    key = label.get("key", "").lower()
                    val = label.get("value", "").lower()
                    if key in ("severity", "priority", "urgency"):
                        return self.SEVERITIES_MAP.get(val, AlertSeverity.WARNING)

        return AlertSeverity.WARNING

    # ------------------------------------------------------------------
    # Webhook (format incoming events)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict | list[dict],
        provider_instance: "BaseProvider" = None,
    ) -> AlertDto | list[AlertDto] | None:
        """
        Format incoming Rootly webhook events into AlertDto(s).

        Rootly webhooks can send:
        - alert.created, alert.updated, alert.resolved
        - incident.created, incident.updated, incident.mitigated,
          incident.resolved, incident.cancelled
        """
        if isinstance(event, list):
            alerts = []
            for e in event:
                result = RootlyProvider._format_single_webhook(e)
                if result:
                    alerts.append(result)
            return alerts if alerts else None

        return RootlyProvider._format_single_webhook(event)

    @staticmethod
    def _format_single_webhook(event: dict) -> AlertDto | None:
        """Format a single Rootly webhook event."""
        event_type = event.get("type", event.get("event", ""))
        resource = event.get("data", event)

        # Determine if this is an alert or incident event
        if "alert" in event_type.lower():
            return RootlyProvider._webhook_alert_to_dto(resource, event_type)
        elif "incident" in event_type.lower():
            return RootlyProvider._webhook_incident_to_dto(resource, event_type)

        # Fallback: try to infer from data structure
        attrs = resource.get("attributes", resource)
        if "short_id" in attrs or "noise" in attrs:
            return RootlyProvider._webhook_alert_to_dto(resource, event_type)
        elif "title" in attrs or "severity" in attrs:
            return RootlyProvider._webhook_incident_to_dto(resource, event_type)

        return None

    @staticmethod
    def _webhook_alert_to_dto(data: dict, event_type: str = "") -> AlertDto | None:
        """Convert a webhook alert payload to AlertDto."""
        try:
            attrs = data.get("attributes", data)
            alert_id = data.get("id", attrs.get("short_id", "unknown"))
            summary = attrs.get("summary", "")
            description = attrs.get("description", "")
            status_str = attrs.get("status", "open")
            source = attrs.get("source", "rootly")
            external_url = attrs.get("external_url", "")
            updated_at = attrs.get("updated_at", "")

            # Map to resolved if event says so
            if "resolved" in event_type.lower():
                status = AlertStatus.RESOLVED
            else:
                status = RootlyProvider.STATUS_MAP.get(status_str, AlertStatus.FIRING)

            # Extract services
            services = attrs.get("services", [])
            service_names = [s.get("name", "") for s in services if isinstance(s, dict) and s.get("name")]
            service = ", ".join(service_names) if service_names else ""

            labels = {
                "source": source,
                "type": "alert",
                "event_type": event_type,
            }

            return AlertDto(
                id=str(alert_id),
                name=summary or f"Rootly Alert {alert_id}",
                status=status,
                severity=AlertSeverity.WARNING,
                lastReceived=updated_at or datetime.now(timezone.utc).isoformat(),
                source=["rootly"],
                message=summary,
                description=description,
                url=external_url,
                service=service,
                labels=labels,
                fingerprint=f"rootly-alert-{alert_id}",
            )
        except Exception:
            return None

    @staticmethod
    def _webhook_incident_to_dto(data: dict, event_type: str = "") -> AlertDto | None:
        """Convert a webhook incident payload to AlertDto."""
        try:
            attrs = data.get("attributes", data)
            incident_id = data.get("id", attrs.get("id", "unknown"))
            title = attrs.get("title", f"Rootly Incident {incident_id}")
            summary = attrs.get("summary", "")
            status_str = attrs.get("status", "started")
            url = attrs.get("url", attrs.get("short_url", ""))
            updated_at = attrs.get("updated_at", "")

            # Override status based on event type
            if "resolved" in event_type.lower() or "closed" in event_type.lower():
                status = AlertStatus.RESOLVED
            elif "mitigated" in event_type.lower():
                status = AlertStatus.PENDING
            elif "cancelled" in event_type.lower():
                status = AlertStatus.SUPPRESSED
            else:
                status = RootlyProvider.STATUS_MAP.get(status_str, AlertStatus.FIRING)

            # Extract severity
            severity = AlertSeverity.WARNING
            severity_data = attrs.get("severity", {})
            if isinstance(severity_data, dict):
                sev_attrs = severity_data
                if "data" in severity_data:
                    sev_attrs = severity_data["data"].get("attributes", severity_data)
                sev_name = sev_attrs.get("severity", sev_attrs.get("name", "")).lower()
                severity = RootlyProvider.SEVERITIES_MAP.get(sev_name, AlertSeverity.WARNING)

            description = f"**{title}**"
            if summary:
                description += f"\n\n{summary}"

            labels = {
                "type": "incident",
                "status": status_str,
                "event_type": event_type,
            }

            return AlertDto(
                id=str(incident_id),
                name=title,
                status=status,
                severity=severity,
                lastReceived=updated_at or datetime.now(timezone.utc).isoformat(),
                source=["rootly"],
                message=title,
                description=description,
                description_format="markdown",
                url=url,
                labels=labels,
                fingerprint=f"rootly-incident-{incident_id}",
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Notify (create/update incidents)
    # ------------------------------------------------------------------

    def _notify(
        self,
        title: str = "",
        summary: str = "",
        severity: str = "",
        status: str = "",
        incident_id: str = "",
        alert_id: str = "",
        **kwargs,
    ):
        """
        Create or update a Rootly incident, or resolve an alert.

        - To create an incident: provide title and optionally summary, severity
        - To update an incident: provide incident_id and fields to update
        - To resolve an alert: provide alert_id and status='resolved'
        """
        if alert_id:
            # Update alert status
            payload = {
                "data": {
                    "type": "alerts",
                    "attributes": {
                        "status": status or "resolved",
                    },
                }
            }
            resp = self._api_put(f"/v1/alerts/{alert_id}", payload)
            self.logger.info(
                f"Updated Rootly alert {alert_id}: {resp.status_code}"
            )
            return {"status": resp.ok, "status_code": resp.status_code}

        if incident_id:
            # Update incident
            attributes = {}
            if title:
                attributes["title"] = title
            if summary:
                attributes["summary"] = summary
            if status:
                attributes["status"] = status

            payload = {
                "data": {
                    "type": "incidents",
                    "attributes": attributes,
                }
            }
            resp = self._api_put(f"/v1/incidents/{incident_id}", payload)
            self.logger.info(
                f"Updated Rootly incident {incident_id}: {resp.status_code}"
            )
            return {"status": resp.ok, "status_code": resp.status_code}

        # Create new incident
        if not title:
            raise ValueError("'title' is required to create a Rootly incident")

        attributes = {"title": title}
        if summary:
            attributes["summary"] = summary

        payload = {
            "data": {
                "type": "incidents",
                "attributes": attributes,
            }
        }

        resp = self._api_post("/v1/incidents", payload)
        self.logger.info(f"Created Rootly incident: {resp.status_code}")

        try:
            body = resp.json()
        except Exception:
            body = resp.text

        return {
            "status": resp.ok,
            "status_code": resp.status_code,
            "body": body,
        }

    # ------------------------------------------------------------------
    # Simulate alert (for UI testing)
    # ------------------------------------------------------------------

    @classmethod
    def simulate_alert(cls) -> dict:
        import random

        event_types = [
            "alert.created",
            "alert.updated",
            "incident.created",
            "incident.mitigated",
            "incident.resolved",
        ]
        titles = [
            "API latency spike in production",
            "Database connection pool exhausted",
            "Certificate expiring in 24 hours",
            "Kubernetes pod crash loop",
            "Memory usage above 90% threshold",
        ]
        severities = ["critical", "high", "medium", "low"]
        statuses = ["started", "in_triage", "mitigated", "resolved"]

        event_type = random.choice(event_types)

        if "alert" in event_type:
            return {
                "type": event_type,
                "data": {
                    "id": str(random.randint(100000, 999999)),
                    "type": "alerts",
                    "attributes": {
                        "short_id": f"ALT-{random.randint(1000, 9999)}",
                        "summary": random.choice(titles),
                        "description": "Simulated Rootly alert for testing",
                        "status": "open" if "created" in event_type else "resolved",
                        "source": "monitoring",
                        "noise": "not_noise",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "external_url": "https://rootly.com/alerts/test",
                        "services": [{"name": "api-gateway"}],
                        "environments": [{"name": "production"}],
                        "labels": [
                            {"key": "severity", "value": random.choice(severities)},
                            {"key": "team", "value": "platform"},
                        ],
                    },
                },
            }
        else:
            return {
                "type": event_type,
                "data": {
                    "id": str(random.randint(100000, 999999)),
                    "type": "incidents",
                    "attributes": {
                        "title": random.choice(titles),
                        "summary": "Simulated Rootly incident for testing",
                        "status": random.choice(statuses),
                        "url": "https://rootly.com/incidents/test",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "severity": {
                            "data": {
                                "attributes": {
                                    "severity": random.choice(severities),
                                    "name": random.choice(severities),
                                }
                            }
                        },
                        "services": [
                            {"data": {"attributes": {"name": "api-gateway"}}}
                        ],
                        "environments": [
                            {"data": {"attributes": {"name": "production"}}}
                        ],
                        "labels": {},
                    },
                },
            }


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("ROOTLY_API_KEY", "")

    provider = RootlyProvider(
        context_manager,
        "test",
        ProviderConfig(
            authentication={"api_key": api_key}
        ),
    )

    print("Scopes:", provider.validate_scopes())
    alerts = provider.get_alerts()
    print(f"Found {len(alerts)} alerts/incidents:")
    for alert in alerts[:5]:
        print(f"  - [{alert.severity}] {alert.name} ({alert.status})")
