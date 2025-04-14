import { TopologyNode } from "@/app/(keep)/topology/model";
import { Edge, Position } from "@xyflow/react";
import dagre, { graphlib } from "@dagrejs/dagre";
import { nodeHeight, nodeWidth } from "@/app/(keep)/topology/ui/map/styles";

// A flag to track if we've shown the warning message
let hasShownLimitWarning = false;

// Updated function with node limit
export function getLayoutedElements(
  nodes: TopologyNode[],
  edges: Edge[],
  bypassLimit = false
) {
  const MAX_NODES = 100;
  const totalNodes = nodes.length;
  let limitedNodes = nodes;
  let limitedEdges = edges;
  let limitApplied = false;

  // Check if we need to limit the nodes (unless bypassing limit is requested)
  if (!bypassLimit && totalNodes > MAX_NODES) {
    limitedNodes = nodes.slice(0, MAX_NODES);
    limitApplied = true;

    // Show warning message only once
    if (!hasShownLimitWarning) {
      console.warn(
        `Topology display limited to ${MAX_NODES} nodes (total: ${totalNodes})`
      );
      hasShownLimitWarning = true;
    }

    // Only keep edges that connect the limited nodes
    const limitedNodeIds = new Set(limitedNodes.map((node) => node.id));
    limitedEdges = edges.filter(
      (edge) =>
        limitedNodeIds.has(edge.source) && limitedNodeIds.has(edge.target)
    );
  }

  const dagreGraph = new graphlib.Graph({});
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({
    rankdir: "LR",
    nodesep: 50,
    ranksep: 200,
  });

  // Add only the limited nodes to the dagre graph
  limitedNodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  // Add the limited edges to the dagre graph
  limitedEdges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  // Apply the layout to the nodes
  limitedNodes.forEach((node) => {
    const gNode = dagreGraph.node(node.id);
    node.position = {
      x: gNode.x - gNode.width / 2,
      y: gNode.y - gNode.height / 2,
    };
    node.style = {
      ...node.style,
      width: gNode.width as number,
      height: gNode.height as number,
    };
    node.targetPosition = Position.Left;
    node.sourcePosition = Position.Right;
  });

  // Return only the limited nodes and edges
  return {
    nodes: limitedNodes,
    edges: limitedEdges,
    metadata: limitApplied
      ? {
          limitApplied: true,
          totalNodes,
          displayedNodes: MAX_NODES,
        }
      : undefined,
  };
}
