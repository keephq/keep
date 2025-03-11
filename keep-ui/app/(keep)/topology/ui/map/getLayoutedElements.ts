import { TopologyNode } from "@/app/(keep)/topology/model";
import { Edge, Position } from "@xyflow/react";
import dagre, { graphlib } from "@dagrejs/dagre";
import { nodeHeight, nodeWidth } from "@/app/(keep)/topology/ui/map/styles";

export function getLayoutedElements(nodes: TopologyNode[], edges: Edge[]) {
  const dagreGraph = new graphlib.Graph({});

  // Function to create a Dagre layout
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: "LR",
    nodesep: 50,
    ranksep: 200,
  });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
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

  return { nodes, edges };
}
