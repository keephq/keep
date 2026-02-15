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
    // Safety check: only add edge if both source and target nodes exist in the graph
    // (Dagre might crash if it tries to layout an edge with missing nodes)
    if (dagreGraph.hasNode(edge.source) && dagreGraph.hasNode(edge.target)) {
      dagreGraph.setEdge(edge.source, edge.target);
    }
  });

  dagre.layout(dagreGraph);

  var nodesWithCorruptedY: number = 0

  nodes.forEach((node) => {
    const gNode = dagreGraph.node(node.id);

    // Dagre has a bug returning NaN for y positions,
    // which causes the nodes to be positioned incorrectly
    // I didn't manage to find the root cause, so here is a "dirty" fix.
    // Fix for https://github.com/keephq/keep/issues/4455
    if(Number.isNaN(gNode.y)) {
      if (gNode.rank) {
        gNode.y = (gNode.rank + nodesWithCorruptedY) * nodeHeight * 1.5;
      }
      else {
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

  return { nodes, edges };
}
