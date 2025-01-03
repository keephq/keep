import logging
import os
import threading
from collections import defaultdict
from typing import Dict, Optional, Set

from sqlmodel import select

from keep.api.core.db import (
    assign_alert_to_incident,
    existed_or_new_session,
    get_last_alerts,
)
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.core.tenant_configuration import TenantConfiguration
from keep.api.models.alert import AlertDto, AlertStatus, IncidentDto, IncidentStatus
from keep.api.models.db.alert import Incident
from keep.api.models.db.topology import TopologyServiceApplication
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
        self.started = False
        self.thread = None
        self._stop_event = threading.Event()
        self._topology_cache = {}
        self._cache_lock = threading.Lock()
        self.enabled = (
            os.environ.get("KEEP_TOPOLOGY_PROCESSOR", "false").lower() == "true"
        )
        # get enabled tenants
        self.tenant_configuration = TenantConfiguration()
        self.enabled_tenants = {
            tenant_id: self.tenant_configuration.get_configuration(
                tenant_id, "topology_processor"
            )
            for tenant_id in self.tenant_configuration.configurations
        }
        # for the single tenant, use the global configuration
        self.enabled_tenants[SINGLE_TENANT_UUID] = self.enabled
        # Configuration
        self.process_interval = 60  # seconds
        self.look_back_window = 15  # minutes

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
        tenants = self.enabled_tenants.keys()
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

        # 1. Get last alerts for the tenant
        topology_data = self._get_topology_data(tenant_id)
        applications = self._get_applications_data(tenant_id)
        services = [t.service for t in topology_data]
        if not topology_data:
            self.logger.info(f"No topology data found for tenant {tenant_id}")
            return

        # Currently topology-based incidents are created for applications only
        # SHAHAR: this is harder to implement service-related incidents without applications
        # TODO: add support for service-related incidents
        if not applications:
            self.logger.info(f"No applications found for tenant {tenant_id}")
            return

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
                self._create_application_based_incident(
                    tenant_id, application, services_to_alerts
                )

    def _get_topology_based_incidents(self, tenant_id: str) -> Dict[str, Incident]:
        """Get all topology-based incidents for a tenant"""
        with existed_or_new_session() as session:
            incidents = session.exec(
                select(Incident).where(
                    Incident.tenant_id == tenant_id
                    and Incident.incident_type == "topology"
                )
            ).all()
            return incidents

    def _check_topology_for_incidents(
        self,
        last_alerts: Dict[str, AlertDto],
        topology_based_incidents: Dict[str, Incident],
    ) -> Set[Incident]:
        """Check if the topology should create incidents"""
        incidents = []
        # get all alerts within the same application:

        # get all alerts within services that have dependencies:
        return incidents

    def _get_application_based_incident(
        self, tenant_id, application: TopologyServiceApplication
    ) -> Optional[Incident]:
        """Get the incident for an application"""
        with existed_or_new_session() as session:
            incident = session.exec(
                select(Incident).where(Incident.incident_application == application.id)
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
            for alert in alerts:
                # Let assign_alert_to_incident do the check if the alert is already assigned
                incident = assign_alert_to_incident(
                    fingerprint=alert.fingerprint,
                    incident=incident,
                    tenant_id=tenant_id,
                    session=session,
                )

            # Check if incident should be resolved
            all_resolved = all(
                [alert.status == AlertStatus.RESOLVED.value for alert in alerts]
            )
            # If all alerts are resolved, update incident status to resolved
            if all_resolved and incident.status != IncidentStatus.RESOLVED.value:
                incident.status = IncidentStatus.RESOLVED.value
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
                is_confirmed=True,  # Topology-based incidents are always confirmed
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
