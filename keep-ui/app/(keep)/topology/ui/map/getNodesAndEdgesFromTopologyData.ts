import {
  ServiceNodeType,
  TopologyApplication,
  TopologyNode,
  TopologyService,
} from "@/app/(keep)/topology/model";
import { Edge } from "@xyflow/react";
import {
  edgeLabelBgBorderRadiusNoHover,
  edgeLabelBgPaddingNoHover,
  edgeLabelBgStyleNoHover,
  edgeMarkerEndNoHover,
} from "@/app/(keep)/topology/ui/map/styles";
import { IncidentDto } from "@/entities/incidents/model";
import { KeyedMutator } from "swr";
import { AlertDto, Severity, Status } from "@/entities/alerts/model";
import { computeCascadeWarnings } from "@/app/(keep)/topology/ui/map/cascade";

const SEVERITY_WEIGHT: Record<Severity, number> = {
  [Severity.Critical]: 5,
  [Severity.Error]: 4,
  [Severity.High]: 4,
  [Severity.Warning]: 3,
  [Severity.Info]: 2,
  [Severity.Low]: 1,
};

/**
 * Highest severity among the firing alerts of a service, so the topology
 * node can reflect its current state. Resolved/suppressed alerts are ignored.
 */
export function getHighestFiringSeverity(
  alerts: AlertDto[]
): Severity | undefined {
  let highest: Severity | undefined;
  for (const alert of alerts) {
    if (alert.status !== Status.Firing) {
      continue;
    }
    const severity = alert.severity as Severity;
    if (
      highest === undefined ||
      SEVERITY_WEIGHT[severity] > SEVERITY_WEIGHT[highest]
    ) {
      highest = severity;
    }
  }
  return highest;
}

export function getNodesAndEdgesFromTopologyData(
  topologyData: TopologyService[],
  applicationsMap: Map<string, TopologyApplication>,
  allIncidents: IncidentDto[],
  allAlerts: AlertDto[],
  topologyMutator: KeyedMutator<TopologyService[]>
) {
  const nodeMap = new Map<string, TopologyNode>();
  const edgeMap = new Map<string, Edge>();

  const alertsByService = new Map<string, AlertDto[]>();
  for (const alert of allAlerts) {
    if (!alert.service) {
      continue;
    }
    const alerts = alertsByService.get(alert.service) ?? [];
    alerts.push(alert);
    alertsByService.set(alert.service, alerts);
  }
  const cascadeWarnings = computeCascadeWarnings(topologyData, alertsByService);

  // Create nodes from service definitions
  for (const service of topologyData) {
    const numIncidentsToService = allIncidents.filter(
      (incident) =>
        incident.services.includes(service.display_name) ||
        incident.services.includes(service.service)
    );
    const serviceAlerts = alertsByService.get(service.service) ?? [];
    const node: ServiceNodeType = {
      id: service.id.toString(),
      type: "service",
      data: {
        ...service,
        incidents: numIncidentsToService.length,
        // the badge counts firing alerts only, consistent with the border
        // color and cascade warnings; resolved alerts don't badge a node
        alerts: serviceAlerts.filter((alert) => alert.status === Status.Firing)
          .length,
        highestAlertSeverity: getHighestFiringSeverity(serviceAlerts),
        cascadeCount: cascadeWarnings.get(service.service) ?? 0,
        topologyMutator,
      },
      position: { x: 0, y: 0 }, // Dagre will handle the actual positioning
      selectable: true,
    };
    if (service.application_ids.length > 0) {
      node.data.applications = service.application_ids
        .map((id) => {
          const app = applicationsMap.get(id);
          if (!app) {
            return null;
          }
          return {
            id: app.id,
            name: app.name,
          };
        })
        .filter((a) => !!a);
    }
    nodeMap.set(service.id.toString(), node);
    service.dependencies.forEach((dependency) => {
      const dependencyService = topologyData.find(
        (s) => s.id === dependency.serviceId
      );
      const edgeId = dependency.id.toString();
      if (!edgeMap.has(edgeId)) {
        edgeMap.set(edgeId, {
          id: edgeId.toString(),
          source: service.id.toString(),
          target: dependencyService?.id.toString() ?? "",
          label: dependency.protocol === "unknown" ? "" : dependency.protocol,
          animated: false,
          labelBgPadding: edgeLabelBgPaddingNoHover,
          labelBgStyle: edgeLabelBgStyleNoHover,
          labelBgBorderRadius: edgeLabelBgBorderRadiusNoHover,
          markerEnd: edgeMarkerEndNoHover,
        });
      }
    });
  }

  return { nodeMap, edgeMap };
}
