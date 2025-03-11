import { TopologyNode } from "@/app/(keep)/topology/model";
import { Edge, Position } from "@xyflow/react";
import dagre, { graphlib } from "@dagrejs/dagre";
import { nodeHeight, nodeWidth } from "@/app/(keep)/topology/ui/map/styles";

export function getLayoutedElements(nodes: TopologyNode[], edges: Edge[]) {
  // Create a new graph
  const dagreGraph = new graphlib.Graph({ multigraph: true });

  // Set graph options
  dagreGraph.setGraph({
    rankdir: "LR",
    nodesep: 50,
    ranksep: 200,
  });

  // Default edge label
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Filter out invalid nodes and edges before adding them to the graph
  const validNodes = nodes.filter((node) => node && node.id);
  const validEdges = edges.filter(
    (edge) =>
      edge &&
      edge.source &&
      edge.target &&
      edge.source !== "" &&
      edge.target !== ""
  );

  // Add nodes to the graph
  validNodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  // Add edges to the graph with unique identifiers
  validEdges.forEach((edge) => {
    // Only add edges where both endpoints exist in our nodes
    if (
      validNodes.some((n) => n.id === edge.source) &&
      validNodes.some((n) => n.id === edge.target)
    ) {
      dagreGraph.setEdge(
        edge.source,
        edge.target,
        { weight: 1 }, // Explicitly set weight
        edge.id || `${edge.source}-${edge.target}` // Ensure unique edge identifier
      );
    }
  });

  // Check if we have a valid graph with nodes and edges
  if (validNodes.length > 0 && validEdges.length > 0) {
    try {
      // Try to run the layout algorithm
      dagre.layout(dagreGraph);

      // Update node positions from layout results
      validNodes.forEach((node) => {
        const gNode = dagreGraph.node(node.id);

        // Only update if the node was processed by dagre
        if (gNode) {
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
        }
      });

      return { nodes: validNodes, edges: validEdges };
    } catch (error) {
      console.error("Dagre layout error:", error);

      // Fallback layout: arrange nodes in a grid pattern
      return applyFallbackLayout(validNodes, validEdges);
    }
  } else {
    // Not enough valid data for graph layout
    return applyFallbackLayout(validNodes, validEdges);
  }
}

// Fallback layout if dagre fails
function applyFallbackLayout(nodes: TopologyNode[], edges: Edge[]) {
  // Simple grid layout (5 nodes per row)
  const rowSize = 5;
  const horizontalGap = nodeWidth + 100;
  const verticalGap = nodeHeight + 100;

  nodes.forEach((node, index) => {
    const row = Math.floor(index / rowSize);
    const col = index % rowSize;

    node.position = {
      x: col * horizontalGap + 50,
      y: row * verticalGap + 50,
    };

    node.style = {
      ...node.style,
      width: nodeWidth,
      height: nodeHeight,
    };

    node.targetPosition = Position.Left;
    node.sourcePosition = Position.Right;
  });

  return { nodes, edges };
}
