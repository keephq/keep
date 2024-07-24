"use client";
import React, { useEffect, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
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
import "./topology.css";

const NODE_WIDTH = 220;
const NODE_HEIGHT = 80;

// Function to create a Dagre layout
const dagreGraph = new graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const getLayoutedElements = (nodes: any[], edges: any[]) => {
  dagreGraph.setGraph({ rankdir: "LR", nodesep: 50, ranksep: 200 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
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
      x: nodeWithPosition.x - NODE_WIDTH / 2,
      y: nodeWithPosition.y - NODE_HEIGHT / 2,
    };

    return node;
  });

  return { nodes, edges };
};

const TopologyPage = () => {
  // State for nodes and edges
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  const onEdgeHover = (eventType: "enter" | "leave", edge: Edge) => {
    const newEdges = [...edges];
    const currentEdge = newEdges.find((e) => e.id === edge.id);
    if (currentEdge) {
      currentEdge.style = eventType === "enter" ? { stroke: "orange" } : {};
      setEdges(newEdges);
    }
  };

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
          labelStyle: { fill: "black" },
          labelBgPadding: [10, 5],
          labelBgStyle: {
            strokeWidth: 1,
            strokeDasharray: "5,5",
            stroke: "gray",
          },
          labelBgBorderRadius: 10,
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
          snapToGrid
          fitViewOptions={{ padding: 0.2 }}
          onEdgeMouseEnter={(_event, edge) => onEdgeHover("enter", edge)}
          onEdgeMouseLeave={(_event, edge) => onEdgeHover("leave", edge)}
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
