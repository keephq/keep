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
  bypassLimit = false,
  applicationMode = false
) {
  const MAX_NODES = 100;
  const MAX_APPLICATION_NODES = 300; // Higher limit for application view
  const totalNodes = nodes.length;
  let limitedNodes = nodes;
  let limitedEdges = edges;
  let limitApplied = false;
  let maxNodesToShow = applicationMode ? MAX_APPLICATION_NODES : MAX_NODES;

  // Check if we need to limit the nodes
  if (
    (!bypassLimit || (applicationMode && totalNodes > MAX_APPLICATION_NODES)) &&
    totalNodes > maxNodesToShow
  ) {
    limitedNodes = nodes.slice(0, maxNodesToShow);
    limitApplied = true;

    // Show warning message only once (if not in application mode)
    if (!applicationMode && !hasShownLimitWarning) {
      console.warn(
        `Topology display limited to ${maxNodesToShow} nodes (total: ${totalNodes})`
      );
      hasShownLimitWarning = true;
    } else if (applicationMode) {
      console.warn(
        `Application view limited to ${MAX_APPLICATION_NODES} nodes (total: ${totalNodes})`
      );
    }

    // Only keep edges that connect the limited nodes
    const limitedNodeIds = new Set(limitedNodes.map((node) => node.id));
    limitedEdges = edges.filter(
      (edge) =>
        limitedNodeIds.has(edge.source) && limitedNodeIds.has(edge.target)
    );
  } else if (bypassLimit && !applicationMode && totalNodes > MAX_NODES) {
    // Log when we're bypassing the limit for debugging
    console.info(
      `Bypassing node limit for ${totalNodes} nodes (e.g., for selected application view)`
    );
  }

  const dagreGraph = new graphlib.Graph({});
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Adjust node spacing based on the number of nodes
  // Use tighter spacing for larger graphs to fit more nodes in the view
  let nodeSep = 50;
  let rankSep = 200;

  if (limitedNodes.length > 100) {
    nodeSep = 30;
    rankSep = 120;
  }
  if (limitedNodes.length > 200) {
    nodeSep = 20;
    rankSep = 80;
  }

  dagreGraph.setGraph({
    rankdir: "LR",
    nodesep: nodeSep,
    ranksep: rankSep,
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

  var nodesWithCorruptedY: number = 0;

  // Apply the layout to the nodes
  limitedNodes.forEach((node) => {
    const gNode = dagreGraph.node(node.id);

    // Dagre has a bug returning NaN for y positions,
    // which causes the nodes to be positioned incorrectly
    // I didn't manage to find the root cause, so here is a "dirty" fix.
    // Fix for https://github.com/keephq/keep/issues/4455
    if (Number.isNaN(gNode.y)) {
      if (gNode.rank) {
        gNode.y = (gNode.rank + nodesWithCorruptedY) * nodeHeight * 1.5;
      } else {
        gNode.y = nodesWithCorruptedY * nodeHeight * 1.5;
      }
      nodesWithCorruptedY++;
    }

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
          displayedNodes: limitedNodes.length,
        }
      : undefined,
  };
}
