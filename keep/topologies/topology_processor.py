import logging
import os
import threading
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set

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
from keep.api.models.db.topology import (
    TopologyServiceApplication,
    TopologyServiceDtoOut,
)
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
            os.environ.get("KEEP_TOPOLOGY_PROCESSOR", "false").lower() == "true"
        )
        # get enabled tenants
        self.tenant_configuration = TenantConfiguration()

        # Global Configuration
        self.process_interval = config(
            "KEEP_TOPOLOGY_PROCESSOR_INTERVAL", cast=int, default=10
        )  # seconds
        self.look_back_window = config(
            "KEEP_TOPOLOGY_PROCESSOR_LOOK_BACK_WINDOW", cast=int, default=15
        )  # minutes
        self.default_depth = config(
            "KEEP_TOPOLOGY_PROCESSOR_DEPTH", cast=int, default=5
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
            tenant_id, applications, services_to_alerts
        )

        # Then process service-based correlation with depth
        self._process_service_depth_correlation(
            tenant_id,
            topology_data,
            services_to_alerts,
            correlation_depth,
            minimum_services,
        )

    def _process_application_correlation(
        self,
        tenant_id: str,
        applications: List[TopologyServiceApplication],
        services_to_alerts: Dict[str, List[AlertDto]],
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
                self._create_application_based_incident(
                    tenant_id, application, services_to_alerts
                )

    def _process_service_depth_correlation(
        self,
        tenant_id: str,
        topology_data: List[TopologyServiceDtoOut],
        services_to_alerts: Dict[str, List[AlertDto]],
        correlation_depth: int,
        minimum_services: int,
    ):
        """
        Process service-based correlation based on depth.
        This correlates alerts across services that are connected within the specified depth.
        """
        self.logger.info(f"Processing service depth correlation for tenant {tenant_id}")

        # Skip if no alerts or topology data
        services_with_alerts = list(services_to_alerts.keys())
        if not services_with_alerts or not topology_data:
            self.logger.info(
                "No services with alerts or no topology data, skipping service depth correlation"
            )
            return

        # Build dependency graph
        dependency_graph = self._build_dependency_graph(topology_data)

        # Find connected components within the specified depth and assign interconnectivity_ids
        correlated_groups = self._find_correlated_service_groups(
            dependency_graph, services_with_alerts, correlation_depth, minimum_services
        )

        self.logger.info(f"Found {len(correlated_groups)} correlated service groups")

        # Process each correlated group
        for group_idx, service_group in enumerate(correlated_groups):
            group_services = list(service_group)

            # Generate a stable interconnectivity_id for this service group
            # Sort services to ensure consistent ID regardless of service discovery order
            sorted_services = sorted(group_services)
            interconnectivity_id = self._generate_interconnectivity_id(sorted_services)

            self.logger.info(
                f"Processing correlated service group {group_idx+1}: {group_services}, "
                f"interconnectivity_id: {interconnectivity_id}"
            )

            # Get existing incident for this interconnectivity_id
            incident = self._get_interconnectivity_incident(
                tenant_id, interconnectivity_id
            )

            if incident:
                self.logger.info(
                    f"Found existing incident for interconnectivity_id {interconnectivity_id}"
                )
                self._update_service_group_incident(
                    tenant_id,
                    group_services,
                    incident,
                    services_to_alerts,
                    interconnectivity_id,
                )
            else:
                self.logger.info(
                    f"Creating new incident for interconnectivity_id {interconnectivity_id}"
                )
                self._create_service_group_incident(
                    tenant_id, group_services, services_to_alerts, interconnectivity_id
                )

    def _generate_interconnectivity_id(self, service_group: List[str]) -> str:
        """
        Generate a stable identifier for a group of interconnected services.
        This ensures that the same services will always get the same ID.

        Args:
            service_group: A list of service names

        Returns:
            A string identifier for the service group
        """
        # Sort to ensure consistent ordering
        sorted_services = sorted(service_group)
        # Join with a delimiter that won't appear in service names
        service_string = "|".join(sorted_services)
        # Use a hash function for a shorter representation
        # We use a simple hash here since we don't need cryptographic security
        import hashlib

        return f"interconnect-{hashlib.md5(service_string.encode()).hexdigest()[:8]}"

    def _get_interconnectivity_incident(
        self, tenant_id: str, interconnectivity_id: str
    ) -> Optional[Incident]:
        """
        Get an incident by its interconnectivity_id

        Args:
            tenant_id: The tenant ID
            interconnectivity_id: The interconnectivity ID to look for

        Returns:
            The incident if found, None otherwise
        """
        with existed_or_new_session() as session:
            # Look for an incident with this interconnectivity_id
            incident = session.exec(
                select(Incident)
                .where(Incident.tenant_id == tenant_id)
                .where(Incident.incident_type == "topology")
                .where(Incident.incident_application.is_(None))  # Not application-based
                .where(Incident.interconnectivity_id == interconnectivity_id)
                .where(Incident.status != IncidentStatus.RESOLVED.value)  # Not resolved
            ).first()

            if incident:
                self.logger.debug(
                    f"Found incident with interconnectivity_id: {interconnectivity_id}"
                )
            else:
                self.logger.debug(
                    f"No incident found with interconnectivity_id: {interconnectivity_id}"
                )

            return incident

    def _create_service_group_incident(
        self,
        tenant_id: str,
        service_group: List[str],
        services_to_alerts: Dict[str, List[AlertDto]],
        interconnectivity_id: str = None,
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
                interconnectivity_id=interconnectivity_id,  # Set the interconnectivity_id
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
                f"Created new incident for service group with interconnectivity_id: {interconnectivity_id}"
            )

    def _update_service_group_incident(
        self,
        tenant_id: str,
        service_group: List[str],
        incident: Incident,
        services_to_alerts: Dict[str, List[AlertDto]],
        interconnectivity_id: str = None,
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

            # Ensure interconnectivity_id is set (for backwards compatibility)
            if (
                not hasattr(incident, "interconnectivity_id")
                or not incident.interconnectivity_id
            ):
                if interconnectivity_id:
                    self.logger.info(
                        f"Setting interconnectivity_id to {interconnectivity_id}"
                    )
                    incident.interconnectivity_id = interconnectivity_id
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
                f"Updated incident with interconnectivity_id: {incident.interconnectivity_id}"
            )

    def _build_dependency_graph(
        self, topology_data: List[TopologyServiceDtoOut]
    ) -> Dict[str, Set[str]]:
        """
        Build a graph representation of service dependencies.
        Returns a dict where keys are service names and values are sets of dependent services.
        """
        graph = defaultdict(set)

        # Map service IDs to service names for lookup
        service_id_to_name = {}
        self.logger.debug(
            f"Building dependency graph from {len(topology_data)} services"
        )

        for service in topology_data:
            service_id_to_name[str(service.id)] = service.service
            # Initialize entry for this service (even if it has no dependencies)
            if service.service not in graph:
                graph[service.service] = set()

            # Log dependency count for debugging
            if hasattr(service, "dependencies") and service.dependencies:
                self.logger.debug(
                    f"Service {service.service} (ID: {service.id}) has {len(service.dependencies)} dependencies"
                )

        # Add dependencies to the graph
        for service in topology_data:
            source_service_name = service.service

            # Skip if service has no dependencies attribute or it's None
            if not hasattr(service, "dependencies") or service.dependencies is None:
                self.logger.debug(
                    f"Service {service.service} has no dependencies attribute or it's None"
                )
                continue

            # Process each dependency
            for dependency in service.dependencies:
                # Skip null dependencies
                if dependency is None:
                    self.logger.warning(
                        f"Null dependency found for service {service.service}"
                    )
                    continue

                # Skip if dependency doesn't have required attributes
                if not hasattr(dependency, "serviceId") or not hasattr(
                    dependency, "serviceName"
                ):
                    self.logger.warning(
                        f"Dependency for service {service.service} missing required attributes"
                    )
                    continue

                # The source service is the current service
                # The destination service is identified by the dependency.serviceId
                dest_service_id = str(dependency.serviceId)

                # Log the dependency details for debugging
                self.logger.debug(
                    f"Processing dependency: {source_service_name} -> ID:{dest_service_id} (Name: {dependency.serviceName})"
                )

                # Look up the destination service name
                if dest_service_id in service_id_to_name:
                    dest_service_name = service_id_to_name[dest_service_id]

                    # Add bidirectional edges
                    graph[source_service_name].add(dest_service_name)
                    graph[dest_service_name].add(source_service_name)

                    self.logger.debug(
                        f"Added bidirectional edge: {source_service_name} <-> {dest_service_name}"
                    )
                else:
                    # Log warning if destination service ID is not found in the mapping
                    self.logger.warning(
                        f"Dependency destination service with ID {dest_service_id} not found in topology data. "
                        f"Using serviceName '{dependency.serviceName}' as fallback."
                    )

                    # Use serviceName as fallback
                    graph[source_service_name].add(dependency.serviceName)
                    graph[dependency.serviceName].add(source_service_name)

                    self.logger.debug(
                        f"Added fallback bidirectional edge: {source_service_name} <-> {dependency.serviceName}"
                    )

        # Log the final graph stats
        node_count = len(graph)
        edge_count = (
            sum(len(edges) for edges in graph.values()) // 2
        )  # Divide by 2 since edges are bidirectional
        self.logger.info(
            f"Dependency graph built with {node_count} nodes and {edge_count} edges"
        )

        return graph

    def _find_correlated_service_groups(
        self,
        dependency_graph: Dict[str, Set[str]],
        services_with_alerts: List[str],
        max_depth: int,
        minimum_services: int,
    ) -> List[Set[str]]:
        """
        Find groups of services that are connected within max_depth and have alerts.
        Returns a list of sets, where each set contains service names that should be correlated.
        """
        correlated_groups = []
        visited = set()

        for service in services_with_alerts:
            if service in visited:
                continue

            # Find all services connected to this one within max_depth
            connected_services = self._find_connected_services(
                dependency_graph, service, max_depth, services_with_alerts
            )

            # Only create a group if there are at least minimum_services connected
            if len(connected_services) >= minimum_services:
                correlated_groups.append(connected_services)
                visited.update(connected_services)

        return correlated_groups

    def _find_connected_services(
        self,
        graph: Dict[str, Set[str]],
        start_service: str,
        max_depth: int,
        services_with_alerts: List[str],
    ) -> Set[str]:
        """
        BFS to find all services connected to start_service within max_depth that have alerts.
        """
        connected = {start_service}
        queue = deque([(start_service, 0)])  # (service, depth)
        visited = {start_service}

        while queue:
            current, depth = queue.popleft()

            # If we reached max depth, don't explore further
            if depth >= max_depth:
                continue

            for neighbor in graph.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)

                    # Only include services with alerts in the connected set
                    if neighbor in services_with_alerts:
                        connected.add(neighbor)

                    # Enqueue neighbor for further exploration
                    queue.append((neighbor, depth + 1))

        return connected

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
