import logging
import os
import threading
from collections import defaultdict
from typing import Dict, List, Optional
from uuid import UUID

from sqlmodel import select

from keep.api.core.config import config
from keep.api.core.db import (
    add_alerts_to_incident,
    assign_alert_to_incident,
    enrich_incidents_with_alerts,
    existed_or_new_session,
    get_last_alerts,
)
from keep.api.core.tenant_configuration import TenantConfiguration
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.alert import Incident
from keep.api.models.db.incident import IncidentStatus
from keep.api.models.db.topology import TopologyApplication, TopologyServiceApplication
from keep.api.models.incident import IncidentDto
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.rulesengine.rulesengine import RulesEngine
from keep.topologies.topologies_service import TopologiesService


class TopologyProcessor:

    @staticmethod
    def get_instance() -> "TopologyProcessor":
        if not hasattr(TopologyProcessor, "_instance"):
            TopologyProcessor._instance = TopologyProcessor()
        return TopologyProcessor._instance

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Starting topology processor")
        self.started = False
        self.thread = None
        self._stop_event = threading.Event()
        self._topology_cache = {}
        self._cache_lock = threading.Lock()
        self.enabled = (
            os.environ.get("KEEP_TOPOLOGY_PROCESSOR", "true").lower() == "true"
        )
        # get enabled tenants
        self.tenant_configuration = TenantConfiguration()

        # Global Configuration
        self.process_interval = config(
            "KEEP_TOPOLOGY_PROCESSOR_INTERVAL", cast=int, default=60
        )  # seconds
        self.look_back_window = config(
            "KEEP_TOPOLOGY_PROCESSOR_LOOK_BACK_WINDOW", cast=int, default=15
        )  # minutes
        self.default_depth = config(
            "KEEP_TOPOLOGY_PROCESSOR_DEPTH", cast=int, default=10
        )  # depth of service dependencies to check
        self.default_minimum_services = config(
            "KEEP_TOPOLOGY_PROCESSOR_MINIMUM_SERVICES", cast=int, default=2
        )  # minimum number of services with alerts for correlation
        self.logger.info(
            "Topology processor started",
            extra={
                "enabled": self.enabled,
                "process_interval": self.process_interval,
                "look_back_window": self.look_back_window,
                "default_depth": self.default_depth,
                "default_minimum_services": self.default_minimum_services,
            },
        )

    def _get_enabled_tenants(self) -> List[str]:
        """Get the list of enabled tenants for topology processing"""
        enabled_tenants = []
        for tenant_id in self.tenant_configuration.configurations:
            # get the tenant configuration
            tenant_config = self.tenant_configuration.get_configuration(
                tenant_id, "topology_processor"
            )
            if tenant_config:
                # check if the tenant is enabled
                if tenant_config.get("enabled", False):
                    enabled_tenants.append(tenant_id)
        return enabled_tenants

    async def start(self):
        """Runs the topology processor in server mode"""
        if not self.enabled:
            self.logger.info("Topology processor is disabled")
            return

        if self.started:
            self.logger.info("Topology processor already started")
            return

        self.logger.info("Starting topology processor")
        self._stop_event.clear()
        self.thread = threading.Thread(
            target=self._start_processing, name="topology-processing", daemon=True
        )
        self.thread.start()
        self.started = True
        self.logger.info("Started topology processor")

    def _start_processing(self):
        """Starts processing the topology"""
        self.logger.info("Starting topology processing")

        while not self._stop_event.is_set():
            try:
                self.logger.info("Processing topology for all tenants")
                self._process_all_tenants()
                self.logger.info(
                    "Finished processing topology for all tenants will wait for next interval [{}]".format(
                        self.process_interval
                    )
                )
            except Exception as e:
                self.logger.exception("Error in topology processing: %s", str(e))

            # Wait for the next interval or until stopped
            self._stop_event.wait(self.process_interval)

        self.logger.info("Topology processing stopped")

    def stop(self):
        """Stops the topology processor"""
        if not self.started:
            return

        self.logger.info("Stopping topology processor")
        self._stop_event.set()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=30)  # Wait up to 30 seconds
            if self.thread.is_alive():
                self.logger.warning("Topology processor thread did not stop gracefully")

        self.started = False
        self.thread = None
        self.logger.info("Stopped topology processor")

    def _process_all_tenants(self):
        """Process topology for all tenants"""
        tenants = self._get_enabled_tenants()
        for tenant_id in tenants:
            try:
                self.logger.info(f"Processing topology for tenant {tenant_id}")
                self._process_tenant(tenant_id)
                self.logger.info(f"Finished processing topology for tenant {tenant_id}")
            except Exception as e:
                self.logger.exception(f"Error processing tenant {tenant_id}: {str(e)}")

    def _process_tenant(self, tenant_id: str):
        """Process topology for a single tenant"""
        self.logger.info(f"Processing topology for tenant {tenant_id}")

        # Get tenant-specific configuration
        tenant_config = self.tenant_configuration.get_configuration(
            tenant_id, "topology_processor"
        )

        # Skip if tenant is not enabled for topology processing
        if not tenant_config or not tenant_config.get("enabled", False):
            self.logger.info(f"Topology processing is disabled for tenant {tenant_id}")
            return

        # Get correlation depth from tenant config or use default
        correlation_depth = tenant_config.get("depth", self.default_depth)
        minimum_services = tenant_config.get(
            "minimum_services", self.default_minimum_services
        )
        self.logger.info(
            f"Using correlation settings for tenant {tenant_id}: depth={correlation_depth}, minimum_services={minimum_services}"
        )

        # 1. Get last alerts for the tenant
        topology_data = self._get_topology_data(tenant_id)
        applications = self._get_applications_data(tenant_id)
        services = [t.service for t in topology_data]
        if not topology_data:
            self.logger.info(f"No topology data found for tenant {tenant_id}")
            return

        # Get alerts and group by service
        db_last_alerts = get_last_alerts(tenant_id, with_incidents=True)
        last_alerts = convert_db_alerts_to_dto_alerts(db_last_alerts)

        services_to_alerts = defaultdict(list)
        # group by service
        for alert in last_alerts:
            if alert.service:
                if alert.service not in services:
                    # ignore alerts for services not in topology data
                    self.logger.debug(
                        f"Alert service {alert.service} not in topology data"
                    )
                    continue
                services_to_alerts[alert.service].append(alert)

        # First process application-based correlation
        self._process_application_correlation(
            tenant_id, applications, services_to_alerts, minimum_services
        )

    def _process_application_correlation(
        self,
        tenant_id: str,
        applications: List[TopologyServiceApplication],
        services_to_alerts: Dict[str, List[AlertDto]],
        minimum_services: int,
    ):
        """Process application-based correlation"""
        self.logger.info(
            f"Processing application-based correlation for tenant {tenant_id}"
        )

        if not applications:
            self.logger.info(f"No applications found for tenant {tenant_id}")
            return

        for application in applications:
            # check if there is an incident for the application
            incident = self._get_application_based_incident(tenant_id, application)
            application_services = [t.service for t in application.services]
            services_with_alerts = [
                service
                for service in application_services
                if service in services_to_alerts
            ]
            # if none of the services in the application have alerts, we don't need to create an incident
            if not services_with_alerts:
                self.logger.info(
                    f"No alerts found for application {application.name}, skipping"
                )
                continue

            # if we are here - we have alerts for the application, we need to create/update an incident
            self.logger.info(
                f"Found alerts for application {application.name}, creating/updating incident"
            )
            # if an incident exists, we will update it
            # NOTE: we support only one incident per application for now
            if incident:
                self.logger.info(
                    f"Found existing incident for application {application.name}"
                )
                # update the incident with new alerts / status / severity
                self._update_application_based_incident(
                    tenant_id, application, incident, services_to_alerts
                )
            else:
                self.logger.info(
                    f"No existing incident found for application {application.name}"
                )
                # create a new incident with the alerts
                if len(services_with_alerts) >= minimum_services:
                    self.logger.info(
                        f"Creating new incident for application {application.name}"
                    )
                    # create a new incident
                    self._create_application_based_incident(
                        tenant_id, application, services_to_alerts
                    )
                else:
                    self.logger.info(
                        f"Not enough services with alerts for application {application.name}, skipping"
                    )
                    continue
        self.logger.info(
            f"Finished processing application-based correlation for tenant {tenant_id}"
        )

    def _create_service_group_incident(
        self,
        tenant_id: str,
        service_group: List[str],
        services_to_alerts: Dict[str, List[AlertDto]],
        application_id: UUID = None,
    ) -> None:
        """Create a new incident for a correlated service group"""
        sorted_services = sorted(service_group)

        with existed_or_new_session() as session:
            # Create a new incident
            incident = Incident(
                tenant_id=tenant_id,
                user_generated_name="Service correlation incident",
                user_summary=f"Multiple related services are experiencing issues: {', '.join(sorted_services)}",
                incident_type="topology",
                is_candidate=False,
                is_visible=True,
                affected_services=sorted_services,  # Set affected_services
                incident_application=application_id,
            )

            # Collect all alerts for services in this group
            all_alerts = []
            for service in service_group:
                if service in services_to_alerts:
                    all_alerts.extend(services_to_alerts[service])

            # Assign alerts to the incident
            for alert in all_alerts:
                incident = assign_alert_to_incident(
                    fingerprint=alert.fingerprint,
                    incident=incident,
                    tenant_id=tenant_id,
                    session=session,
                )

            # Send notification about new incident
            incident_dto = IncidentDto.from_db_incident(incident)
            RulesEngine.send_workflow_event(tenant_id, session, incident_dto, "created")

            self.logger.info(
                f"Created new incident for service group with application_id: {application_id}"
            )

    def _update_service_group_incident(
        self,
        tenant_id: str,
        service_group: List[str],
        incident: Incident,
        services_to_alerts: Dict[str, List[AlertDto]],
    ) -> None:
        """Update an existing service group incident with new alerts"""
        sorted_services = sorted(service_group)

        with existed_or_new_session() as session:
            # Update affected_services if needed
            if set(incident.affected_services) != set(sorted_services):
                self.logger.info(
                    f"Updating affected_services from {incident.affected_services} to {sorted_services}"
                )
                incident.affected_services = sorted_services
                session.add(incident)
                session.commit()

            # Collect all alerts for services in this group
            all_alerts = []
            for service in service_group:
                if service in services_to_alerts:
                    all_alerts.extend(services_to_alerts[service])

            # Add alerts to the incident
            add_alerts_to_incident(
                tenant_id=tenant_id,
                incident=incident,
                fingerprints=[alert.fingerprint for alert in all_alerts],
                session=session,
                exclude_unlinked_alerts=True,
            )

            # Check if incident should be resolved
            if incident.resolve_on == "all_resolved":
                self.logger.info(
                    "Checking if service group incident should be resolved"
                )
                incident = enrich_incidents_with_alerts(tenant_id, [incident], session)[
                    0
                ]
                alert_dtos = convert_db_alerts_to_dto_alerts(incident.alerts)
                statuses = []
                for alert in alert_dtos:
                    if isinstance(alert.status, str):
                        statuses.append(alert.status)
                    else:
                        statuses.append(alert.status.value)
                all_resolved = all(
                    [
                        s == AlertStatus.RESOLVED.value
                        or s == AlertStatus.SUPPRESSED.value
                        for s in statuses
                    ]
                )

                # Update incident status based on alert statuses
                if all_resolved and incident.status != IncidentStatus.RESOLVED.value:
                    self.logger.info(
                        "All alerts resolved, updating incident status to resolved"
                    )
                    incident.status = IncidentStatus.RESOLVED.value
                    session.add(incident)
                    session.commit()
                elif (
                    incident.status == IncidentStatus.RESOLVED.value
                    and not all_resolved
                ):
                    self.logger.info(
                        "Not all alerts resolved, updating incident status to firing"
                    )
                    incident.status = IncidentStatus.FIRING.value
                    session.add(incident)
                    session.commit()

            # Send notification about incident update
            incident_dto = IncidentDto.from_db_incident(incident)
            RulesEngine.send_workflow_event(tenant_id, session, incident_dto, "updated")

            self.logger.info(
                f"Updated incident with application_id: {incident.incident_application}"
            )

    def _get_topology_based_incidents(self, tenant_id: str) -> Dict[str, Incident]:
        """Get all topology-based incidents for a tenant"""
        with existed_or_new_session() as session:
            incidents = session.exec(
                select(Incident).where(
                    Incident.tenant_id == tenant_id,
                    Incident.incident_type == "topology",
                )
            ).all()
            return incidents

    def _get_application_based_incident(
        self, tenant_id, application: TopologyApplication
    ) -> Optional[Incident]:
        """Get the incident for an application"""
        with existed_or_new_session() as session:
            incident = session.exec(
                select(Incident)
                .where(Incident.tenant_id == tenant_id)
                .where(Incident.incident_type == "topology")
                .where(Incident.incident_application == application.id)
                .where(
                    Incident.status.in_(
                        [IncidentStatus.FIRING.value, IncidentStatus.ACKNOWLEDGED.value]
                    )
                )  # Not resolved or merged/deleted
            ).first()
            return incident

    def _get_topology_data(self, tenant_id: str):
        """Get topology data for a tenant"""
        with existed_or_new_session() as session:
            topology_data = TopologiesService.get_all_topology_data(
                tenant_id=tenant_id, session=session
            )
            return topology_data

    def _get_applications_data(self, tenant_id: str):
        """Get applications data for a tenant"""
        with existed_or_new_session() as session:
            applications = TopologiesService.get_applications_by_tenant_id(
                tenant_id=tenant_id, session=session
            )
            return applications

    def _update_application_based_incident(
        self,
        tenant_id: str,
        application: TopologyServiceApplication,
        incident: Incident,
        services_with_alerts: Dict[str, list[AlertDto]],
    ) -> None:
        """
        Update an existing application-based incident with new alerts and status

        Args:
            application: The application associated with the incident
            incident: The existing incident to update
            services_with_alerts: List of services that have active alerts
        """
        self.logger.info(f"Updating incident for application {application.name}")

        with existed_or_new_session() as session:
            # Get all alerts for the services
            alerts = []

            for service in services_with_alerts:
                service_alerts = services_with_alerts[service]
                alerts.extend(service_alerts)

            # Assign all alerts to the incident if they're not already assigned
            add_alerts_to_incident(
                tenant_id=tenant_id,
                incident=incident,
                fingerprints=[alert.fingerprint for alert in alerts],
                session=session,
                exclude_unlinked_alerts=True,
            )

            # Check if incident should be resolved
            if incident.resolve_on == "all_resolved":
                self.logger.info("Checking if incident should be resolved")
                incident = enrich_incidents_with_alerts(tenant_id, [incident], session)[
                    0
                ]
                alert_dtos = convert_db_alerts_to_dto_alerts(incident.alerts)
                statuses = []
                for alert in alert_dtos:
                    if isinstance(alert.status, str):
                        statuses.append(alert.status)
                    else:
                        statuses.append(alert.status.value)
                all_resolved = all(
                    [
                        s == AlertStatus.RESOLVED.value
                        or s == AlertStatus.SUPPRESSED.value
                        for s in statuses
                    ]
                )
                # If all alerts are resolved, update incident status to resolved
                if all_resolved and incident.status != IncidentStatus.RESOLVED.value:
                    self.logger.info(
                        "All alerts are resolved, updating incident status to resolved"
                    )
                    incident.status = IncidentStatus.RESOLVED.value
                    session.add(incident)
                    session.commit()
                # elif the alert is resolved and the incident is not resolved, update the incident status to updated
                elif (
                    incident.status == IncidentStatus.RESOLVED.value
                    and not all_resolved
                ):
                    self.logger.info(
                        "Alerts are not resolved, updating incident status to updated"
                    )
                    incident.status = IncidentStatus.FIRING.value
                    session.add(incident)
                    session.commit()

            # Send notification about incident update
            incident_dto = IncidentDto.from_db_incident(incident)
            RulesEngine.send_workflow_event(tenant_id, session, incident_dto, "updated")
            self.logger.info(f"Updated incident for application {application.name}")

    def _create_application_based_incident(
        self,
        tenant_id,
        application: TopologyServiceApplication,
        services_with_alerts: Dict[str, list[AlertDto]],
    ) -> None:
        """
        Create a new application-based incident

        Args:
            application: The application to create an incident for
            services_with_alerts: List of services that have active alerts
        """
        self.logger.info(f"Creating new incident for application {application.name}")

        with existed_or_new_session() as session:
            # Create new incident
            incident = Incident(
                tenant_id=tenant_id,
                user_generated_name=f"Application incident: {application.name}",
                user_summary=f"Multiple services in application {application.name} are experiencing issues",
                incident_type="topology",
                incident_application=application.id,
                is_candidate=False,  # Topology-based incidents are always confirmed
                is_visible=True,  # Topology-based incidents are always confirmed
            )

            # Get all alerts for the services and find max severity
            for service in services_with_alerts:
                service_alerts = services_with_alerts[service]

                # Assign alerts to incident
                for alert in service_alerts:
                    incident = assign_alert_to_incident(
                        fingerprint=alert.fingerprint,
                        incident=incident,
                        tenant_id=tenant_id,
                        session=session,
                    )

            # Send notification about new incident
            incident_dto = IncidentDto.from_db_incident(incident)
            # Trigger the workflow event
            RulesEngine.send_workflow_event(tenant_id, session, incident_dto, "created")
            self.logger.info(f"Created new incident for application {application.name}")
