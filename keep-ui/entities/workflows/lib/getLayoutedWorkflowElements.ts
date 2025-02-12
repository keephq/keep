import { FlowNode } from "../model/types";
import { Edge } from "@xyflow/react";
import dagre, { graphlib } from "@dagrejs/dagre";
import { Position } from "@xyflow/react";

export const getLayoutedWorkflowElements = (
  nodes: FlowNode[],
  edges: Edge[],
  options: { "elk.direction"?: string } = {}
) => {
  const isHorizontal = options["elk.direction"] === "RIGHT";
  const dagreGraph = new graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Set graph direction and spacing
  dagreGraph.setGraph({
    rankdir: isHorizontal ? "LR" : "TB",
    nodesep: 80,
    ranksep: 80,
    edgesep: 80,
  });

  // Add nodes to dagre graph
  nodes.forEach((node) => {
    const type = node?.data?.type
      ?.replace("step-", "")
      ?.replace("action-", "")
      ?.replace("condition-", "")
      ?.replace("__end", "");

    let width = ["start", "end"].includes(type) ? 80 : 280;
    let height = 80;

    // Special case for trigger start and end nodes, which act as section headers
    if (node.id === "trigger_start" || node.id === "trigger_end") {
      width = 150;
      height = 40;
    }

    dagreGraph.setNode(node.id, { width, height });
  });

  // Add edges to dagre graph
  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  // Run the layout
  dagre.layout(dagreGraph);

  // Get the positioned nodes and edges
  const layoutedNodes = nodes.map((node) => {
    const dagreNode = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      style: {
        ...node.style,
        width: dagreNode.width as number,
        height: dagreNode.height as number,
      },
      // Dagre provides positions with the center of the node as origin
      position: {
        x: dagreNode.x - dagreNode.width / 2,
        y: dagreNode.y - dagreNode.height / 2,
      },
    };
  });

  return {
    nodes: layoutedNodes,
    edges,
  };
};
