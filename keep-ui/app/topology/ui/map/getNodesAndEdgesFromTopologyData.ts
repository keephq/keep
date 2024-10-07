import {
  ServiceNodeType,
  TopologyApplication,
  TopologyNode,
  TopologyService,
} from "@/app/topology/model";
import { Edge } from "@xyflow/react";
import {
  edgeLabelBgBorderRadiusNoHover,
  edgeLabelBgPaddingNoHover,
  edgeLabelBgStyleNoHover,
  edgeMarkerEndNoHover,
} from "@/app/topology/ui/map/styles";

export function getNodesAndEdgesFromTopologyData(
  topologyData: TopologyService[],
  applicationsMap: Map<string, TopologyApplication>
) {
  const nodeMap = new Map<string, TopologyNode>();
  const edgeMap = new Map<string, Edge>();
  // Create nodes from service definitions
  for (const service of topologyData) {
    const node: ServiceNodeType = {
      id: service.service.toString(),
      type: "service",
      data: service,
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
