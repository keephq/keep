"use client";
import React, { useEffect, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import dagre, { graphlib } from "@dagrejs/dagre";
import "@xyflow/react/dist/style.css";
import CustomNode from "./custom-node";
import { serviceDefinitions, serviceDependencies } from "./mock-topology-data";
import { Card } from "@tremor/react";

// Function to create a Dagre layout
const dagreGraph = new graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const getLayoutedElements = (nodes: any[], edges: any[]) => {
  dagreGraph.setGraph({ rankdir: "LR", nodesep: 50, ranksep: 100 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 200, height: 100 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.targetPosition = "left";
    node.sourcePosition = "right";

    node.position = {
      x: nodeWithPosition.x - 200 / 2,
      y: nodeWithPosition.y - 100 / 2,
    };

    return node;
  });

  return { nodes, edges };
};

const TopologyPage = () => {
  // State for nodes and edges
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<
    { id: string; source: string; target: string; label: string }[]
  >([]);

  useEffect(() => {
    // Create nodes from service definitions
    const newNodes = Object.keys(serviceDefinitions).map((serviceId) => ({
      id: serviceId,
      type: "customNode",
      data: serviceDefinitions[serviceId],
      position: { x: 0, y: 0 }, // Dagre will handle the actual position
    }));

    // Create edges from service dependencies
    const newEdges: any = [];
    Object.keys(serviceDependencies).forEach((service) => {
      serviceDependencies[service].forEach((dependency) => {
        newEdges.push({
          id: `${service}-${dependency.service}`,
          source: service,
          target: dependency.service,
          label: dependency.protocol,
          animated: true,
          // style: { stroke: "red", strokeWidth: 2, strokeDasharray: "5,5" },
          labelStyle: { fill: "orange", fontWeight: 700 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
          },
        });
      });
    });

    const layoutedElements = getLayoutedElements(newNodes, newEdges);
    setNodes(layoutedElements.nodes);
    setEdges(layoutedElements.edges);
  }, []);

  return (
    <Card className="p-4 md:p-10 mx-auto h-full">
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodeTypes={{ customNode: CustomNode }}
        >
          <Background variant={BackgroundVariant.Dots} />
          <MiniMap pannable zoomable />
          <Controls />
        </ReactFlow>
      </ReactFlowProvider>
    </Card>
  );
};

export default TopologyPage;
