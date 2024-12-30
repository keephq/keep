import logging
import os
import threading
from collections import defaultdict
from typing import Dict, Optional, Set

from sqlmodel import select

from keep.api.core.db import existed_or_new_session, get_last_alerts
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.core.tenant_configuration import TenantConfiguration
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import Incident
from keep.api.models.db.topology import TopologyServiceApplication
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
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
        self.logger.debug(f"Processing topology for tenant {tenant_id}")

        # 1. Get last alerts for the tenant
        topology_data = self._get_topology_data(tenant_id)
        applications = self._get_applications_data(tenant_id)
        services = [t.service for t in topology_data]
        if not topology_data:
            self.logger.debug(f"No topology data found for tenant {tenant_id}")
            return

        # Currently topology-based incidents are created for applications only
        # SHAHAR: this is harder to implement service-related incidents without applications
        # TODO: add support for service-related incidents
        if not applications:
            self.logger.debug(f"No applications found for tenant {tenant_id}")
            return

        db_last_alerts = get_last_alerts(tenant_id, with_incidents=True)
        last_alerts = convert_db_alerts_to_dto_alerts(db_last_alerts)

        services_with_alerts = defaultdict(list)
        # group by service
        for alert in last_alerts:
            if alert.service:
                if alert.service not in services:
                    # ignore alerts for services not in topology data
                    self.logger.debug(
                        f"Alert service {alert.service} not in topology data"
                    )
                    continue
                services_with_alerts[alert.service].append(alert)

        for application in applications:
            # check if there is an incident for the application
            incident = self._get_application_based_incident(tenant_id, application)
            print(incident)
            application_services = [t.service for t in application.services]
            # if more than one service in the application has alerts, create an incident
            services_with_alerts = [
                service
                for service in application_services
                if service in services_with_alerts
            ]
            if len(services_with_alerts) > 1:
                self._create_or_update_application_based_incident(
                    application, services_with_alerts, services_with_alerts[0]
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

    def _get_nested_dependencies(self, topology_data):
        """
        Get nested dependencies for each service including all sub-dependencies.
        Returns a dict mapping service name to list of all dependencies (direct and indirect).
        """
        # First, build a map of service_id to service and its dependencies
        service_deps = {}
        for service in topology_data:
            service_deps[service.service] = {
                "deps": list(service.dependencies),  # Use list instead of set
                "processed": False,
            }

        def get_all_deps(service_name: str, visited: set):
            """Recursively get all dependencies for a service"""
            if service_name in visited:
                # Avoid circular dependencies
                return []

            visited.add(service_name)

            if service_name not in service_deps:
                # Service not found in our data
                return []

            # Start with direct dependencies
            all_deps = service_deps[service_name]["deps"].copy()

            # For each direct dependency, get its dependencies
            for dep in service_deps[service_name]["deps"]:
                # Find the service object for this dependency
                for service in topology_data:
                    if service.service == dep.serviceName:
                        # Get nested dependencies recursively
                        nested_deps = get_all_deps(dep.serviceName, visited.copy())
                        # Add nested deps if they're not already in all_deps
                        for nested_dep in nested_deps:
                            if not any(
                                d.serviceId == nested_dep.serviceId for d in all_deps
                            ):
                                all_deps.append(nested_dep)
                        break

            return all_deps

        # Build complete dependency map
        nested_dependencies = {}
        for service in topology_data:
            nested_dependencies[service.service] = get_all_deps(service.service, set())

        return nested_dependencies
