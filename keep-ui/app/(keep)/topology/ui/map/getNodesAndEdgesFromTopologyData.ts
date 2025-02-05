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

export function getNodesAndEdgesFromTopologyData(
  topologyData: TopologyService[],
  applicationsMap: Map<string, TopologyApplication>,
  allIncidents: IncidentDto[],
  topologyMutator: KeyedMutator<TopologyService[]>
) {
  const nodeMap = new Map<string, TopologyNode>();
  const edgeMap = new Map<string, Edge>();

  // Create nodes from service definitions
  for (const service of topologyData) {
    const numIncidentsToService = allIncidents.filter(
      (incident) =>
        incident.services.includes(service.display_name) ||
        incident.services.includes(service.service)
    );
    const node: ServiceNodeType = {
      id: service.id.toString(),
      type: "service",
      data: {
        ...service,
        incidents: numIncidentsToService.length,
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
