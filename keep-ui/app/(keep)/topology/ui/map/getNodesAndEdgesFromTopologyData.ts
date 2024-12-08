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

export function getNodesAndEdgesFromTopologyData(
  topologyData: TopologyService[],
  applicationsMap: Map<string, TopologyApplication>,
  allIncidents: IncidentDto[]
) {
  const nodeMap = new Map<string, TopologyNode>();
  const edgeMap = new Map<string, Edge>();
  const allServices = topologyData.map((data) => data.display_name);
  // Create nodes from service definitions
  for (const service of topologyData) {
    const numIncidentsToService = allIncidents.filter((incident) =>
      incident.services.includes(service.display_name)
    );
    const node: ServiceNodeType = {
      id: service.service.toString(),
      type: "service",
      data: { ...service, incidents: numIncidentsToService.length },
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
    nodeMap.set(service.service.toString(), node);
    service.dependencies.forEach((dependency) => {
      const dependencyService = topologyData.find(
        (s) => s.service === dependency.serviceName
      );
      const edgeId = `${service.service}_${dependency.protocol}_${
        dependencyService
          ? dependencyService.service
          : dependency.serviceId.toString()
      }`;
      if (!edgeMap.has(edgeId)) {
        edgeMap.set(edgeId, {
          id: edgeId,
          source: service.service.toString(),
          target: dependency.serviceName.toString(),
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
